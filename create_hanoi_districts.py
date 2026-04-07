import requests

API_BASE = "http://localhost:8000"

# List of Hanoi districts to create
HANOI_DISTRICTS = [
    {"code": "HB", "name": "Quận Hoàn Bà Đình", "center_lat": 21.0285, "center_lng": 105.8581},
    {"code": "TCH", "name": "Quận Thanh Chương", "center_lat": 21.0045, "center_lng": 105.8645},
    {"code": "DC", "name": "Quận Đống Đa", "center_lat": 21.0262, "center_lng": 105.8449},
    {"code": "HAD", "name": "Quận Hai Bà Trưng", "center_lat": 20.9992, "center_lng": 105.8527},
    {"code": "HA", "name": "Quận Hoàn Kiếm", "center_lat": 21.0285, "center_lng": 105.8493},
    {"code": "CGV", "name": "Quận Cầu Giấy", "center_lat": 21.0410, "center_lng": 105.7880},
    {"code": "BTL", "name": "Quận Bắc Từ Liêm", "center_lat": 21.0887, "center_lng": 105.7704},
    {"code": "TL", "name": "Quận Tây Hồ", "center_lat": 21.0901, "center_lng": 105.8243},
]

print("🔍 Creating Hanoi districts...\n")

for district in HANOI_DISTRICTS:
    try:
        res = requests.post(
            f"{API_BASE}/districts",
            json=district,
            headers={"Authorization": f"Bearer YOUR_ADMIN_TOKEN"}  # If auth is required
        )
        if res.status_code in [200, 201]:
            print(f"✅ Created: {district['name']} (Code: {district['code']})")
        else:
            print(f"⚠️  {district['name']}: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Error creating {district['name']}: {e}")

print("\n✅ Districts creation complete!")
