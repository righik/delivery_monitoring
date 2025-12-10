import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.config import settings


class CDEKClient:
    def __init__(self):
        self.base_url = settings.cdek_api_url
        self.client_id = settings.cdek_client_id
        self.client_secret = settings.cdek_client_secret
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
    
    async def _get_token(self) -> str:
        if self._token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            return self._token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth/token",
                params={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            
            self._token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
            
            return self._token
    
    async def get_tracking_info(self, tracking_code: str) -> Optional[Dict[str, Any]]:
        token = await self._get_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/orders",
                headers={"Authorization": f"Bearer {token}"},
                params={"cdek_number": tracking_code}
            )
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get("entity"):
                return None
            
            orders = data["entity"]
            if not orders:
                return None
            print(orders)
            return orders[0]
    
    async def get_order_statuses(self, tracking_code: str) -> List[Dict[str, Any]]:
        order_info = await self.get_tracking_info(tracking_code)
        
        if not order_info:
            return []
        
        statuses = order_info.get("statuses", [])
        
        result = []
        for status in statuses:
            result.append({
                "code": status.get("code", ""),
                "name": status.get("name", ""),
                "datetime": status.get("date_time", ""),
                "city": status.get("city", ""),
                "reason_code": status.get("reason_code"),
                "reason": status.get("reason")
            })
        print(result)
        return result


cdek_client = CDEKClient()
