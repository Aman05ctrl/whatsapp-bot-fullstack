from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LeadCreate(BaseModel):
    name: Optional[str] = None
    country_code: Optional[str] = None
    phone: Optional[str] = None
    interest: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    raw_id: Optional[str] = None
    lead_score: Optional[int] = 0
    lead_status: Optional[str] = 'active'
    follow_up_due: Optional[str] = None
    lead_summary: Optional[str] = None
    budget_category: Optional[str] = None
    agent_handover: Optional[str] = 'No'
    conversation_status: Optional[str] = None
    user_fingerprint: Optional[str] = None
    notes: Optional[str] = None

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    country_code: Optional[str] = None
    phone: Optional[str] = None
    interest: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    lead_score: Optional[int] = None
    lead_status: Optional[str] = None
    follow_up_due: Optional[str] = None
    lead_summary: Optional[str] = None
    budget_category: Optional[str] = None
    agent_handover: Optional[str] = None
    conversation_status: Optional[str] = None
    user_fingerprint: Optional[str] = None
    notes: Optional[str] = None

class LeadResponse(BaseModel):
    id: int
    client_id: int
    created_at: datetime
    last_updated: datetime
    name: Optional[str]
    country_code: Optional[str]
    phone: Optional[str]
    interest: Optional[str]
    email: Optional[str]
    city: Optional[str]
    raw_id: Optional[str]
    lead_score: int
    lead_status: str
    follow_up_due: Optional[str]
    lead_summary: Optional[str]
    budget_category: Optional[str]
    agent_handover: str
    conversation_status: Optional[str]
    user_fingerprint: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True

class BotLogCreate(BaseModel):
    user_name: Optional[str] = None
    country_code: Optional[str] = None
    phone: Optional[str] = None
    user_message: Optional[str] = None
    reply_type: Optional[str] = None
    bot_response: Optional[str] = None

class BotLogResponse(BaseModel):
    id: int
    client_id: int
    timestamp: datetime
    user_name: Optional[str]
    country_code: Optional[str]
    phone: Optional[str]
    user_message: Optional[str]
    reply_type: Optional[str]
    bot_response: Optional[str]

    class Config:
        from_attributes = True