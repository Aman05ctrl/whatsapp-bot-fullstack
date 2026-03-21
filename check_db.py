import psycopg2

try:
    conn = psycopg2.connect('postgresql://postgres:Kqrt4pi2d8%40@127.0.0.1:5432/real_estate_db')
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = cur.fetchall()
    print("✅ Connected to database!")
    print("\nTables found:")
    for t in tables:
        print(f"  - {t[0]}")
    
    # Check leads table
    try:
        cur.execute("SELECT COUNT(*) FROM leads")
        count = cur.fetchone()[0]
        print(f"\nLeads in database: {count}")
        
        if count > 0:
            cur.execute("SELECT id, name, phone, city, email, created_at FROM leads LIMIT 5")
            rows = cur.fetchall()
            print("\nFirst 5 leads:")
            for row in rows:
                print(f"  {row}")
    except Exception as e:
        print(f"\nNo leads table or error: {e}")
    
    conn.close()

except Exception as e:
    print(f"❌ Connection failed: {e}")
