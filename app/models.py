from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Shipment(Base):
    __tablename__ = "shipments"
    
    id = Column(Integer, primary_key=True, index=True)
    tracking_code = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    statuses = relationship("ShipmentStatus", back_populates="shipment", cascade="all, delete-orphan")


class ShipmentStatus(Base):
    __tablename__ = "shipment_statuses"
    
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False, index=True)
    status_code = Column(String(50), nullable=False)
    status_text = Column(Text, nullable=False)
    status_datetime = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    shipment = relationship("Shipment", back_populates="statuses")
