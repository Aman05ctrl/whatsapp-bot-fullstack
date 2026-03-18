from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from property_backend.app.database import get_db
from property_backend.app.models.crm import Lead, BotLog
from property_backend.app.models.property import Client
from property_backend.app.schemas.crm import LeadCreate, LeadUpdate, LeadResponse, BotLogCreate, BotLogResponse
from property_backend.app.utils.dependencies import get_current_client

router = APIRouter()

# ─── LEADS ───────────────────────────────────────────────

@router.get("/leads", response_model=List[LeadResponse])
def get_leads(
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
    phone: Optional[str] = Query(None),
    lead_status: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
):
    query = db.query(Lead).filter(Lead.client_id == current_client.id)
    if phone:
        query = query.filter(Lead.phone.ilike(f"%{phone}%"))
    if lead_status:
        query = query.filter(Lead.lead_status == lead_status)
    if city:
        query = query.filter(Lead.city.ilike(f"%{city}%"))
    return query.order_by(Lead.last_updated.desc()).all()

@router.post("/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
def create_lead(
    lead_data: LeadCreate,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    lead = Lead(client_id=current_client.id, **lead_data.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

@router.put("/leads/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: int,
    lead_data: LeadUpdate,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.client_id == current_client.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for key, value in lead_data.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    db.commit()
    db.refresh(lead)
    return lead

@router.delete("/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead_id: int,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.client_id == current_client.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()

# ─── LOGS ────────────────────────────────────────────────

@router.get("/logs", response_model=List[BotLogResponse])
def get_logs(
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
    phone: Optional[str] = Query(None),
    reply_type: Optional[str] = Query(None),
):
    query = db.query(BotLog).filter(BotLog.client_id == current_client.id)
    if phone:
        query = query.filter(BotLog.phone.ilike(f"%{phone}%"))
    if reply_type:
        query = query.filter(BotLog.reply_type == reply_type)
    return query.order_by(BotLog.timestamp.desc()).all()

@router.post("/logs", response_model=BotLogResponse, status_code=status.HTTP_201_CREATED)
def create_log(
    log_data: BotLogCreate,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    log = BotLog(client_id=current_client.id, **log_data.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

@router.delete("/logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_log(
    log_id: int,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    log = db.query(BotLog).filter(BotLog.id == log_id, BotLog.client_id == current_client.id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    db.delete(log)
    db.commit()