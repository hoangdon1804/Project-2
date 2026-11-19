import json
import re
import time
import unicodedata
import logging
from threading import Lock

import requests
from shapely.geometry import LineString, mapping, shape
from shapely.ops import polygonize_full, unary_union
from shapely.errors import GEOSException

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
HISTORICAL_DATE = "2025-06-01T00:00:00Z"
_CACHE = {}
_CACHE_LOCK = Lock()


class WardImportError(Exception):
    """An actionable import failure; never silently import partial responses."""


def normalize_name(value):
    value = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[.,]", " ", value)).strip()


def _city_code(region_name):
    name = normalize_name(region_name)
    name = re.sub(r"^(thanh pho|tp)\s*", "", name)
    aliases = {"ha noi": "VN-HN", "hanoi": "VN-HN", "hn": "VN-HN",
               "ho chi minh": "VN-SG", "hcm": "VN-SG", "tphcm": "VN-SG",
               "sai gon": "VN-SG", "saigon": "VN-SG"}
    if name not in aliases:
        raise WardImportError("Phân vùng phải thuộc khu vực Hà Nội hoặc TP. Hồ Chí Minh.")
    return aliases[name]


def _query(query):
    errors = []
    for url in OVERPASS_URLS:
        try:
            response = requests.post(url, data={"data": query},
                                     headers={"User-Agent": "TerritorySystem/1.0"},
                                     timeout=(10, 150))
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("remark") or not isinstance(data.get("elements"), list):
                raise ValueError("Incomplete Overpass response")
            return data
        except (requests.RequestException, ValueError) as exc:
            errors.append(str(exc))
    logging.getLogger(__name__).warning("Overpass endpoints failed: %s", errors)
    raise WardImportError("Dịch vụ bản đồ đang quá tải hoặc trả dữ liệu thiếu. Vui lòng thử lại sau.")


def _catalog(city_code, historical=False):
    # Areas are current in Overpass even for attic queries. This intentionally
    # scopes historical districts to the city's current extent (including HCM expansion).
    key = (city_code, historical)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and time.monotonic() - cached[0] < 900:
            return cached[1]
    date = f'[date:"{HISTORICAL_DATE}"]' if historical else ""
    query = (f'[out:json][timeout:120]{date};'
             f'area["ISO3166-2"={json.dumps(city_code)}]["admin_level"="4"]->.city;'
             '(relation(pivot.city);'
             'relation["boundary"="administrative"]["admin_level"~"^(6|8)$"](area.city););out geom;')
    data = _query(query)
    if historical:
        data["city_geometry"] = _catalog(city_code)["city_geometry"]
    else:
        parents = [e for e in data["elements"] if e.get("tags", {}).get("ISO3166-2") == city_code]
        boundary = osm_to_geojson({"elements": parents})
        if len(boundary) != 1:
            raise WardImportError("Không xác định được ranh giới thành phố trên OSM.")
        data["city_geometry"] = boundary[0]["geometry"]
    data["elements"] = [e for e in data["elements"] if e.get("tags", {}).get("admin_level") in ("6", "8")]
    if not data["elements"]:
        raise WardImportError("Nguồn OSM chưa có ranh giới cho khu vực này. Không có dữ liệu nào được lưu.")
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic(), data)
    return data


def _bare_name(name):
    return re.sub(r"^(quan|huyen|thi xa|thanh pho|phuong|xa|thi tran|dac khu)\s+", "", normalize_name(name))


def _matches(element, name):
    tags = element.get("tags", {})
    names = [n for key in ("name", "name:vi", "name:en", "alt_name", "short_name", "official_name")
             for n in tags.get(key, "").split(";") if n]
    normalized = normalize_name(name)
    if re.match(r"^(quan|huyen|thi xa|thanh pho|phuong|xa|thi tran|dac khu)\s", normalized):
        return any(normalize_name(n) == normalized for n in names)
    return any(_bare_name(n) == _bare_name(name) for n in names)


def _in_city(element, catalog):
    # Overpass area queries include neighbours touching the city's border.
    polygon = shape(osm_to_geojson({"elements": [element]})[0]["geometry"])
    return shape(catalog["city_geometry"]).covers(polygon.representative_point())


