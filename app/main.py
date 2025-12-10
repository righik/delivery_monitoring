from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database import get_db
from app import services

app = FastAPI(title="CDEK Delivery Monitoring")

templates = Jinja2Templates(directory="app/templates")


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
    results = await services.update_all_shipments_statuses(db)
    
    success_count = sum(1 for r in results if r.get("success"))
    failed_count = len(results) - success_count
    total_new_statuses = sum(r.get("new_statuses", 0) for r in results if r.get("success"))
    
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
