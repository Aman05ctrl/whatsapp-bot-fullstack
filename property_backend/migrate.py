import sys
sys.path.insert(0, 'D:\\WhatsApp Bot')

from property_backend.app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Leads table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            name VARCHAR(255),
            country_code VARCHAR(10),
            phone VARCHAR(50),
            interest TEXT,
            email VARCHAR(255),
            city VARCHAR(100),
            raw_id VARCHAR(255),
            lead_score INTEGER DEFAULT 0,
            lead_status VARCHAR(50) DEFAULT 'active',
            follow_up_due VARCHAR(100),
            lead_summary TEXT,
            budget_category VARCHAR(100),
            agent_handover VARCHAR(50) DEFAULT 'No',
            conversation_status VARCHAR(50),
            user_fingerprint VARCHAR(255),
            notes TEXT
        )
    """))

    # Logs table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_logs (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            user_name VARCHAR(255),
            country_code VARCHAR(10),
            phone VARCHAR(50),
            user_message TEXT,
            reply_type VARCHAR(50),
            bot_response TEXT
        )
    """))

    conn.commit()
    print('✅ Leads and Logs tables created!')