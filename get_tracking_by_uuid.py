import asyncio
import httpx
import json
from datetime import datetime
from app.config import settings


async def get_order_by_uuid(client: httpx.AsyncClient, token: str, uuid: str):
    """
    Получить информацию о заказе по UUID
    """
    try:
        response = await client.get(
            f"{settings.cdek_api_url}/orders/{uuid}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("entity", {})
        else:
            print(f"  ⚠️ Ошибка {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"  ❌ Исключение: {e}")
        return None


async def main():
    print("=" * 70)
    print("🔍 Получение трек-номеров по UUID")
    print("=" * 70)
    print(f"API: {settings.cdek_api_url}")
    print("-" * 70)
    
    # UUID заказов (можно изменить на свои)
    uuids = [
        "df8841ea-7be3-46b3-bf13-67f3b19ba2fe",
    ]
    
    print("\n📝 UUID для проверки:")
    for idx, uuid in enumerate(uuids, 1):
        print(f"  {idx}. {uuid}")
    
    # Авторизация
    print("\n🔑 Авторизация...")
    async with httpx.AsyncClient(timeout=30.0) as client:
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
            return
        
        token = response.json()["access_token"]
        print("✅ Авторизация успешна")
        
        # Получаем информацию по каждому UUID
        print("\n" + "=" * 70)
        print("📦 Получение информации о заказах...")
        print("=" * 70)
        
        orders_info = []
        tracking_codes = []
        
        for idx, uuid in enumerate(uuids, 1):
            print(f"\n🔍 Заказ #{idx}: {uuid}")
            
            order = await get_order_by_uuid(client, token, uuid)
            
            if order:
                cdek_number = order.get("cdek_number")
                im_number = order.get("number")
                
                print(f"  ✅ Заказ найден")
                print(f"     Номер ИМ: {im_number}")
                
                if cdek_number:
                    print(f"     Номер СДЭК: {cdek_number} ✅")
                    tracking_codes.append(cdek_number)
                    orders_info.append({
                        "uuid": uuid,
                        "im_number": im_number,
                        "cdek_number": cdek_number,
                        "has_number": True
                    })
                else:
                    print(f"     Номер СДЭК: (еще не присвоен) ⏳")
                    orders_info.append({
                        "uuid": uuid,
                        "im_number": im_number,
                        "cdek_number": None,
                        "has_number": False
                    })
                
                # Показываем статусы
                statuses = order.get("statuses", [])
                if statuses:
                    latest_status = statuses[-1]
                    print(f"     Статус: {latest_status.get('name')} ({latest_status.get('code')})")
                    print(f"     Дата: {latest_status.get('date_time')}")
            else:
                print(f"  ❌ Не удалось получить информацию")
                orders_info.append({
                    "uuid": uuid,
                    "im_number": None,
                    "cdek_number": None,
                    "has_number": False
                })
            
            await asyncio.sleep(0.5)  # Небольшая задержка
        
        # Итоги
        print("\n" + "=" * 70)
        print("📊 Результаты:")
        print("=" * 70)
        
        orders_with_numbers = [o for o in orders_info if o["has_number"]]
        orders_without_numbers = [o for o in orders_info if not o["has_number"]]
        
        print(f"\n✅ Заказов с номерами СДЭК: {len(orders_with_numbers)}")
        print(f"⏳ Заказов без номеров: {len(orders_without_numbers)}")
        
        if tracking_codes:
            print("\n" + "=" * 70)
            print("📋 Трек-номера для init_db.py:")
            print("-" * 70)
            print("\ntest_tracking_codes = [")
            for code in tracking_codes:
                print(f'    "{code}",')
            print("]")
            print("\n" + "=" * 70)
            
            # Сохраняем в файл
            with open("tracking_codes_from_uuid.txt", "w", encoding="utf-8") as f:
                f.write("# Трек-номера СДЭК (получены по UUID)\n")
                f.write(f"# Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# API: {settings.cdek_api_url}\n\n")
                
                f.write("# Для init_db.py:\n")
                f.write("test_tracking_codes = [\n")
                for code in tracking_codes:
                    f.write(f'    "{code}",\n')
                f.write("]\n\n")
                
                f.write("# Детали заказов:\n")
                for order in orders_with_numbers:
                    f.write(f"\n# UUID: {order['uuid']}\n")
                    f.write(f"# ИМ: {order['im_number']}\n")
                    f.write(f"# СДЭК: {order['cdek_number']}\n")
            
            print("\n💾 Результаты сохранены в: tracking_codes_from_uuid.txt")
            
            print("\n" + "=" * 70)
            print("✅ Готово!")
            print("=" * 70)
            print("\n📝 Следующие шаги:")
            print("  1. Скопируйте код выше в init_db.py")
            print("  2. Запустите: python init_db.py")
            print("  3. Запустите: python run.py")
            print("  4. Откройте: http://localhost:8000/shipments")
            print("  5. Нажмите 'Обновить статусы'")
        
        if orders_without_numbers:
            print("\n" + "=" * 70)
            print("⏳ Заказы без номеров СДЭК:")
            print("-" * 70)
            for order in orders_without_numbers:
                print(f"\nUUID: {order['uuid']}")
                if order['im_number']:
                    print(f"ИМ: {order['im_number']}")
                print("Статус: Номер СДЭК еще не присвоен")
            
            print("\n💡 Что делать:")
            print("  1. Подождите 1-2 минуты")
            print("  2. Запустите этот скрипт снова:")
            print("     python get_tracking_by_uuid.py")
            print("  3. Или проверьте статус в ЛК СДЭК")


if __name__ == "__main__":
    asyncio.run(main())
