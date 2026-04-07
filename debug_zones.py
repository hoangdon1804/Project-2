import sys
import os
import requests
import json

# Add backend to path for runtime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# For Pylance: use proper imports
if os.path.exists(os.path.join(os.path.dirname(__file__), 'backend')):
    from database import SessionLocal  # type: ignore
    from models import Zone, District  # type: ignore
else:
    # Fallback for different execution contexts
    from backend.database import SessionLocal
    from backend.models import Zone, District

# Get zones from API
print("=" * 60)
print("ZONES FROM API")
print("=" * 60)

API_BASE = "http://localhost:8000"

try:
    res = requests.get(f"{API_BASE}/zones")
    if res.status_code == 200:
        zones = res.json()
        print(f"Total zones from API: {len(zones)}")
        for zone in zones:
            print(f"\n📍 Zone: {zone.get('name')} (ID: {zone.get('id')})")
            print(f"   Code: {zone.get('zone_code')}")
            print(f"   Center: ({zone.get('center_lat')}, {zone.get('center_lng')})")
            geometry = zone.get('geometry')
            if geometry:
                print(f"   ✅ Geometry Type: {geometry.get('type')}")
                if geometry.get('type') == 'Polygon':
                    coords = geometry.get('coordinates', [])
                    print(f"      Polygon Coords Count: {len(coords[0]) if coords else 0}")
                elif geometry.get('type') == 'MultiPolygon':
                    coords = geometry.get('coordinates', [])
                    print(f"      MultiPolygon Parts: {len(coords)}")
            else:
                print("   ❌ NO GEOMETRY!")
    else:
        print(f"Error: {res.status_code} - {res.text}")
except Exception as e:
    print(f"Error connecting to API: {e}")

# Check database directly
print("\n" + "=" * 60)
print("ALL DISTRICTS IN DATABASE")
print("=" * 60)

db = SessionLocal()
try:
    districts = db.query(District).all()
    print(f"\nTotal districts: {len(districts)}")
    for district in districts:
        print(f"  - ID: {district.id}, Code: {district.code}, Name: {district.name}")
except Exception as e:
    print(f"Database error: {e}")
finally:
    db.close()

# Check first district
print("\n" + "=" * 60)
print("ZONES IN DATABASE (first district)")
print("=" * 60)

db = SessionLocal()
try:
    district = db.query(District).first()
    if district:
        zones = db.query(Zone).filter(Zone.district_id == district.id).all()
        print(f"\nDistrict: {district.name} (Code: {district.code}, ID: {district.id})")
        print(f"Zones count: {len(zones)}")
        for zone in zones:
            print(f"\n📍 Zone: {zone.name} (ID: {zone.id})")
            print(f"   Code: {zone.zone_code}")
            print(f"   Center: ({zone.center_lat}, {zone.center_lng})")
            if zone.geometry:
                print(f"   ✅ Geometry Type: {zone.geometry.get('type')}")
                print(f"   Geometry Size: {len(json.dumps(zone.geometry))} bytes")
                if zone.geometry.get('type') == 'Polygon':
                    coords = zone.geometry.get('coordinates', [])
                    print(f"      Polygon Coordinates Count: {len(coords[0]) if coords else 0}")
                elif zone.geometry.get('type') == 'MultiPolygon':
                    coords = zone.geometry.get('coordinates', [])
                    print(f"      MultiPolygon Parts: {len(coords)}")
            else:
                print("   ❌ NO GEOMETRY IN DATABASE!")
    else:
        print("No districts found")
except Exception as e:
    print(f"Database error: {e}")
finally:
    db.close()
