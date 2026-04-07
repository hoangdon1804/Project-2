import osmnx as ox
import requests
import random
from shapely.geometry import mapping

API_BASE = "http://localhost:8000"

def get_district_id_by_code(district_code):
    try:
        res = requests.get(f"{API_BASE}/districts")
        if res.status_code == 200:
            for d in res.json():
                if d['code'] == district_code:
                    return d['id']
    except Exception as e:
        print(f"❌ Lỗi kết nối Backend: {e}")
    return None

def import_zones_with_osmnx(district_code, place_name):
    district_id = get_district_id_by_code(district_code)
    if not district_id:
        print(f"❌ Không tìm thấy District ID cho mã: {district_code}. Vui lòng tạo District trước.")
        return

    print(f"⏳ Đang tải dữ liệu từ OpenStreetMap cho: {place_name}...")
    
    # 1. Lấy dữ liệu bằng OSMnx
    tags = {"boundary": "administrative", "admin_level": "8"}
    gdf = ox.features_from_place(place_name, tags)
    
    # Lọc chỉ lấy Polygon và MultiPolygon
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]

    success_count = 0
    for _, row in gdf.iterrows():
        ward_name = row.get('name', 'Không tên')
        
        # 2. Xử lý Geometry sang định dạng GeoJSON mà Leaflet hiểu được
        # mapping(row.geometry) chuyển đổi shapely object sang dict GeoJSON
        geojson_geometry = mapping(row.geometry)
        
        # 3. Tính toán tâm (Centroid) để hiển thị Marker hoặc tính khoảng cách
        centroid = row.geometry.centroid
        lat, lng = centroid.y, centroid.x

        # 4. Chuẩn bị Payload cho API
        payload = {
            "zone_code": f"W-{random.randint(10000, 99999)}",
            "district_id": district_id,
            "name": ward_name,
            "geometry": geojson_geometry, 
            "center_lat": lat,
            "center_lng": lng,
            "num_customers": random.randint(100, 1000),
            "num_orders": random.randint(200, 2000),
            "revenue": random.randint(50, 500) * 1000000
        }

        # 5. Gửi dữ liệu lên Backend
        try:
            res = requests.post(f"{API_BASE}/zones", json=payload)
            if res.status_code == 200:
                print(f" ✅ Đã import: {ward_name}")
                success_count += 1
            else:
                print(f" ❌ Lỗi khi lưu {ward_name}: {res.text}")
        except Exception as e:
            print(f" ❌ Lỗi kết nối khi xử lý {ward_name}: {e}")

    print(f"\n🎉 HOÀN TẤT! Đã import {success_count} phường vào hệ thống.")

if __name__ == "__main__":
    # Đảm bảo bạn đã tạo District "BD" trong Admin Dashboard trước khi chạy
    import_zones_with_osmnx("BD", "Quận Ba Đình, Hà Nội, Vietnam")