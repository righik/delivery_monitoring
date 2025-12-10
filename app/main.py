from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging
from app.database import get_db
from app import services
from app.logging_config import setup_logging

setup_logging(log_level="INFO", log_file="logs/app.log")

logger = logging.getLogger(__name__)

app = FastAPI(title="CDEK Delivery Monitoring")

templates = Jinja2Templates(directory="app/templates")

logger.info("🚀 Приложение CDEK Delivery Monitoring запущено")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    statistics = services.get_shipments_statistics(db)
    shipments = services.get_shipments_with_details(db)
    
    return templates.TemplateResponse(
        "shipments.html",
        {
            "request": request,
            "statistics": statistics,
            "shipments": shipments
        }
    )


@app.get("/shipments", response_class=HTMLResponse)
async def shipments_page(request: Request, db: Session = Depends(get_db)):
    statistics = services.get_shipments_statistics(db)
    shipments = services.get_shipments_with_details(db)
    
    return templates.TemplateResponse(
        "shipments.html",
        {
            "request": request,
            "statistics": statistics,
            "shipments": shipments
        }
    )


@app.get("/api/shipments")
async def api_shipments(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    return services.get_shipments_with_details(db)


@app.post("/update-statuses")
async def update_statuses(db: Session = Depends(get_db)) -> Dict[str, Any]:
    logger.info("🔄 Запрос на обновление статусов всех отправлений")
    
    results = await services.update_all_shipments_statuses(db)
    
    success_count = sum(1 for r in results if r.get("success"))
    failed_count = len(results) - success_count
    total_new_statuses = sum(r.get("new_statuses", 0) for r in results if r.get("success"))
    
    logger.info(f"✅ Обновление завершено: успешно={success_count}, ошибок={failed_count}, новых статусов={total_new_statuses}")
    
    return {
        "success": True,
        "total_shipments": len(results),
        "updated_successfully": success_count,
        "failed": failed_count,
        "total_new_statuses": total_new_statuses,
        "details": results
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}
