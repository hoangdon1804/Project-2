import requests
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import linemerge, polygonize, unary_union

def fetch_wards_from_osm(district_name: str):
    # Sử dụng server chính thống của OSM để ổn định hơn
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # Query linh hoạt hơn: Tìm bất kỳ khu vực nào có tên khớp và lấy admin_level=8 bên trong
    query = f"""
    [out:json][timeout:60];
    (
      area["name"="{district_name}"];
      area["name"~"{district_name}"];
    )->.a;
    (
      relation["admin_level"="8"](area.a);
    );
    out body;
    >;
    out skel qt;
    """
    
    headers = {'User-Agent': 'TerritorySystem/1.0'}
    try:
        response = requests.get(overpass_url, params={'data': query}, headers=headers, timeout=60)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"OSM Connection Error: {e}")
        return None

def osm_to_geojson(osm_data):
    if not osm_data: return []
    elements = osm_data.get("elements", [])
    
    # 1. Tạo bản đồ tra cứu tọa độ từ các node
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in elements if e["type"] == "node"}
    
    # 2. Tạo bản đồ tra cứu tọa độ của các way
    ways = {}
    for e in elements:
        if e["type"] == "way":
            coords = [nodes[nid] for nid in e.get("nodes", []) if nid in nodes]
            if len(coords) >= 2:
                ways[e["id"]] = coords
    
    wards = []
    # 3. Xử lý từng relation (đại diện cho 1 phường)
    for rel in [e for e in elements if e["type"] == "relation"]:
        ward_name = rel.get("tags", {}).get("name", "Không tên")
        
        # Lấy tất cả các way có role là "outer"
        outer_way_ids = [m["ref"] for m in rel.get("members", []) 
                         if m["type"] == "way" and m["role"] == "outer"]
        
        # Chuyển các way id thành danh sách các LineString của Shapely
        lines = []
        for wid in outer_way_ids:
            if wid in ways:
                lines.append(LineString(ways[wid]))
        
        if not lines: continue

        try:
            # Dùng linemerge để nối các đoạn rời rạc thành các đường dài hơn
            merged = linemerge(lines)
            
            # Tạo đa giác từ các đường đã nối (polygonize)
            # Dùng unary_union để làm sạch các điểm thừa hoặc lỗi tự giao nhau
            polygons = list(polygonize(merged))
            
            if not polygons:
                # Nếu không tạo được polygon, thử hợp nhất các đường rồi lấy ranh giới
                combined = unary_union(merged)
                if isinstance(combined, Polygon):
                    polygons = [combined]
                elif hasattr(combined, 'geoms'): # Nếu là MultiPolygon
                    polygons = list(combined.geoms)

            for poly in polygons:
                # Chuyển đổi từ Shapely sang GeoJSON coordinates
                # poly.exterior.coords trả về list (lon, lat)
                final_coords = [list(c) for c in poly.exterior.coords]
                
                wards.append({
                    "name": ward_name,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [final_coords]
                    },
                    "center": [poly.centroid.x, poly.centroid.y]
                })
        except Exception as e:
            print(f"⚠️ Lỗi xử lý hình học cho phường {ward_name}: {e}")

    return wards