def fetch_wards_from_osm(district_name: str, region_name: str):
    if not isinstance(district_name, str) or not district_name.strip():
        raise WardImportError("Vui lòng nhập tên phường/xã hoặc quận/huyện.")
    city_code = _city_code(region_name)
    name = normalize_name(district_name)
    historical = bool(re.match(r"^(quan|huyen|thi xa|thanh pho)\s", name))
    current = None if historical else _catalog(city_code)
    matches = [] if current is None else [e for e in current["elements"] if _matches(e, name) and _in_city(e, current)]
    if not matches:
        old = _catalog(city_code, historical=True)
        districts = [e for e in old["elements"] if e.get("tags", {}).get("admin_level") == "6" and _matches(e, name) and _in_city(e, old)]
        if len(districts) != 1:
            raise WardImportError("Không xác định được địa danh duy nhất trong thành phố đã chọn. Hãy nhập đầy đủ tên phường/xã hoặc quận/huyện.")
        district = osm_to_geojson({"elements": districts})
        if not district:
            raise WardImportError("Ranh giới quận/huyện trên OSM chưa đầy đủ.")
        boundary = shape(district[0]["geometry"])
        candidates = [e for e in old["elements"] if e.get("tags", {}).get("admin_level") == "8"]
        # Use polygon coverage rather than OSM area membership (which also selects
        # neighbours sharing a boundary node). Never clip or manufacture boundaries.
        matches = []
        for element in candidates:
            # Far-away incomplete geometries should not block this district.
            bounds = element.get("bounds")
            if bounds:
                minx, miny, maxx, maxy = boundary.bounds
                if bounds["maxlon"] < minx or bounds["minlon"] > maxx or bounds["maxlat"] < miny or bounds["minlat"] > maxy:
                    continue
            ward = osm_to_geojson({"elements": [element]})
            if ward:
                polygon = shape(ward[0]["geometry"])
                if boundary.intersection(polygon).area / polygon.area > 0.5:
                    matches.append(element)
        historical = True
    elif len(matches) > 1:
        raise WardImportError("Tên địa danh bị trùng. Vui lòng nhập đầy đủ tên đơn vị hành chính.")
    return {"elements": matches, "snapshot": HISTORICAL_DATE if historical else None}


def osm_to_geojson(osm_data):
    if not osm_data:
        return []
    elements = osm_data.get("elements", [])
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in elements if e["type"] == "node"}
    ways = {e["id"]: [nodes[n] for n in e.get("nodes", []) if n in nodes]
            for e in elements if e["type"] == "way" and all(n in nodes for n in e.get("nodes", []))}
    wards = []
    seen = set()
    for rel in elements:
        if rel["type"] != "relation" or rel["id"] in seen:
            continue
        seen.add(rel["id"])
        tags = rel.get("tags", {})
        if tags.get("boundary") != "administrative":
            continue
        name = tags.get("name:vi") or tags.get("name")
        if not name:
            raise WardImportError("OSM có đơn vị hành chính thiếu tên.")
        rings = {"outer": [], "inner": []}
        try:
            for member in rel.get("members", []):
                role = member.get("role") or "outer"
                if role not in rings:
                    continue
                if member["type"] != "way":
                    raise ValueError("Unsupported nested boundary")
                geometry = member.get("geometry")
                coords = [(p["lon"], p["lat"]) for p in geometry] if geometry else ways.get(member["ref"], [])
                if len(coords) < 2:
                    raise ValueError("Missing boundary way")
                rings[role].append(LineString(coords))
            polygons = {}
            for role, lines in rings.items():
                polygons[role], cuts, dangles, invalid = polygonize_full(lines)
                if any(not g.is_empty for g in (cuts, dangles, invalid)):
                    raise ValueError("Unclosed boundary")
            polygon = unary_union(polygons["outer"])
            if not polygons["inner"].is_empty:
                polygon = polygon.difference(unary_union(polygons["inner"]))
            if polygon.is_empty or not polygon.is_valid or polygon.geom_type not in ("Polygon", "MultiPolygon"):
                raise ValueError("Invalid boundary")
            center = polygon.representative_point()
            wards.append({"osm_id": rel["id"], "name": name,
                          "geometry": mapping(polygon), "center": [center.x, center.y]})
        except (ValueError, KeyError, TypeError, GEOSException) as exc:
            raise WardImportError(f"Ranh giới {name} trên OSM chưa đầy đủ hoặc không hợp lệ. Chưa lưu dữ liệu.") from exc
    return wards
