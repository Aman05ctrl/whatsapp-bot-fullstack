import psycopg2

conn = psycopg2.connect('postgresql://postgres:Kqrt4pi2d8%40@127.0.0.1:5432/real_estate_db')
cur = conn.cursor()

# Clients table columns
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='clients' ORDER BY ordinal_position")
print("CLIENTS TABLE:")
for r in cur.fetchall():
    print(f"  - {r[0]} ({r[1]})")

# Properties table columns
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='properties' ORDER BY ordinal_position")
print("\nPROPERTIES TABLE:")
for r in cur.fetchall():
    print(f"  - {r[0]} ({r[1]})")

conn.close()