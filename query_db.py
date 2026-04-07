import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import SessionLocal
from models import District, Zone

db = SessionLocal()

districts = db.query(District).all()
print(f"Total Districts: {len(districts)}")
for d in districts:
    print(f"  - ID: {d.id}, Code: {d.code}, Name: {d.name}")

zones = db.query(Zone).all()
print(f"\nTotal Zones: {len(zones)}")
for z in zones:
    has_geom = "✅" if z.geometry else "❌"
    print(f"  - ID: {z.id}, Name: {z.name}, district_id: {z.district_id}, Geom: {has_geom}")

db.close()
