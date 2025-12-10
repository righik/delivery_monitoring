"""
Скрипт инициализации для Docker
Создает тестовые заказы, получает трек-номера и добавляет их в БД
"""
import asyncio
import httpx
import sys
from datetime import datetime
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal, engine
from app.models import Base, Shipment


async def create_test_order_and_get_number(client: httpx.AsyncClient, token: str, order_num: int):
    """Создать заказ и получить его данные"""
    print(f"\n📦 Создание тестового заказа #{order_num}...")
    
    order_data = {
        "type": 1,
        "number": f"DOCKER-TEST-{order_num}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "tariff_code": 1,
        "comment": f"Docker тестовый заказ #{order_num}",
        "sender": {
            "name": "Docker Test Sender",
            "phones": [{"number": "+79000000001"}]
        },
        "recipient": {
            "name": f"Docker Test Recipient {order_num}",
            "phones": [{"number": "+79000000002"}]
        },
        "from_location": {
            "code": 44,
            "fias_guid": "0c5b2444-70a0-4932-980c-b4dc0d3f02b5",
            "address": "ул. Тестовая, д. 1"
        },
        "to_location": {
            "code": 137,
            "fias_guid": "c2deb16a-0330-4f05-821f-1d09c93331e6",
            "address": "ул. Тестовая, д. 2"
        },
        "packages": [{
            "number": "1",
            "weight": 1000,
            "length": 20,
            "width": 15,
            "height": 10,
            "comment": "Docker test package",
            "items": [{
                "name": "Docker Test Item",
                "ware_key": f"DOCKER-ITEM-{order_num}",
                "payment": {"value": 0},
                "cost": 1000,
                "weight": 1000,
                "amount": 1
            }]
        }]
    }
    
    try:
        response = await client.post(
            f"{settings.cdek_api_url}/orders",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=order_data
        )
        
        if response.status_code in [200, 201, 202]:
            result = response.json()
            entity = result.get("entity", {})
            uuid = entity.get("uuid")
            im_number = order_data.get("number")
            
            print(f"✅ Заказ создан: UUID={uuid}, ИМ={im_number}")
            
            # Ждем немного
            await asyncio.sleep(2)
            
            # Получаем полную информацию
            order_response = await client.get(
                f"{settings.cdek_api_url}/orders/{uuid}",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if order_response.status_code == 200:
                order_info = order_response.json().get("entity", {})
                cdek_number = order_info.get("cdek_number")
                
                # Возвращаем cdek_number если есть, иначе im_number
                tracking_code = cdek_number if cdek_number else im_number
                print(f"   Трек-номер: {tracking_code}")
                
                return {
                    "tracking_code": tracking_code,
                    "uuid": uuid,
                    "im_number": im_number,
                    "cdek_number": cdek_number
                }
            else:
                print(f"⚠️ Не удалось получить детали заказа")
                return {
                    "tracking_code": im_number,
                    "uuid": uuid,
                    "im_number": im_number,
                    "cdek_number": None
                }
        else:
            print(f"❌ Ошибка создания: {response.status_code}")
            print(f"   {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return None


async def initialize_test_data():
    """Главная функция инициализации"""
    print("=" * 70)
    print("🚀 Docker инициализация тестовых данных")
    print("=" * 70)
    print(f"API: {settings.cdek_api_url}")
    print(f"DB: {settings.database_url}")
    print("-" * 70)
    
    # Проверяем наличие учетных данных
    if not settings.cdek_client_id or not settings.cdek_client_secret:
        print("❌ Ошибка: CDEK_CLIENT_ID и CDEK_CLIENT_SECRET должны быть установлены!")
        print("   Создайте файл .env с учетными данными")
        sys.exit(1)
    
    # Авторизация
    print("\n🔑 Авторизация в CDEK API...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{settings.cdek_api_url}/oauth/token",
                params={
                    "grant_type": "client_credentials",
                    "client_id": settings.cdek_client_id,
                    "client_secret": settings.cdek_client_secret
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Ошибка авторизации: {response.text}")
                sys.exit(1)
            
            token = response.json()["access_token"]
            print("✅ Авторизация успешна")
            
        except Exception as e:
            print(f"❌ Ошибка подключения к API: {e}")
            sys.exit(1)
        
        # Создаем 3 тестовых заказа
        print("\n" + "=" * 70)
        print("📦 Создание тестовых заказов...")
        print("=" * 70)
        
        orders = []
        for i in range(1, 4):
            order = await create_test_order_and_get_number(client, token, i)
            if order:
                orders.append(order)
            await asyncio.sleep(1)
        
        if not orders:
            print("\n❌ Не удалось создать ни одного заказа")
            sys.exit(1)
        
        print(f"\n✅ Создано заказов: {len(orders)}")
    
    # Добавляем в БД
    print("\n" + "=" * 70)
    print("💾 Добавление в базу данных...")
    print("=" * 70)
    
    db: Session = SessionLocal()
    try:
        added_count = 0
        for order in orders:
            tracking_code = order["tracking_code"]
            
            # Проверяем, нет ли уже такого трек-номера
            existing = db.query(Shipment).filter(
                Shipment.tracking_code == tracking_code
            ).first()
            
            if existing:
                print(f"⚠️ Трек-номер {tracking_code} уже существует, пропускаем")
                continue
            
            shipment = Shipment(tracking_code=tracking_code)
            db.add(shipment)
            added_count += 1
            print(f"✅ Добавлен: {tracking_code}")
        
        db.commit()
        print(f"\n✅ Добавлено новых отправлений: {added_count}")
        
        # Показываем итоговую статистику
        total = db.query(Shipment).count()
        print(f"📊 Всего отправлений в БД: {total}")
        
    except Exception as e:
        print(f"❌ Ошибка при работе с БД: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
    
    print("\n" + "=" * 70)
    print("✅ Инициализация завершена успешно!")
    print("=" * 70)
    print("\n📝 Созданные трек-номера:")
    for idx, order in enumerate(orders, 1):
        print(f"  {idx}. {order['tracking_code']}")
        if order['cdek_number']:
            print(f"     CDEK: {order['cdek_number']}")
        print(f"     ИМ: {order['im_number']}")
        print(f"     UUID: {order['uuid']}")
    
    print("\n🌐 Приложение готово к запуску!")
    print("   Откройте: http://localhost:8000/shipments")


def main():
    """Entry point"""
    try:
        asyncio.run(initialize_test_data())
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
