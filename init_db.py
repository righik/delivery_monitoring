from app.database import SessionLocal
from app.models import Shipment

test_tracking_codes = [
    "10192769726",
]


def init_test_data():
    db = SessionLocal()
    try:
        existing_count = db.query(Shipment).count()
        
        if existing_count > 0:
            print(f"База данных уже содержит {existing_count} отправлений.")
            print("Пропускаем инициализацию тестовых данных.")
            return
        
        print("Добавление тестовых трек-номеров...")
        
        for tracking_code in test_tracking_codes:
            shipment = Shipment(tracking_code=tracking_code)
            db.add(shipment)
            print(f"  ✓ Добавлен трек-номер: {tracking_code}")
        
        db.commit()
        print(f"\nУспешно добавлено {len(test_tracking_codes)} тестовых отправлений.")
        print("\nВажно: Замените эти трек-номера на реальные в таблице 'shipments'")
        print("или используйте эндпоинт /update-statuses для получения данных из API СДЭК.")
        
    except Exception as e:
        print(f"Ошибка при инициализации: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_test_data()
