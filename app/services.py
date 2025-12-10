from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.models import Shipment, ShipmentStatus
from app.cdek_client import cdek_client


DELIVERED_STATUS_CODES = ["DELIVERED", "RECEIVED_AT_DELIVERY_OFFICE"]


def get_all_shipments(db: Session) -> List[Shipment]:
    return db.query(Shipment).all()


def get_shipment_by_tracking_code(db: Session, tracking_code: str) -> Optional[Shipment]:
    return db.query(Shipment).filter(Shipment.tracking_code == tracking_code).first()


def create_shipment(db: Session, tracking_code: str) -> Shipment:
    shipment = Shipment(tracking_code=tracking_code)
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return shipment


def add_status_to_shipment(
    db: Session,
    shipment_id: int,
    status_code: str,
    status_text: str,
    status_datetime: datetime
) -> ShipmentStatus:
    existing_status = db.query(ShipmentStatus).filter(
        ShipmentStatus.shipment_id == shipment_id,
        ShipmentStatus.status_code == status_code,
        ShipmentStatus.status_datetime == status_datetime
    ).first()
    
    if existing_status:
        return existing_status
    
    status = ShipmentStatus(
        shipment_id=shipment_id,
        status_code=status_code,
        status_text=status_text,
        status_datetime=status_datetime
    )
    db.add(status)
    db.commit()
    db.refresh(status)
    return status


def get_latest_status(shipment: Shipment) -> Optional[ShipmentStatus]:
    if not shipment.statuses:
        return None
    return max(shipment.statuses, key=lambda s: s.status_datetime)


def get_first_status(shipment: Shipment) -> Optional[ShipmentStatus]:
    if not shipment.statuses:
        return None
    return min(shipment.statuses, key=lambda s: s.status_datetime)


def is_problematic_shipment(shipment: Shipment) -> bool:
    latest_status = get_latest_status(shipment)
    first_status = get_first_status(shipment)
    
    if not latest_status or not first_status:
        return False
    
    is_delivered = latest_status.status_code in DELIVERED_STATUS_CODES
    
    days_since_first_status = (datetime.utcnow() - first_status.status_datetime).days
    
    return not is_delivered and days_since_first_status > 3


async def update_shipment_statuses(db: Session, tracking_code: str) -> Dict[str, Any]:
    shipment = get_shipment_by_tracking_code(db, tracking_code)
    
    if not shipment:
        shipment = create_shipment(db, tracking_code)
    
    try:
        statuses = await cdek_client.get_order_statuses(tracking_code)
        
        new_statuses_count = 0
        for status_data in statuses:
            status_datetime_str = status_data.get("datetime", "")
            if status_datetime_str:
                try:
                    status_datetime = datetime.fromisoformat(status_datetime_str.replace("Z", "+00:00"))
                except:
                    status_datetime = datetime.utcnow()
            else:
                status_datetime = datetime.utcnow()
            
            status_text = status_data.get("name", "")
            if status_data.get("city"):
                status_text += f" ({status_data['city']})"
            if status_data.get("reason"):
                status_text += f" - {status_data['reason']}"
            
            existing = db.query(ShipmentStatus).filter(
                ShipmentStatus.shipment_id == shipment.id,
                ShipmentStatus.status_code == status_data["code"],
                ShipmentStatus.status_datetime == status_datetime
            ).first()
            
            if not existing:
                add_status_to_shipment(
                    db,
                    shipment.id,
                    status_data["code"],
                    status_text,
                    status_datetime
                )
                new_statuses_count += 1
        
        return {
            "success": True,
            "tracking_code": tracking_code,
            "new_statuses": new_statuses_count,
            "total_statuses": len(statuses)
        }
    
    except Exception as e:
        return {
            "success": False,
            "tracking_code": tracking_code,
            "error": str(e)
        }


async def update_all_shipments_statuses(db: Session) -> List[Dict[str, Any]]:
    shipments = get_all_shipments(db)
    results = []
    
    for shipment in shipments:
        result = await update_shipment_statuses(db, shipment.tracking_code)
        results.append(result)
    
    return results


def get_shipments_statistics(db: Session) -> Dict[str, int]:
    shipments = get_all_shipments(db)
    
    total = len(shipments)
    in_transit = 0
    delivered = 0
    problematic = 0
    
    for shipment in shipments:
        latest_status = get_latest_status(shipment)
        
        if latest_status:
            if latest_status.status_code in DELIVERED_STATUS_CODES:
                delivered += 1
            else:
                in_transit += 1
        
        if is_problematic_shipment(shipment):
            problematic += 1
    
    return {
        "total": total,
        "in_transit": in_transit,
        "delivered": delivered,
        "problematic": problematic
    }


def get_shipments_with_details(db: Session) -> List[Dict[str, Any]]:
    shipments = get_all_shipments(db)
    result = []
    
    for shipment in shipments:
        latest_status = get_latest_status(shipment)
        
        shipment_data = {
            "id": shipment.id,
            "tracking_code": shipment.tracking_code,
            "created_at": shipment.created_at.isoformat(),
            "current_status": None,
            "current_status_datetime": None,
            "problem": is_problematic_shipment(shipment)
        }
        
        if latest_status:
            shipment_data["current_status"] = latest_status.status_text
            shipment_data["current_status_datetime"] = latest_status.status_datetime.isoformat()
        
        result.append(shipment_data)
    
    return result
