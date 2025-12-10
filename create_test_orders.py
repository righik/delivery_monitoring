import asyncio
import httpx
import json
from datetime import datetime
from app.config import settings


async def create_test_order(client: httpx.AsyncClient, token: str, order_number: int):
    """
    Создать тестовый заказ через API СДЭК
    """
    print(f"\n📦 Создание заказа #{order_number}...")
    
    # Данные тестового заказа согласно документации API СДЭК
    # Используем минимальный набор полей для успешного создания
    order_data = {
        "type": 1,  # 1 - интернет-магазин (онлайн заказ)
        "number": f"TEST-ORDER-{order_number}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "tariff_code": 1,  # 1 - Экспресс лайт дверь-дверь (базовый тариф)
        "comment": f"Тестовый заказ для мониторинга #{order_number}",
        "sender": {
            "name": "Тестовый отправитель",
            "phones": [{"number": "+79000000001"}]
        },
        "recipient": {
            "name": f"Тестовый получатель {order_number}",
            "phones": [{"number": "+79000000002"}]
        },
        "from_location": {
            "code": 44,  # Москва
            "fias_guid": "0c5b2444-70a0-4932-980c-b4dc0d3f02b5",  # ФИАС Москвы
            "address": "ул. Тестовая, д. 1"
        },
        "to_location": {
            "code": 137,  # Санкт-Петербург  
            "fias_guid": "c2deb16a-0330-4f05-821f-1d09c93331e6",  # ФИАС СПб
            "address": "ул. Тестовая, д. 2"
        },
        "packages": [
            {
                "number": "1",
                "weight": 1000,  # 1 кг (в граммах)
                "length": 20,  # см
                "width": 15,   # см
                "height": 10,  # см
                "comment": "Тестовая посылка",
                "items": [
                    {
                        "name": "Тестовый товар",
                        "ware_key": f"TEST-ITEM-{order_number}",
                        "payment": {
                            "value": 0  # 0 - без наложенного платежа
                        },
                        "cost": 1000,  # Объявленная стоимость в рублях
                        "weight": 1000,  # Вес товара в граммах
                        "amount": 1  # Количество
                    }
                ]
            }
        ]
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
        
        print(f"Статус: {response.status_code}")
        
        if response.status_code in [200, 201, 202]:  # 202 = Accepted
            result = response.json()
            entity = result.get("entity", {})
            
            print(f"✅ Заказ создан успешно!")
            print(f"   UUID: {entity.get('uuid')}")
            
            # Номер ИМ из исходных данных
            im_number = order_data.get("number")
            print(f"   Номер ИМ: {im_number}")
            
            # Номер СДЭК присваивается не сразу, может быть пустым
            cdek_number = entity.get("cdek_number")
            if cdek_number:
                print(f"   Номер СДЭК: {cdek_number}")
            else:
                print(f"   Номер СДЭК: (будет присвоен позже)")
            
            return {
                "success": True,
                "uuid": entity.get("uuid"),
                "number": im_number,
                "cdek_number": cdek_number,
                "entity": entity
            }
        else:
            error_data = response.json()
            print(f"❌ Ошибка создания заказа")
            print(f"Детали:\n{json.dumps(error_data, indent=2, ensure_ascii=False)}")
            
            return {
                "success": False,
                "error": error_data
            }
    
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return {
            "success": False,
            "error": str(e)
        }


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
            return None
    except Exception as e:
        print(f"Ошибка получения заказа: {e}")
        return None


async def wait_for_cdek_numbers(client: httpx.AsyncClient, token: str, orders: list):
    """
    Ожидание присвоения номеров СДЭК
    """
    print("\n⏳ Ожидание присвоения номеров СДЭК...")
    print("(Это может занять несколько секунд)")
    
    max_attempts = 10
    delay = 3  # секунды между попытками
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 Попытка {attempt}/{max_attempts}...")
        
        all_have_numbers = True
        
        for order in orders:
            if not order.get("success"):
                continue
            
            if order.get("cdek_number"):
                print(f"  ✅ {order['number']}: {order['cdek_number']}")
                continue
            
            # Запрашиваем обновленную информацию
            uuid = order.get("uuid")
            updated_order = await get_order_by_uuid(client, token, uuid)
            
            if updated_order:
                cdek_number = updated_order.get("cdek_number")
                if cdek_number:
                    order["cdek_number"] = cdek_number
                    print(f"  ✅ {order['number']}: {cdek_number} (получен!)")
                else:
                    all_have_numbers = False
                    print(f"  ⏳ {order['number']}: ожидание...")
            else:
                all_have_numbers = False
                print(f"  ⚠️ {order['number']}: не удалось получить")
        
        if all_have_numbers:
            print("\n✅ Все номера СДЭК получены!")
            return True
        
        if attempt < max_attempts:
            print(f"\nОжидание {delay} секунд...")
            await asyncio.sleep(delay)
    
    print("\n⚠️ Не все номера были получены за отведенное время")
    print("Номера могут быть присвоены позже. Попробуйте запустить скрипт снова через минуту.")
    return False


async def main():
    print("=" * 70)
    print("🚀 Создание тестовых заказов СДЭК")
    print("=" * 70)
    print(f"API: {settings.cdek_api_url}")
    print("-" * 70)
    
    # Количество заказов для создания
    num_orders = int(input("\nСколько тестовых заказов создать? (рекомендуется 3-5): ").strip() or "3")
    
    if num_orders < 1 or num_orders > 10:
        print("❌ Количество должно быть от 1 до 10")
        return
    
    print(f"\n📝 Будет создано заказов: {num_orders}")
    
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
        
        # Создаем заказы
        print("\n" + "=" * 70)
        print("📦 Создание заказов...")
        print("=" * 70)
        
        orders = []
        for i in range(1, num_orders + 1):
            result = await create_test_order(client, token, i)
            orders.append(result)
            await asyncio.sleep(1)  # Небольшая задержка между запросами
        
        # Подсчет успешных
        successful_orders = [o for o in orders if o.get("success")]
        failed_orders = [o for o in orders if not o.get("success")]
        
        print("\n" + "=" * 70)
        print(f"📊 Результат создания:")
        print(f"  ✅ Успешно: {len(successful_orders)}")
        print(f"  ❌ Ошибок: {len(failed_orders)}")
        print("=" * 70)
        
        if not successful_orders:
            print("\n❌ Не удалось создать ни одного заказа")
            return
        
        # Ожидаем присвоения номеров СДЭК
        await wait_for_cdek_numbers(client, token, successful_orders)
        
        # Собираем трек-номера
        tracking_codes = []
        uuids_without_numbers = []
        
        print("\n" + "=" * 70)
        print("📋 Итоговый список:")
        print("=" * 70)
        
        for order in successful_orders:
            cdek_number = order.get("cdek_number")
            if cdek_number:
                tracking_codes.append(cdek_number)
                print(f"✅ {order['number']}")
                print(f"   UUID: {order['uuid']}")
                print(f"   Номер СДЭК: {cdek_number}")
            else:
                uuids_without_numbers.append(order['uuid'])
                print(f"⏳ {order['number']}")
                print(f"   UUID: {order['uuid']}")
                print(f"   Номер СДЭК: (еще не присвоен)")
        
        # Сохраняем результаты
        if tracking_codes:
            print("\n" + "=" * 70)
            print("✅ Готовый код для init_db.py:")
            print("-" * 70)
            print("\ntest_tracking_codes = [")
            for code in tracking_codes:
                print(f'    "{code}",')
            print("]")
            print("\n" + "=" * 70)
            
            # Сохраняем в файл
            with open("test_orders.txt", "w", encoding="utf-8") as f:
                f.write("# Тестовые заказы СДЭК\n")
                f.write(f"# Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# API: {settings.cdek_api_url}\n\n")
                
                f.write("# Трек-номера для init_db.py:\n")
                f.write("test_tracking_codes = [\n")
                for code in tracking_codes:
                    f.write(f'    "{code}",\n')
                f.write("]\n\n")
                
                f.write("# Детали заказов:\n")
                for order in successful_orders:
                    f.write(f"\n# {order['number']}\n")
                    f.write(f"#   UUID: {order['uuid']}\n")
                    f.write(f"#   СДЭК: {order.get('cdek_number', 'не присвоен')}\n")
            
            print("\n💾 Результаты сохранены в файл: test_orders.txt")
        
        if uuids_without_numbers:
            print("\n" + "=" * 70)
            print("⏳ Заказы без номеров СДЭК (проверьте позже):")
            print("-" * 70)
            for uuid in uuids_without_numbers:
                print(f"  UUID: {uuid}")
            print("\nДля проверки используйте:")
            print(f"  python test_single_tracking.py")
            print("  (введите UUID вместо трек-номера)")
        
        print("\n" + "=" * 70)
        print("✅ Готово!")
        print("=" * 70)
        
        if tracking_codes:
            print("\n📝 Следующие шаги:")
            print("  1. Скопируйте код выше в init_db.py")
            print("  2. Запустите: python init_db.py")
            print("  3. Запустите: python run.py")
            print("  4. Откройте: http://localhost:8000/shipments")
        else:
            print("\n⏳ Номера СДЭК еще не присвоены")
            print("  1. Подождите 1-2 минуты")
            print("  2. Запустите скрипт снова")
            print("  3. Или используйте UUID для проверки статуса")


if __name__ == "__main__":
    asyncio.run(main())
