import httpx
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.config import settings

logger = logging.getLogger(__name__)


class CDEKClient:
    def __init__(self):
        self.base_url = settings.cdek_api_url
        self.client_id = settings.cdek_client_id
        self.client_secret = settings.cdek_client_secret
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
    
    async def _get_token(self) -> str:
        if self._token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            logger.debug("Используется кэшированный токен")
            return self._token
        
        logger.info("Запрос нового токена авторизации")
        
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/oauth/token"
                params = {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": "***"  # Скрываем секрет в логах
                }
                
                logger.debug(f"POST {url}")
                logger.debug(f"Параметры: {params}")
                
                response = await client.post(
                    url,
                    params={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret
                    }
                )
                
                logger.debug(f"Статус ответа: {response.status_code}")
                
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"✅ Токен получен успешно, expires_in: {data.get('expires_in')}s")
                logger.debug(f"Ответ API: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                self._token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                
                return self._token
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Ошибка HTTP при получении токена: {e.response.status_code}")
            logger.error(f"Ответ сервера: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при получении токена: {e}")
            raise
    
    async def get_tracking_info(self, tracking_code: str) -> Optional[Dict[str, Any]]:
        logger.info(f"📦 Запрос информации о заказе: {tracking_code}")
        
        try:
            token = await self._get_token()
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/orders"
                params = {"cdek_number": tracking_code}
                
                logger.debug(f"GET {url}")
                logger.debug(f"Параметры: {params}")
                logger.debug(f"Authorization: Bearer {token[:20]}...")
                
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params
                )
                
                logger.debug(f"Статус ответа: {response.status_code}")
                
                if response.status_code == 404:
                    logger.warning(f"⚠️ Заказ {tracking_code} не найден (404)")
                    return None
                
                if response.status_code == 400:
                    error_data = response.json()
                    logger.warning(f"⚠️ Ошибка 400 для заказа {tracking_code}")
                    logger.warning(f"Детали: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                    
                    # Проверяем на forbidden
                    if "v2_entity_forbidden" in str(error_data):
                        logger.warning(
                            f"💡 Заказ {tracking_code} запрещен для доступа. "
                            f"Возможные причины:\n"
                            f"  1. Заказ принадлежит другому аккаунту\n"
                            f"  2. Используется тестовый API для продакшн заказа (или наоборот)\n"
                            f"  3. Неверный формат трек-номера"
                        )
                    return None
                
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"Полный ответ API:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
                
                if not data.get("entity"):
                    logger.warning(f"⚠️ Пустой ответ для заказа {tracking_code}")
                    logger.warning(f"Структура ответа: {list(data.keys())}")
                    return None
                
                entity = data["entity"]
                
                # API может вернуть либо список заказов, либо один объект
                if isinstance(entity, dict):
                    # Один заказ (при поиске по im_number или uuid)
                    order = entity
                    logger.debug(f"Получен один заказ (dict)")
                elif isinstance(entity, list):
                    # Массив заказов (при поиске по cdek_number)
                    if not entity:
                        logger.warning(f"⚠️ Пустой список заказов для {tracking_code}")
                        logger.warning(f"Полный ответ: {json.dumps(data, indent=2, ensure_ascii=False)}")
                        return None
                    order = entity[0]
                    logger.debug(f"Получен массив заказов, взят первый")
                else:
                    logger.error(f"❌ Неожиданный тип entity: {type(entity)}")
                    logger.error(f"Содержимое entity: {entity}")
                    return None
                logger.info(f"✅ Информация о заказе {tracking_code} получена")
                logger.info(f"   UUID: {order.get('uuid')}")
                logger.info(f"   Номер СДЭК: {order.get('cdek_number', 'не присвоен')}")
                logger.info(f"   Номер ИМ: {order.get('number', 'нет')}")
                logger.info(f"   Статусов: {len(order.get('statuses', []))}")
                return order
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Ошибка HTTP при запросе заказа {tracking_code}: {e.response.status_code}")
            logger.error(f"Ответ сервера: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при запросе заказа {tracking_code}: {e}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise
    
    async def get_order_statuses(self, tracking_code: str) -> List[Dict[str, Any]]:
        logger.info(f"📊 Получение статусов для заказа: {tracking_code}")
        
        order_info = await self.get_tracking_info(tracking_code)
        
        if not order_info:
            logger.warning(f"⚠️ Не удалось получить информацию о заказе {tracking_code}")
            return []
        
        statuses = order_info.get("statuses", [])
        logger.info(f"Найдено статусов: {len(statuses)}")
        
        result = []
        for idx, status in enumerate(statuses, 1):
            status_data = {
                "code": status.get("code", ""),
                "name": status.get("name", ""),
                "datetime": status.get("date_time", ""),
                "city": status.get("city", ""),
                "reason_code": status.get("reason_code"),
                "reason": status.get("reason")
            }
            result.append(status_data)
            
            logger.debug(f"Статус #{idx}:")
            logger.debug(f"  Код: {status_data['code']}")
            logger.debug(f"  Название: {status_data['name']}")
            logger.debug(f"  Время: {status_data['datetime']}")
            logger.debug(f"  Город: {status_data['city']}")
            if status_data['reason']:
                logger.debug(f"  Причина: {status_data['reason']}")
        
        logger.info(f"✅ Обработано статусов: {len(result)}")
        
        return result


cdek_client = CDEKClient()
