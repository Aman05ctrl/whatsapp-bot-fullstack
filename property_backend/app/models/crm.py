from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from property_backend.app.database import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    name = Column(String(255), nullable=True)
    country_code = Column(String(10), nullable=True)
    phone = Column(String(50), nullable=True, index=True)
    interest = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    raw_id = Column(String(255), nullable=True)
    lead_score = Column(Integer, default=0)
    lead_status = Column(String(50), default='active')
    follow_up_due = Column(String(100), nullable=True)
    lead_summary = Column(Text, nullable=True)
    budget_category = Column(String(100), nullable=True)
    agent_handover = Column(String(50), default='No')
    conversation_status = Column(String(50), nullable=True)
    user_fingerprint = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    client = relationship("Client", backref="leads")


class BotLog(Base):
    __tablename__ = "bot_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_name = Column(String(255), nullable=True)
    country_code = Column(String(10), nullable=True)
    phone = Column(String(50), nullable=True, index=True)
    user_message = Column(Text, nullable=True)
    reply_type = Column(String(50), nullable=True)
    bot_response = Column(Text, nullable=True)

    client = relationship("Client", backref="bot_logs")