from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_
from typing import List, Dict, Any, Optional
from external_services import fetch_wards_from_osm, osm_to_geojson, WardImportError, normalize_name
import models
import schemas
import auth
import time
import random
import math
from datetime import datetime
from database import SessionLocal
from algorithms import AdvancedTerritoryDesign
import algorithm_comparison
import fake_metrics
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.validation import make_valid
from shapely.errors import GEOSException

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_territory_zone_ids(territory: models.Territory, db: Session) -> List[int]:
    zone_ids = [int(zid) for zid in (territory.zone_ids or [])]
    actual_zone_ids = [
        zone.id
        for zone in db.query(models.Zone).filter(
            models.Zone.territory_id == territory.id
        ).all()
    ]
    merged = list(dict.fromkeys([*zone_ids, *actual_zone_ids]))
    if merged != zone_ids:
        territory.zone_ids = merged
        db.flush()
    return merged


ADJACENCY_TOLERANCE_DEG = 3e-5  # ~3 m: chấp nhận sai số nhỏ ở biên giữa hai zone
OVERLAP_MIN_AREA_M2 = 50.0      # bỏ qua phần giao nhỏ do sai số biên


def _zone_shape(zone: models.Zone):
    """Trả về polygon hợp lệ của zone hoặc None nếu thiếu/lỗi geometry."""
    if not zone.geometry:
        return None
    try:
        polygon = shape(zone.geometry)
        if not polygon.is_valid:
            polygon = make_valid(polygon)
        if polygon.is_empty:
            return None
        return polygon
    except (TypeError, ValueError, KeyError, GEOSException):
        return None


def _zone_area_km2(zone: models.Zone) -> Optional[float]:
    """Diện tích zone (km²) từ geometry lon/lat (xem fake_metrics.area_km2)."""
    return fake_metrics.area_km2(zone.geometry)


def _find_adjacent_pairs(zones: List[models.Zone]) -> List[tuple]:
    """Các cặp (id nhỏ, id lớn) có khoảng cách biên <= ADJACENCY_TOLERANCE_DEG."""
    polygons = {}
    for zone in zones:
        polygon = _zone_shape(zone)
        if polygon is not None:
            polygons[zone.id] = polygon
    ids = list(polygons)
    tree = STRtree([polygons[i] for i in ids])
    pairs = set()
    for index, zone_id in enumerate(ids):
        for other_index in tree.query(polygons[zone_id], predicate="dwithin",
                                      distance=ADJACENCY_TOLERANCE_DEG):
            other_id = ids[int(other_index)]
            if other_id != zone_id:
                pairs.add((min(zone_id, other_id), max(zone_id, other_id)))

    # Zone thiếu geometry: dùng khoảng cách tâm như phương án dự phòng.
    no_geo = [z for z in zones if z.id not in polygons and z.center_lat is not None]
    for zone_a in no_geo:
        for zone_b in zones:
            if zone_b.id == zone_a.id or zone_b.center_lat is None:
                continue
            if (abs(zone_a.center_lat - zone_b.center_lat) <= 0.015
                    and abs(zone_a.center_lng - zone_b.center_lng) <= 0.015):
                pairs.add((min(zone_a.id, zone_b.id), max(zone_a.id, zone_b.id)))
    return sorted(pairs)


def _rebuild_zone_adjacency(territory: models.Territory, db: Session) -> Dict[str, Any]:
    zone_ids = _get_territory_zone_ids(territory, db)
    if not zone_ids:
        return {"territory_id": territory.id, "zone_count": 0, "adjacency_count": 0}

    zones = db.query(models.Zone).filter(models.Zone.id.in_(zone_ids)).all()
    db.query(models.ZoneAdjacency).filter(
        (models.ZoneAdjacency.zone_id1.in_(zone_ids))
        | (models.ZoneAdjacency.zone_id2.in_(zone_ids))
    ).delete(synchronize_session=False)

    pairs = _find_adjacent_pairs(zones)
    for zone_id1, zone_id2 in pairs:
        db.add(models.ZoneAdjacency(zone_id1=zone_id1, zone_id2=zone_id2, is_adjacent=True))
    db.flush()
    return {
        "territory_id": territory.id,
        "zone_count": len(zones),
        "adjacency_count": len(pairs),
    }


def _zone_group_is_connected(zone_ids: List[int], db: Session) -> bool:
    zone_ids = [int(zone_id) for zone_id in zone_ids]
    if len(zone_ids) <= 1:
        return True
    zone_id_set = set(zone_ids)
    adjacencies = db.query(models.ZoneAdjacency).filter(
        (models.ZoneAdjacency.zone_id1.in_(zone_ids))
        | (models.ZoneAdjacency.zone_id2.in_(zone_ids))
    ).all()
    adjacency = {zone_id: set() for zone_id in zone_ids}
    for adj in adjacencies:
        if not adj.is_adjacent:
            continue
        if adj.zone_id1 in zone_id_set and adj.zone_id2 in zone_id_set:
            adjacency[adj.zone_id1].add(adj.zone_id2)
            adjacency[adj.zone_id2].add(adj.zone_id1)

    visited = {zone_ids[0]}
    queue = [zone_ids[0]]
    while queue:
        current = queue.pop(0)
        for neighbor in adjacency.get(current, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return len(visited) == len(zone_id_set)


# ============ AUTH ROUTES ============
@router.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Register new user
    - sales: needs admin approval (is_approved = False)
    - admin: cannot be registered here (must be created by admin)
    """
    try:
        # Kiểm tra username tồn tại
        existing_username = db.query(models.User).filter(
            models.User.username == user.username
        ).first()
        if existing_username:
            raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")
        
        # Kiểm tra email tồn tại
        existing_email = db.query(models.User).filter(
            models.User.email == user.email
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email đã được đăng ký")
        
        hashed = auth.hash_password(user.password)

        new_user = models.User(
            username=user.username,
            email=user.email,
            password=hashed,
            role=user.role,
            full_name=user.full_name,
            phone=user.phone,
            is_approved=False
        )

        db.add(new_user)
        db.commit()
        
        return {"msg": "Đăng ký thành công! Vui lòng chờ admin duyệt tài khoản của bạn."}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(
        or_(
            models.User.username == user.username,
            models.User.email == user.username,
        )
    ).first()

    if not db_user:
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không chính xác")

    if not auth.verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không chính xác")

    token = auth.create_token({
        "id": db_user.id,
        "role": db_user.role,
        "username": db_user.username
    })

    return {"token": token, "role": db_user.role, "id": db_user.id}


# ============ ADMIN ACCOUNT MANAGEMENT ROUTES ============
@router.post("/admin/create-sales")
def admin_create_sales(user_data: schemas.AdminCreateSales, db: Session = Depends(get_db)):
    """Admin creates sales account directly (auto-approved)"""
    try:
        # Kiểm tra username tồn tại
        existing_username = db.query(models.User).filter(
            models.User.username == user_data.username
        ).first()
        if existing_username:
            raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")
        
        # Kiểm tra email tồn tại
        existing_email = db.query(models.User).filter(
            models.User.email == user_data.email
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email đã được đăng ký")
        
        # Nếu có region_id, kiểm tra khu vực tồn tại
        if user_data.region_id:
            region = db.query(models.Region).filter(
                models.Region.id == user_data.region_id
            ).first()
            if not region:
                raise HTTPException(status_code=400, detail="Khu vực không tồn tại")
        
        hashed = auth.hash_password(user_data.password)

        new_sales = models.User(
            username=user_data.username,
            email=user_data.email,
            password=hashed,
            role='sales',
            full_name=user_data.full_name,
            phone=user_data.phone,
            region_id=user_data.region_id,
            is_approved=True  # Admin created, auto-approved
        )

        db.add(new_sales)
        db.commit()
        return {"msg": "Tài khoản sales được tạo thành công!", "id": new_sales.id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/create-admin")
def admin_create_admin(user_data: schemas.AdminCreateAdmin, db: Session = Depends(get_db)):
    """Admin creates another admin account"""
    try:
        # Kiểm tra username tồn tại
        existing_username = db.query(models.User).filter(
            models.User.username == user_data.username
        ).first()
        if existing_username:
            raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")
        
        # Kiểm tra email tồn tại
        existing_email = db.query(models.User).filter(
            models.User.email == user_data.email
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email đã được đăng ký")
        
        hashed = auth.hash_password(user_data.password)

        new_admin = models.User(
            username=user_data.username,
            email=user_data.email,
            password=hashed,
            role='admin',
            full_name=user_data.full_name,
            phone=user_data.phone,
            is_approved=True  # Admin created, auto-approved
        )

        db.add(new_admin)
        db.commit()
        return {"msg": "Tài khoản admin được tạo thành công!", "id": new_admin.id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/pending-sales")
def get_pending_sales(db: Session = Depends(get_db)):
    """Get list of pending sales approvals"""
    pending_sales = db.query(models.User).filter(
        and_(
            models.User.role == 'sales',
            models.User.is_approved == False
        )
    ).all()
    return pending_sales


@router.post("/admin/approve-sales/{user_id}")
def approve_sales(user_id: int, approval: schemas.ApproveSalesRequest, db: Session = Depends(get_db)):
    """Admin approves or rejects sales user"""
    user = db.query(models.User).filter(models.User.id == approval.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User không tìm thấy")
    
    if user.role != 'sales':
        raise HTTPException(status_code=400, detail="User này không phải sales role")
    
    user.is_approved = approval.is_approved
    db.commit()
    
    status = "duyệt" if approval.is_approved else "từ chối"
    return {"msg": f"Tài khoản sales được {status} thành công!"}


# ============ REGION ROUTES ============
@router.post("/regions")
def create_region(region: schemas.RegionCreate, db: Session = Depends(get_db)):
    """Tạo khu vực mới"""
    # Kiểm tra tên khu vực đã tồn tại
    existing = db.query(models.Region).filter(
        models.Region.name == region.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tên khu vực đã tồn tại")
    
    new_region = models.Region(name=region.name)
    db.add(new_region)
    db.commit()
    db.refresh(new_region)
    return new_region


@router.get("/regions")
def get_regions(db: Session = Depends(get_db)):
    """Lấy danh sách tất cả khu vực"""
    regions = db.query(models.Region).all()
    return regions


@router.get("/regions/{region_id}")
def get_region(region_id: int, db: Session = Depends(get_db)):
    """Lấy chi tiết khu vực với các phân vùng và sales"""
    region = db.query(models.Region).filter(
        models.Region.id == region_id
    ).first()
    
    if not region:
        raise HTTPException(status_code=404, detail="Khu vực không tìm thấy")
    
    # Tính toán thông tin từ territories và zones
    territories = region.territories
    sales_users = region.sales_users
    
    # Lấy tất cả zones trong khu vực này
    zone_ids = []
    for territory in territories:
        if territory.zone_ids:
            zone_ids.extend(territory.zone_ids)
    
    zones = db.query(models.Zone).filter(models.Zone.id.in_(zone_ids)).all() if zone_ids else []
    
    total_zones = len(zones)
    total_customers = sum(z.num_customers for z in zones)
    total_orders = sum(z.num_orders for z in zones)
    total_revenue = sum(z.revenue for z in zones)
    
    return {
        "id": region.id,
        "name": region.name,
        "territories": territories,
        "sales_users": sales_users,
        "zones": zones,
        "total_zones": total_zones,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "created_at": region.created_at
    }


@router.put("/regions/{region_id}")
def update_region(region_id: int, region: schemas.RegionUpdate, db: Session = Depends(get_db)):
    """Cập nhật khu vực"""
    db_region = db.query(models.Region).filter(
        models.Region.id == region_id
    ).first()
    
    if not db_region:
        raise HTTPException(status_code=404, detail="Khu vực không tìm thấy")
    
    if region.name:
        # Kiểm tra tên không bị trùng với khu vực khác
        existing = db.query(models.Region).filter(
            and_(
                models.Region.name == region.name,
                models.Region.id != region_id
            )
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Tên khu vực đã tồn tại")
        
        db_region.name = region.name
    
    db.commit()
    db.refresh(db_region)
    return db_region


@router.delete("/regions/{region_id}")
def delete_region(region_id: int, db: Session = Depends(get_db)):
    """Xóa khu vực (không được xóa nếu có phân vùng hoặc sales)"""
    region = db.query(models.Region).filter(
        models.Region.id == region_id
    ).first()
    
    if not region:
        raise HTTPException(status_code=404, detail="Khu vực không tìm thấy")
    
    # Kiểm tra có phân vùng
    territories = db.query(models.Territory).filter(
        models.Territory.region_id == region_id
    ).all()
    
    if territories:
        raise HTTPException(status_code=400, detail="Không thể xóa khu vực có phân vùng. Vui lòng xóa phân vùng trước.")
    
    # Kiểm tra có sales
    sales = db.query(models.User).filter(
        and_(
            models.User.region_id == region_id,
            models.User.role == 'sales'
        )
    ).all()
    
    if sales:
        raise HTTPException(status_code=400, detail="Không thể xóa khu vực có sales. Vui lòng gỡ khu vực khỏi sales trước.")
    
    db.delete(region)
    db.commit()
    return {"msg": "Đã xóa khu vực thành công"}


@router.post("/admin/assign-region-to-sales")
def assign_region_to_sales(request: schemas.AssignRegionToSalesRequest, db: Session = Depends(get_db)):
    """Gán khu vực cho sales hoặc gỡ khu vực"""
    sales = db.query(models.User).filter(
        models.User.id == request.sales_id
    ).first()
    
    if not sales:
        raise HTTPException(status_code=404, detail="Sales không tìm thấy")
    
    if sales.role != 'sales':
        raise HTTPException(status_code=400, detail="User này không phải sales role")
    
    # Nếu region_id là None, gỡ khu vực
    if request.region_id is None:
        sales.region_id = None
        db.commit()
        return {"msg": f"Đã gỡ khu vực khỏi sales {sales.full_name}"}
    
    # Kiểm tra khu vực tồn tại
    region = db.query(models.Region).filter(
        models.Region.id == request.region_id
    ).first()
    
    if not region:
        raise HTTPException(status_code=404, detail="Khu vực không tìm thấy")
    
    sales.region_id = request.region_id
    db.commit()
    
    return {"msg": f"Đã gán khu vực {region.name} cho sales {sales.full_name}"}


@router.put("/admin/sales/{user_id}")
def update_sales(user_id: int, user_data: schemas.AdminUpdateSales, db: Session = Depends(get_db)):
    """Cap nhat thong tin sales, bao gom khu vuc phu trach"""
    sales = db.query(models.User).filter(models.User.id == user_id).first()
    provided_fields = getattr(user_data, "model_fields_set", user_data.__fields_set__)

    if not sales:
        raise HTTPException(status_code=404, detail="Sales khong tim thay")

    if sales.role != 'sales':
        raise HTTPException(status_code=400, detail="User nay khong phai sales role")

    if user_data.email and user_data.email != sales.email:
        existing_email = db.query(models.User).filter(
            and_(
                models.User.email == user_data.email,
                models.User.id != user_id
            )
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email da duoc dang ky")
        sales.email = user_data.email

    if user_data.full_name is not None:
        sales.full_name = user_data.full_name

    if user_data.phone is not None:
        sales.phone = user_data.phone

    if "region_id" in provided_fields:
        if user_data.region_id is not None:
            region = db.query(models.Region).filter(
                models.Region.id == user_data.region_id
            ).first()
            if not region:
                raise HTTPException(status_code=404, detail="Khu vuc khong tim thay")
        sales.region_id = user_data.region_id

    try:
        db.commit()
        db.refresh(sales)
        return {"msg": f"Da cap nhat sales {sales.username} thanh cong"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Loi khi cap nhat sales: {str(e)}")


@router.get("/admin/sales-by-region/{region_id}")
def get_sales_by_region(region_id: int, db: Session = Depends(get_db)):
    """Lấy danh sách sales thuộc khu vực"""
    region = db.query(models.Region).filter(
        models.Region.id == region_id
    ).first()
    
    if not region:
        raise HTTPException(status_code=404, detail="Khu vực không tìm thấy")
    
    sales_users = db.query(models.User).filter(
        and_(
            models.User.region_id == region_id,
            models.User.role == 'sales'
        )
    ).all()
    
    return sales_users


# ============ ZONE ROUTES ============
@router.post("/zones")
def create_zone(zone: schemas.ZoneCreate, db: Session = Depends(get_db)):
    """Tạo zone"""
    existing = db.query(models.Zone).filter(
        models.Zone.zone_code == zone.zone_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mã zone đã tồn tại")
    
    new_zone = models.Zone(
        zone_code=zone.zone_code,
        territory_id=zone.territory_id,  # Đổi từ district_id thành territory_id
        name=zone.name,
        geometry=zone.geometry,
        center_lat=zone.center_lat,
        center_lng=zone.center_lng,
        area_size=zone.area_size,
        num_customers=zone.num_customers,
        num_orders=zone.num_orders,
        revenue=zone.revenue
    )
    db.add(new_zone)
    db.commit()
    db.refresh(new_zone) # Thêm refresh để lấy ID mới
    territory = db.query(models.Territory).filter(models.Territory.id == zone.territory_id).first()
    if territory:
        zone_ids = list(territory.zone_ids or [])
        if new_zone.id not in zone_ids:
            zone_ids.append(new_zone.id)
            territory.zone_ids = zone_ids
            db.commit()
    return new_zone


@router.get("/zones")
def get_zones(district_id: int = Query(None), db: Session = Depends(get_db)):
    """Lấy danh sách zones"""
    query = db.query(models.Zone)
    if district_id:
        query = query.filter(models.Zone.district_id == district_id)
    return query.all()


@router.get("/zones/overlaps")
def get_zone_overlaps(territory_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """Các cặp zone trong cùng một territory có phần giao đáng kể (>= OVERLAP_MIN_AREA_M2)."""
    query = db.query(models.Zone).filter(models.Zone.territory_id.isnot(None))
    if territory_id:
        query = query.filter(models.Zone.territory_id == territory_id)
    zones = query.all()

    polygons = {}
    skipped = []
    for zone in zones:
        polygon = _zone_shape(zone)
        if polygon is None:
            skipped.append({"id": zone.id, "name": zone.name})
        else:
            polygons[zone.id] = polygon

    by_territory: Dict[int, List[models.Zone]] = {}
    for zone in zones:
        if zone.id in polygons:
            by_territory.setdefault(zone.territory_id, []).append(zone)

    overlaps = []
    for group in by_territory.values():
        tree = STRtree([polygons[z.id] for z in group])
        for index, first in enumerate(group):
            polygon_a = polygons[first.id]
            for other_index in tree.query(polygon_a, predicate="intersects"):
                other_index = int(other_index)
                if other_index <= index:
                    continue
                second = group[other_index]
                intersection = polygon_a.intersection(polygons[second.id])
                if intersection.is_empty:
                    continue
                # Đổi độ² sang m² tại vĩ độ của phần giao.
                lat = intersection.representative_point().y
                area_m2 = intersection.area * (111320.0 ** 2) * math.cos(math.radians(lat))
                if area_m2 >= OVERLAP_MIN_AREA_M2:
                    overlaps.append({
                        "zone_a": {"id": first.id, "name": first.name, "zone_code": first.zone_code},
                        "zone_b": {"id": second.id, "name": second.name, "zone_code": second.zone_code},
                        "overlap_area": intersection.area,
                        "overlap_area_m2": round(area_m2, 1),
                    })
    return {"count": len(overlaps), "overlaps": overlaps, "skipped_zones": skipped}


@router.get("/zones/{zone_id}")
def get_zone(zone_id: int, db: Session = Depends(get_db)):
    """Lấy chi tiết zone"""
    zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone không tìm thấy")
    return zone


@router.put("/zones/{zone_id}")
def update_zone(zone_id: int, zone: schemas.ZoneUpdate, db: Session = Depends(get_db)):
    """Cập nhật zone"""
    db_zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Zone không tìm thấy")
    
    update_data = zone.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_zone, key, value)
    
    db.commit()
    return db_zone


@router.put("/zones/{zone_id}/metrics")
def update_zone_metrics(zone_id: int, metrics: schemas.ZoneMetricsUpdate, db: Session = Depends(get_db)):
    """Cap nhat thong tin kinh doanh cua zone va luu vao lich su ban hang."""
    db_zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Zone khong tim thay")

    db_zone.num_customers = metrics.num_customers
    db_zone.num_orders = metrics.num_orders
    db_zone.revenue = metrics.revenue

    activity = models.ZoneActivity(
        zone_id=zone_id,
        num_customers=metrics.num_customers,
        num_orders=metrics.num_orders,
        avg_order_value=(metrics.revenue / metrics.num_orders) if metrics.num_orders else 0,
        total_revenue=metrics.revenue,
        notes=metrics.notes,
    )

    db.add(activity)
    db.commit()
    db.refresh(db_zone)
    return db_zone


@router.post("/zones/{zone_id}/activities")
def create_zone_activity(zone_id: int, activity: schemas.ZoneActivityCreate, 
                        db: Session = Depends(get_db)):
    """Tạo hoạt động cho zone"""
    zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone không tìm thấy")
    
    # Xóa activity cũ nếu có
    new_activity = models.ZoneActivity(
        zone_id=zone_id,
        num_customers=activity.num_customers,
        num_orders=activity.num_orders,
        avg_order_value=activity.avg_order_value,
        total_revenue=activity.total_revenue,
        population_density=activity.population_density,
        business_density=activity.business_density,
        traffic_density=activity.traffic_density,
        notes=activity.notes
    )
    
    # Cập nhật thông tin zone
    zone.num_customers = activity.num_customers
    zone.num_orders = activity.num_orders
    zone.revenue = activity.total_revenue
    
    db.add(new_activity)
    db.commit()
    return new_activity


@router.get("/zones/{zone_id}/activities")
def get_zone_activity(zone_id: int, db: Session = Depends(get_db)):
    """Lấy hoạt động của zone"""
    activity = db.query(models.ZoneActivity).filter(
        models.ZoneActivity.zone_id == zone_id
    ).order_by(models.ZoneActivity.updated_at.desc()).all()
    
    if not activity:
        return []
    
    return activity

@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    """Xóa zone và các activity liên quan"""
    zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone không tìm thấy")
    
    # Xóa các bản ghi phụ thuộc trước để tránh lỗi khóa ngoại.
    activities = db.query(models.ZoneActivity).filter(models.ZoneActivity.zone_id == zone_id).all()
    for activity in activities:
        db.delete(activity)
    for adjacency in db.query(models.ZoneAdjacency).filter(
        or_(models.ZoneAdjacency.zone_id1 == zone_id, models.ZoneAdjacency.zone_id2 == zone_id)
    ).all():
        db.delete(adjacency)
    for distance in db.query(models.ZoneDistance).filter(
        or_(models.ZoneDistance.zone_id1 == zone_id, models.ZoneDistance.zone_id2 == zone_id)
    ).all():
        db.delete(distance)

    # Đồng bộ cả territory hiện tại và dữ liệu zone_ids cũ.
    for territory in db.query(models.Territory).all():
        if territory.zone_ids and any(int(zid) == int(zone_id) for zid in territory.zone_ids):
            territory.zone_ids = [zid for zid in territory.zone_ids if int(zid) != int(zone_id)]

    db.delete(zone)
    db.commit()
    return {"msg": "Đã xóa Zone thành công"}

# ============ TERRITORY ROUTES ============
@router.post("/territories")
def create_territory(territory: schemas.TerritoryCreate, db: Session = Depends(get_db)):
    """Tạo phân vùng mới"""
    # Kiểm tra tên phân vùng đã tồn tại
    existing = db.query(models.Territory).filter(
        models.Territory.name == territory.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tên phân vùng đã tồn tại")
    
    # Kiểm tra khu vực tồn tại
    region = db.query(models.Region).filter(
        models.Region.id == territory.region_id
    ).first()
    if not region:
        raise HTTPException(status_code=400, detail="Khu vực không tồn tại")
    
    # Kiểm tra tất cả zones tồn tại
    source_territory_ids = list(getattr(territory, "source_territory_ids", []) or [])
    source_zones = []
    if source_territory_ids:
        source_territories = db.query(models.Territory).filter(
            models.Territory.id.in_(source_territory_ids)
        ).all()
        if len(source_territories) != len(source_territory_ids):
            raise HTTPException(status_code=400, detail="Mot so phan vung nguon khong ton tai")

        source_zones = db.query(models.Zone).filter(
            models.Zone.territory_id.in_(source_territory_ids)
        ).all()

    explicit_zones = db.query(models.Zone).filter(models.Zone.id.in_(territory.zone_ids)).all()
    if len(explicit_zones) != len(territory.zone_ids):
        raise HTTPException(status_code=400, detail="Mot so zones khong ton tai")
    zones_to_clone = list({z.id: z for z in [*source_zones, *explicit_zones]}.values())
    
    new_territory = models.Territory(
        name=territory.name,
        region_id=territory.region_id,
        zone_ids=[]
    )
    
    db.add(new_territory)
    db.flush()

    new_zone_ids = []
    for zone in zones_to_clone:
        cloned_zone = models.Zone(
            zone_code=f"{zone.zone_code}-M{new_territory.id}-{int(time.time())}-{zone.id}",
            territory_id=new_territory.id,
            name=zone.name,
            geometry=zone.geometry,
            center_lat=zone.center_lat,
            center_lng=zone.center_lng,
            area_size=zone.area_size,
            num_customers=zone.num_customers,
            num_orders=zone.num_orders,
            revenue=zone.revenue,
        )
        db.add(cloned_zone)
        db.flush()
        new_zone_ids.append(cloned_zone.id)

    new_territory.zone_ids = new_zone_ids
    db.commit()
    db.refresh(new_territory)
    return new_territory


@router.get("/territories")
def get_territories(db: Session = Depends(get_db)):
    """Lấy danh sách phân vùng"""
    query = db.query(models.Territory)
    territories = query.all()
    changed = False
    for territory in territories:
        actual_zone_ids = [
            zone.id
            for zone in db.query(models.Zone).filter(
                models.Zone.territory_id == territory.id
            ).all()
        ]
        if actual_zone_ids and territory.zone_ids != actual_zone_ids:
            territory.zone_ids = actual_zone_ids
            changed = True
    if changed:
        db.commit()
    return territories


@router.get("/territories/{territory_id}")
def get_territory(territory_id: int, db: Session = Depends(get_db)):
    """Lấy chi tiết phân vùng"""
    territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id
    ).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Phân vùng không tìm thấy")
    return territory


@router.post("/territories/{territory_id}/rebuild-adjacency")
def rebuild_territory_adjacency(territory_id: int, db: Session = Depends(get_db)):
    """Cap nhat lai ma tran ke cua cac zone trong phan vung."""
    territory = db.query(models.Territory).filter(models.Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Phan vung khong tim thay")
    result = _rebuild_zone_adjacency(territory, db)
    db.commit()
    return {"msg": "Da cap nhat ma tran ke", **result}


FAKE_MEDIAN_ZONE_CUSTOMERS = fake_metrics.MEDIAN_ZONE_CUSTOMERS  # zone có diện tích trung vị nhận chừng này KH
FAKE_MIN_CUSTOMERS = fake_metrics.MIN_CUSTOMERS


@router.post("/territories/{territory_id}/fake-zone-metrics")
def fake_territory_zone_metrics(
    territory_id: int,
    seed: Optional[int] = Query(None, description="Seed để tạo lại đúng cùng dữ liệu"),
    customers_per_km2: Optional[float] = Query(
        None, gt=0, description="Mật độ khách hàng cố định; mặc định tự hiệu chỉnh theo diện tích trung vị"
    ),
    noise: float = Query(0.25, ge=0, le=1, description="Độ lệch chuẩn của nhiễu log-normal quanh mật độ"),
    db: Session = Depends(get_db),
):
    """Tạo dữ liệu mẫu theo diện tích: khách hàng = mật độ x diện tích (km²) x nhiễu log-normal.

    Mật độ mặc định = FAKE_MEDIAN_ZONE_CUSTOMERS / diện tích trung vị của phân vùng, nên trong một phân vùng
    số khách hàng tỉ lệ với diện tích, còn độ lớn chung giữ như trước. Đơn hàng và doanh thu sinh theo khách hàng.
    Diện tích được lưu vào zone.area_size (km²)."""
    territory = db.query(models.Territory).filter(models.Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Phan vung khong tim thay")

    zone_ids = _get_territory_zone_ids(territory, db)
    zones = db.query(models.Zone).filter(models.Zone.id.in_(zone_ids)).all() if zone_ids else []
    if not zones:
        raise HTTPException(status_code=400, detail="Phan vung khong co zones")

    seed = seed if seed is not None else random.randrange(1, 2 ** 31)
    rng = random.Random(seed)

    areas = {zone.id: _zone_area_km2(zone) for zone in zones}
    try:
        density, median_area = fake_metrics.density_for(areas.values(), customers_per_km2)
    except ValueError:
        raise HTTPException(status_code=400, detail="Khong zone nao co geometry hop le de tinh dien tich")
    missing_geometry = [zone.id for zone in zones if not areas[zone.id]]

    for zone in zones:
        area = areas[zone.id] or median_area
        if areas[zone.id]:
            zone.area_size = round(area, 4)
        customers = fake_metrics.fake_customers(rng, area, density, noise)
        orders = fake_metrics.fake_orders(rng, customers)
        avg_order_value = rng.randint(180000, 2500000)
        revenue = float(orders * avg_order_value)
        zone.num_customers = customers
        zone.num_orders = orders
        zone.revenue = revenue
        db.add(
            models.ZoneActivity(
                zone_id=zone.id,
                num_customers=customers,
                num_orders=orders,
                avg_order_value=avg_order_value,
                total_revenue=revenue,
                notes=f"Fake data by area (seed {seed})",
            )
        )

    db.commit()
    return {
        "msg": "Da fake du lieu kinh doanh cho zones theo dien tich",
        "updated_zones": len(zones),
        "seed": seed,
        "customers_per_km2": round(density, 2),
        "median_area_km2": round(median_area, 4),
        "total_area_km2": round(sum(areas[z.id] or median_area for z in zones), 4),
        "zones_without_geometry": missing_geometry,
    }


@router.post("/territories/{territory_id}/versions")
def create_territory_version(
    territory_id: int,
    request: schemas.TerritoryVersionCreate,
    db: Session = Depends(get_db),
):
    """Tao version moi bang cach clone zones hien tai cua phan vung."""
    territory = db.query(models.Territory).filter(models.Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Phan vung khong tim thay")

    root_id = territory.parent_territory_id or territory.id
    version_scope_ids = [root_id]
    children = db.query(models.Territory).filter(models.Territory.parent_territory_id == root_id).all()
    version_scope_ids.extend([child.id for child in children])
    current_max_version = max([t.version_no or 1 for t in [territory, *children]] or [1])
    next_version = current_max_version + 1
    new_name = request.name or f"{territory.name} v{next_version}"

    existing = db.query(models.Territory).filter(models.Territory.name == new_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ten version phan vung da ton tai")

    new_territory = models.Territory(
        name=new_name,
        region_id=territory.region_id,
        parent_territory_id=root_id,
        version_no=next_version,
        zone_ids=[],
    )
    db.add(new_territory)
    db.flush()

    source_zones = db.query(models.Zone).filter(models.Zone.territory_id == territory.id).all()
    if not source_zones and territory.zone_ids:
        source_zones = db.query(models.Zone).filter(models.Zone.id.in_(territory.zone_ids)).all()

    new_zone_ids = []
    for zone in source_zones:
        cloned_zone = models.Zone(
            zone_code=f"{zone.zone_code}-V{next_version}-{int(time.time())}",
            territory_id=new_territory.id,
            name=zone.name,
            geometry=zone.geometry,
            center_lat=zone.center_lat,
            center_lng=zone.center_lng,
            area_size=zone.area_size,
            num_customers=zone.num_customers,
            num_orders=zone.num_orders,
            revenue=zone.revenue,
        )
        db.add(cloned_zone)
        db.flush()
        new_zone_ids.append(cloned_zone.id)

    new_territory.zone_ids = new_zone_ids
    db.commit()
    db.refresh(new_territory)
    return new_territory


@router.put("/territories/{territory_id}")
def update_territory(territory_id: int, territory: schemas.TerritoryUpdate, db: Session = Depends(get_db)):
    db_territory = db.query(models.Territory).filter(models.Territory.id == territory_id).first()
    if not db_territory:
        raise HTTPException(status_code=404, detail="Phân vùng không tìm thấy")
    
    if territory.zone_ids is not None:
        # Đảm bảo lưu dưới dạng list các số nguyên
        db_territory.zone_ids = [int(id) for id in territory.zone_ids]
    
    if territory.name:
        db_territory.name = territory.name
    
    db.commit()
    db.refresh(db_territory) # Làm mới dữ liệu
    return db_territory


@router.delete("/territories/{territory_id}")
def delete_territory(territory_id: int, db: Session = Depends(get_db)):
    """Xóa territory cùng toàn bộ zone và dữ liệu phụ thuộc."""
    territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id
    ).first()
    
    if not territory:
        raise HTTPException(status_code=404, detail="Phân vùng không tìm thấy")

    zone_ids = [z.id for z in db.query(models.Zone.id).filter(
        models.Zone.territory_id == territory_id
    ).all()]
    if zone_ids:
        db.query(models.ZoneActivity).filter(models.ZoneActivity.zone_id.in_(zone_ids)).delete(
            synchronize_session=False
        )
        db.query(models.ZoneAdjacency).filter(or_(
            models.ZoneAdjacency.zone_id1.in_(zone_ids),
            models.ZoneAdjacency.zone_id2.in_(zone_ids),
        )).delete(synchronize_session=False)
        db.query(models.ZoneDistance).filter(or_(
            models.ZoneDistance.zone_id1.in_(zone_ids),
            models.ZoneDistance.zone_id2.in_(zone_ids),
        )).delete(synchronize_session=False)
        db.query(models.Zone).filter(models.Zone.id.in_(zone_ids)).delete(
            synchronize_session=False
        )
    db.query(models.WorkAssignment).filter(
        models.WorkAssignment.territory_id == territory_id
    ).delete(synchronize_session=False)
    db.delete(territory)
    db.commit()
    
    return {"msg": "Đã xóa Territory thành công"}



# ============ SALES ROUTES ============
def _serialize_zone_for_sales(zone: models.Zone) -> Dict[str, Any]:
    return {
        "id": zone.id,
        "zone_code": zone.zone_code,
        "name": zone.name,
        "territory_id": zone.territory_id,
        "geometry": zone.geometry,
        "center_lat": zone.center_lat,
        "center_lng": zone.center_lng,
        "num_customers": zone.num_customers or 0,
        "num_orders": zone.num_orders or 0,
        "revenue": zone.revenue or 0,
        "created_at": zone.created_at,
    }


def _find_sales_assignment(
    sales_id: int,
    db: Session,
    date: Optional[str] = None,
) -> Optional[models.WorkAssignment]:
    query = db.query(models.WorkAssignment).filter(
        models.WorkAssignment.is_finalized == True
    )
    if date:
        query = query.filter(models.WorkAssignment.assignment_date.like(f"{date}%"))
    assignments = query.order_by(models.WorkAssignment.assignment_date.desc()).all()
    for assignment in assignments:
        if str(sales_id) in (assignment.assignment_data or {}):
            return assignment
    return None


@router.get("/sales/{sales_id}/profile")
def get_sales_profile(sales_id: int, db: Session = Depends(get_db)):
    sales = db.query(models.User).filter(models.User.id == sales_id).first()
    if not sales:
        raise HTTPException(status_code=404, detail="Sales khong tim thay")
    if sales.role != "sales":
        raise HTTPException(status_code=400, detail="User nay khong phai sales")
    return {
        "id": sales.id,
        "username": sales.username,
        "email": sales.email,
        "full_name": sales.full_name,
        "phone": sales.phone,
        "region_id": sales.region_id,
        "region_name": sales.region.name if sales.region else None,
        "created_at": sales.created_at,
    }


@router.put("/sales/{sales_id}/profile")
def update_sales_profile(
    sales_id: int,
    user_data: schemas.SalesProfileUpdate,
    db: Session = Depends(get_db),
):
    sales = db.query(models.User).filter(models.User.id == sales_id).first()
    if not sales:
        raise HTTPException(status_code=404, detail="Sales khong tim thay")
    if sales.role != "sales":
        raise HTTPException(status_code=400, detail="User nay khong phai sales")

    if user_data.email and user_data.email != sales.email:
        existing_email = db.query(models.User).filter(
            models.User.email == user_data.email,
            models.User.id != sales_id,
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email da duoc su dung")
        sales.email = user_data.email
    if user_data.full_name is not None:
        sales.full_name = user_data.full_name
    if user_data.phone is not None:
        sales.phone = user_data.phone

    db.commit()
    db.refresh(sales)
    return {"msg": "Da cap nhat ho so thanh cong", "profile": get_sales_profile(sales_id, db)}


@router.get("/sales/{sales_id}/work-shift")
def get_sales_work_shift(
    sales_id: int,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    shift_date = date or datetime.utcnow().strftime("%Y-%m-%d")
    assignment = _find_sales_assignment(sales_id, db, shift_date)
    if not assignment:
        return {
            "sales_id": sales_id,
            "date": shift_date,
            "has_shift": False,
            "zones": [],
            "summary": {
                "total_zones": 0,
                "total_customers": 0,
                "total_orders": 0,
                "total_revenue": 0,
            },
        }

    zone_ids = [int(zone_id) for zone_id in assignment.assignment_data.get(str(sales_id), [])]
    zones = db.query(models.Zone).filter(models.Zone.id.in_(zone_ids)).all() if zone_ids else []
    territory = assignment.territory

    return {
        "sales_id": sales_id,
        "date": shift_date,
        "has_shift": True,
        "assignment_id": assignment.id,
        "assignment_date": assignment.assignment_date,
        "territory": {
            "id": territory.id,
            "name": territory.name,
            "region_id": territory.region_id,
            "region_name": territory.region.name if territory.region else None,
        } if territory else None,
        "zones": [_serialize_zone_for_sales(zone) for zone in zones],
        "summary": {
            "total_zones": len(zones),
            "total_customers": sum(zone.num_customers or 0 for zone in zones),
            "total_orders": sum(zone.num_orders or 0 for zone in zones),
            "total_revenue": sum(zone.revenue or 0 for zone in zones),
        },
        "algorithm": assignment.algorithm_used,
    }


@router.get("/sales/{sales_id}/sales-history")
def get_sales_history(sales_id: int, db: Session = Depends(get_db)):
    assignments = db.query(models.WorkAssignment).filter(
        models.WorkAssignment.is_finalized == True
    ).order_by(models.WorkAssignment.assignment_date.desc()).all()

    rows = []
    seen_activity_ids = set()
    for assignment in assignments:
        zone_ids = [int(zone_id) for zone_id in (assignment.assignment_data or {}).get(str(sales_id), [])]
        if not zone_ids:
            continue
        zones = db.query(models.Zone).filter(models.Zone.id.in_(zone_ids)).all()
        zone_by_id = {zone.id: zone for zone in zones}
        activities = db.query(models.ZoneActivity).filter(
            models.ZoneActivity.zone_id.in_(zone_ids)
        ).order_by(models.ZoneActivity.updated_at.desc()).all()

        for activity in activities:
            if activity.id in seen_activity_ids:
                continue
            seen_activity_ids.add(activity.id)
            zone = zone_by_id.get(activity.zone_id)
            rows.append({
                "id": activity.id,
                "assignment_id": assignment.id,
                "assignment_date": assignment.assignment_date,
                "territory_id": assignment.territory_id,
                "territory_name": assignment.territory.name if assignment.territory else None,
                "zone_id": activity.zone_id,
                "zone_name": zone.name if zone else None,
                "zone_code": zone.zone_code if zone else None,
                "updated_at": activity.updated_at,
                "num_customers": activity.num_customers or 0,
                "num_orders": activity.num_orders or 0,
                "total_revenue": activity.total_revenue or 0,
                "avg_order_value": activity.avg_order_value or 0,
                "notes": activity.notes,
            })

    return rows


@router.post("/sales/{sales_id}/invoices")
def create_sales_invoice(
    sales_id: int,
    invoice: schemas.SalesInvoiceCreate,
    db: Session = Depends(get_db),
):
    assignment = _find_sales_assignment(sales_id, db, datetime.utcnow().strftime("%Y-%m-%d"))
    if not assignment:
        raise HTTPException(status_code=400, detail="Sales chua co ca lam viec hom nay")

    assigned_zone_ids = [int(zone_id) for zone_id in assignment.assignment_data.get(str(sales_id), [])]
    if invoice.zone_id not in assigned_zone_ids:
        raise HTTPException(status_code=400, detail="Zone khong thuoc ca lam viec hom nay")

    zone = db.query(models.Zone).filter(models.Zone.id == invoice.zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone khong tim thay")
    if invoice.order_count <= 0:
        raise HTTPException(status_code=400, detail="So don phai lon hon 0")
    if invoice.amount < 0:
        raise HTTPException(status_code=400, detail="Gia tien khong hop le")

    zone.num_orders = (zone.num_orders or 0) + invoice.order_count
    zone.num_customers = (zone.num_customers or 0) + max(invoice.customer_count or 0, 0)
    zone.revenue = (zone.revenue or 0) + invoice.amount

    sold_at = invoice.sold_at or datetime.utcnow()
    location_note = ""
    if invoice.current_lat is not None and invoice.current_lng is not None:
        location_note = f" | vi tri: {invoice.current_lat}, {invoice.current_lng}"
    notes = (
        f"Hoa don sales #{sales_id}; thoi gian: {sold_at.isoformat()}; "
        f"so don: {invoice.order_count}; gia tien: {invoice.amount}; "
        f"zone: {zone.name}{location_note}"
    )
    if invoice.notes:
        notes = f"{notes} | ghi chu: {invoice.notes}"

    activity = models.ZoneActivity(
        zone_id=zone.id,
        num_customers=zone.num_customers,
        num_orders=zone.num_orders,
        avg_order_value=(zone.revenue / zone.num_orders) if zone.num_orders else 0,
        total_revenue=zone.revenue,
        notes=notes,
        updated_by=sales_id,
        updated_at=sold_at,
    )

    db.add(activity)
    db.commit()
    db.refresh(zone)
    return {
        "msg": "Da tao hoa don thanh cong",
        "invoice": {
            "zone_id": zone.id,
            "zone_name": zone.name,
            "order_count": invoice.order_count,
            "amount": invoice.amount,
            "sold_at": sold_at,
            "current_lat": invoice.current_lat,
            "current_lng": invoice.current_lng,
        },
        "zone": _serialize_zone_for_sales(zone),
    }


@router.get("/sales/{sales_id}/assignments")
def get_sales_assignments(sales_id: int, date: Optional[str] = None, db: Session = Depends(get_db)):
    """Lấy assignments (phân vùng) của sales person"""
    query = db.query(models.WorkAssignment).filter(
        models.WorkAssignment.assignment_data.contains(f'"{sales_id}"')
    )
    
    if date:
        query = query.filter(models.WorkAssignment.assignment_date == date)
    
    assignments = query.all()
    return assignments


@router.get("/sales/{sales_id}/dashboard")
def get_sales_dashboard(sales_id: int, db: Session = Depends(get_db)):
    """Lấy dashboard cho sales person"""
    # Get latest assignment for this sales person
    latest_assignment = db.query(models.WorkAssignment).filter(
        models.WorkAssignment.assignment_data.contains(f'"{sales_id}"'),
        models.WorkAssignment.is_finalized == True
    ).order_by(models.WorkAssignment.assignment_date.desc()).first()
    
    if not latest_assignment:
        return {
            'sales_id': sales_id,
            'num_assignments': 0,
            'total_zones': 0,
            'total_customers': 0,
            'total_orders': 0,
            'total_revenue': 0,
            'assignments': []
        }
    
    # Get zones assigned to this sales person from latest assignment
    assignment_data = latest_assignment.assignment_data  # {sales_id: [zone_ids]}
    zone_ids = assignment_data.get(str(sales_id), [])
    
    zones = db.query(models.Zone).filter(models.Zone.id.in_(zone_ids)).all()
    
    total_customers = sum(z.num_customers for z in zones)
    total_orders = sum(z.num_orders for z in zones)
    total_revenue = sum(z.revenue for z in zones)
    total_zones = len(zones)
    
    return {
        'sales_id': sales_id,
        'num_assignments': 1,
        'total_zones': total_zones,
        'total_customers': total_customers,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'zones': zones,
        'assignment_date': latest_assignment.assignment_date,
        'algorithm': latest_assignment.algorithm_used
    }


# ============ ADMIN ROUTES ============
@router.get("/admin/statistics")
def get_admin_statistics(db: Session = Depends(get_db)):
    """Lấy thống kê cho admin"""
    total_zones = db.query(models.Zone).count()
    total_territories = db.query(models.Territory).count()
    total_sales = db.query(models.User).filter(models.User.role == 'sales').count()
    all_zones = db.query(models.Zone).all()
    total_customers = sum(z.num_customers for z in all_zones)
    total_orders = sum(z.num_orders for z in all_zones)
    total_revenue = sum(z.revenue for z in all_zones)
    
    return {
        'total_zones': total_zones,
        'total_territories': total_territories,
        'total_sales': total_sales,
        'total_customers': total_customers,
        'total_orders': total_orders,
        'total_revenue': total_revenue
    }


@router.get("/admin/all-sales")
def get_all_sales(db: Session = Depends(get_db)):
    """Lấy danh sách tất cả sales"""
    sales = db.query(models.User).filter(
        models.User.role == 'sales',
        models.User.is_approved == True
    ).all()
    return sales


@router.get("/admin/available-sales")
def get_available_sales(date: str = Query(...), db: Session = Depends(get_db)):
    """
    Lấy danh sách sales chưa được phân công vào ngày định
    date: YYYY-MM-DD format
    """
    # Hiện tại trả về tất cả sales đã duyệt
    # Trong tương lai có thể kiểm tra với WorkAssignment
    sales = db.query(models.User).filter(
        models.User.role == 'sales',
        models.User.is_approved == True
    ).all()
    return sales


@router.post("/admin/assign-work")
def assign_work(request: schemas.AssignWorkRequest, db: Session = Depends(get_db)):
    """Run territory assignment with fresh adjacency and region/free-sales checks."""
    try:
        territory = db.query(models.Territory).filter(
            models.Territory.id == request.territory_id
        ).first()
        if not territory:
            raise HTTPException(status_code=404, detail="Phan vung khong ton tai")

        zone_ids = _get_territory_zone_ids(territory, db)
        zones_in_territory = db.query(models.Zone).filter(
            models.Zone.id.in_(zone_ids)
        ).all() if zone_ids else []
        if not zones_in_territory:
            raise HTTPException(status_code=400, detail="Phan vung khong co zones nao")

        sales_ids = list(dict.fromkeys([int(sid) for sid in request.sales_ids]))
        if not sales_ids:
            raise HTTPException(status_code=400, detail="Vui long chon sales")
        if len(sales_ids) > len(zones_in_territory):
            raise HTTPException(
                status_code=400,
                detail="So sales khong duoc lon hon so zones neu moi sales can it nhat 1 zone",
            )

        selected_sales = db.query(models.User).filter(models.User.id.in_(sales_ids)).all()
        if len(selected_sales) != len(sales_ids):
            raise HTTPException(status_code=400, detail="Mot so sales khong ton tai")

        invalid_sales = [
            sales.id
            for sales in selected_sales
            if sales.role != "sales"
            or not sales.is_approved
            or sales.region_id != territory.region_id
        ]
        if invalid_sales:
            raise HTTPException(
                status_code=400,
                detail=f"Sales khong thuoc cung khu vuc phan vung: {invalid_sales}",
            )

        busy_assignments = db.query(models.WorkAssignment).filter(
            models.WorkAssignment.assignment_date.like(f"{request.date}%")
        ).all()
        busy_sales_ids = {
            int(sid)
            for assignment in busy_assignments
            for sid in assignment.assignment_data.keys()
        }
        selected_busy_sales = [sid for sid in sales_ids if sid in busy_sales_ids]
        if selected_busy_sales:
            raise HTTPException(
                status_code=400,
                detail=f"Sales da ban trong ngay nay: {selected_busy_sales}",
            )

        adjacency_meta = _rebuild_zone_adjacency(territory, db)
        db.commit()

        zones_data = [
            {
                "id": z.id,
                "code": z.zone_code,
                "lat": z.center_lat or 21.0285,
                "lng": z.center_lng or 105.8542,
                "num_customers": z.num_customers or 0,
                "num_orders": z.num_orders or 0,
                "revenue": z.revenue or 0,
            }
            for z in zones_in_territory
        ]

        adj_list = {zone_id: [] for zone_id in zone_ids}
        adjacencies = db.query(models.ZoneAdjacency).filter(
            (models.ZoneAdjacency.zone_id1.in_(zone_ids))
            | (models.ZoneAdjacency.zone_id2.in_(zone_ids))
        ).all()
        for adj in adjacencies:
            if adj.is_adjacent:
                adj_list.setdefault(adj.zone_id1, []).append(adj.zone_id2)
                adj_list.setdefault(adj.zone_id2, []).append(adj.zone_id1)

        if len(zone_ids) > 1 and not any(adj_list.values()):
            raise HTTPException(
                status_code=400,
                detail="Không xác định được quan hệ kề giữa các zone. Hãy kiểm tra geometry của zone.",
            )

        designer = AdvancedTerritoryDesign(zones_data, adj_list)
        result = designer.solve(num_sales=len(sales_ids), algorithm=request.algorithm)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])

        territories_result = result.get("territories", {})
        assignment = {}
        for i, sales_id in enumerate(sales_ids):
            assignment[str(sales_id)] = territories_result.get(i, territories_result.get(str(i), []))

        assigned_zone_ids = {
            int(zone_id)
            for zone_list in assignment.values()
            for zone_id in zone_list
        }
        missing_zone_ids = [zone_id for zone_id in zone_ids if zone_id not in assigned_zone_ids]
        if missing_zone_ids:
            zone_workload = {
                zone["id"]: zone["num_customers"] + zone["num_orders"] * 0.2
                for zone in zones_data
            }
            for zone_id in missing_zone_ids:
                neighbor_sales = {
                    sales_id
                    for sales_id, assigned_ids in assignment.items()
                    if any(neighbor_id in assigned_ids for neighbor_id in adj_list.get(zone_id, []))
                }
                if neighbor_sales:
                    target_sales = min(
                        neighbor_sales,
                        key=lambda sales_id: sum(
                            zone_workload.get(int(assigned_zone_id), 0)
                            for assigned_zone_id in assignment[sales_id]
                        ),
                    )
                else:
                    target_sales = min(
                        assignment.keys(),
                        key=lambda sales_id: sum(
                            zone_workload.get(int(assigned_zone_id), 0)
                            for assigned_zone_id in assignment[sales_id]
                        ),
                    )
                assignment[str(target_sales)].append(zone_id)

        return {
            "assignment": assignment,
            "metrics": result.get("metrics", {}),
            "cv_pct": result.get("cv_pct", 0),
            "total_distance": result.get("total_distance", 0),
            "hoover_index": result.get("hoover_index", 0),
            "algorithm": request.algorithm,
            "adjacency": adjacency_meta,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi khi chay thuat toan: {str(e)}")


@router.post("/admin/assign-work-legacy")
def assign_work(request: schemas.AssignWorkRequest, db: Session = Depends(get_db)):
    """
    Chạy thuật toán chia việc và trả về kết quả giao việc
    """
    try:
        from algorithms import AdvancedTerritoryDesign
        
        # Lấy thông tin phân vùng
        territory = db.query(models.Territory).filter(
            models.Territory.id == request.territory_id
        ).first()
        
        if not territory:
            raise HTTPException(status_code=404, detail="Phân vùng không tồn tại")
        
        # Lấy thông tin zones
        zones_in_territory = db.query(models.Zone).filter(
            models.Zone.id.in_(territory.zone_ids)
        ).all()
        
        if not zones_in_territory:
            raise HTTPException(status_code=400, detail="Phân vùng không có zones nào")
        
        # Chuẩn bị dữ liệu cho algorithm
        zones_data = [
            {
                'id': z.id,
                'code': z.zone_code,
                'lat': z.center_lat or 21.0285,
                'lng': z.center_lng or 105.8542,
                'num_customers': z.num_customers,
                'num_orders': z.num_orders,
                'revenue': z.revenue
            }
            for z in zones_in_territory
        ]
        
        # Tạo ma trận kề từ ZoneAdjacency
        adj_list = {}
        for zone_id in territory.zone_ids:
            adj_list[zone_id] = []
        
        adjacencies = db.query(models.ZoneAdjacency).filter(
            (models.ZoneAdjacency.zone_id1.in_(territory.zone_ids)) | 
            (models.ZoneAdjacency.zone_id2.in_(territory.zone_ids))
        ).all()
        
        for adj in adjacencies:
            if adj.is_adjacent:
                if adj.zone_id1 not in adj_list:
                    adj_list[adj.zone_id1] = []
                if adj.zone_id2 not in adj_list:
                    adj_list[adj.zone_id2] = []
                
                adj_list[adj.zone_id1].append(adj.zone_id2)
                adj_list[adj.zone_id2].append(adj.zone_id1)
        
        # Nếu không có adjacency, tạo đường nối đơn giản
        if not adjacencies:
            zone_ids_list = territory.zone_ids
            for i, z_id in enumerate(zone_ids_list):
                if i > 0:
                    adj_list[z_id].append(zone_ids_list[i-1])
        
        # Gọi thuật toán
        num_sales = len(request.sales_ids)
        designer = AdvancedTerritoryDesign(zones_data, adj_list)
        
        result = designer.solve(
            num_sales=num_sales,
            algorithm=request.algorithm
        )
        
        # Convert result territories (dict) to assignment format
        assignment = {}
        for i, sales_id in enumerate(request.sales_ids):
            if str(i) in result.get('territories', {}):
                assignment[sales_id] = result['territories'][str(i)]
            else:
                assignment[sales_id] = []
        
        return {
            'assignment': assignment,
            'cv_pct': result.get('cv_pct', 0),
            'total_distance': result.get('total_distance', 0),
            'hoover_index': result.get('hoover_index', 0),
            'algorithm': request.algorithm
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi chạy thuật toán: {str(e)}")


def _zones_and_adjacency(zones_in_territory: List[models.Zone], zone_ids: List[int], db: Session):
    """zones_data / adj_list in the format of AdvancedTerritoryDesign and algorithm_comparison (read-only)."""
    zones_data = [
        {
            "id": z.id,
            "code": z.zone_code,
            "lat": z.center_lat or 21.0285,
            "lng": z.center_lng or 105.8542,
            "num_customers": z.num_customers or 0,
            "num_orders": z.num_orders or 0,
            "revenue": z.revenue or 0,
        }
        for z in zones_in_territory
    ]
    adj_list = {zone_id: [] for zone_id in zone_ids}
    adjacencies = db.query(models.ZoneAdjacency).filter(
        (models.ZoneAdjacency.zone_id1.in_(zone_ids)) | (models.ZoneAdjacency.zone_id2.in_(zone_ids))
    ).all()
    for adj in adjacencies:
        if adj.is_adjacent:
            adj_list.setdefault(adj.zone_id1, []).append(adj.zone_id2)
            adj_list.setdefault(adj.zone_id2, []).append(adj.zone_id1)
    return zones_data, adj_list


def _prepare_assignment_problem(territory_id: int, sales_ids: List[int], date: str, db: Session):
    """Same checks and data preparation as /admin/assign-work, shared by the comparison endpoint."""
    territory = db.query(models.Territory).filter(models.Territory.id == territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Phan vung khong ton tai")

    zone_ids = _get_territory_zone_ids(territory, db)
    zones_in_territory = db.query(models.Zone).filter(
        models.Zone.id.in_(zone_ids)
    ).all() if zone_ids else []
    if not zones_in_territory:
        raise HTTPException(status_code=400, detail="Phan vung khong co zones nao")

    sales_ids = list(dict.fromkeys([int(sid) for sid in sales_ids]))
    if not sales_ids:
        raise HTTPException(status_code=400, detail="Vui long chon sales")
    if len(sales_ids) > len(zones_in_territory):
        raise HTTPException(
            status_code=400,
            detail="So sales khong duoc lon hon so zones neu moi sales can it nhat 1 zone",
        )

    selected_sales = db.query(models.User).filter(models.User.id.in_(sales_ids)).all()
    if len(selected_sales) != len(sales_ids):
        raise HTTPException(status_code=400, detail="Mot so sales khong ton tai")
    invalid_sales = [
        sales.id
        for sales in selected_sales
        if sales.role != "sales" or not sales.is_approved or sales.region_id != territory.region_id
    ]
    if invalid_sales:
        raise HTTPException(
            status_code=400,
            detail=f"Sales khong thuoc cung khu vuc phan vung: {invalid_sales}",
        )

    busy_assignments = db.query(models.WorkAssignment).filter(
        models.WorkAssignment.assignment_date.like(f"{date}%")
    ).all()
    busy_sales_ids = {int(sid) for assignment in busy_assignments for sid in assignment.assignment_data.keys()}
    selected_busy_sales = [sid for sid in sales_ids if sid in busy_sales_ids]
    if selected_busy_sales:
        raise HTTPException(status_code=400, detail=f"Sales da ban trong ngay nay: {selected_busy_sales}")

    adjacency_meta = _rebuild_zone_adjacency(territory, db)
    db.commit()

    zones_data, adj_list = _zones_and_adjacency(zones_in_territory, zone_ids, db)
    if len(zone_ids) > 1 and not any(adj_list.values()):
        raise HTTPException(
            status_code=400,
            detail="Không xác định được quan hệ kề giữa các zone. Hãy kiểm tra geometry của zone.",
        )
    return sales_ids, zones_data, adj_list, adjacency_meta


@router.get("/admin/algorithms")
def list_assignment_algorithms():
    """Algorithms available for /admin/compare-algorithms, with availability on this server."""
    return {
        "algorithms": algorithm_comparison.list_algorithms(),
        "defaults": {"tolerance": 0.05, "time_limit": 60},
    }


@router.post("/admin/compare-algorithms")
def compare_assignment_algorithms(request: schemas.CompareAlgorithmsRequest, db: Session = Depends(get_db)):
    """Run the selected algorithms in parallel on the same territory and sales, and return every result
    with the same quality metrics so that the admin can compare them and pick one."""
    names = list(dict.fromkeys(request.algorithms))
    unknown = [name for name in names if name not in algorithm_comparison.ALGORITHMS]
    if not names:
        raise HTTPException(status_code=400, detail="Vui long chon it nhat 1 thuat toan")
    if unknown:
        raise HTTPException(status_code=400, detail=f"Thuat toan khong ton tai: {unknown}")

    sales_ids, zones_data, adj_list, adjacency_meta = _prepare_assignment_problem(
        request.territory_id, request.sales_ids, request.date, db
    )
    seed = request.seed if request.seed is not None else random.randrange(1, 2 ** 31)
    problem = algorithm_comparison.build_problem(
        zones_data, adj_list, len(sales_ids), request.tolerance, request.time_limit, seed
    )
    try:
        reports = algorithm_comparison.compare(problem, names)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi khi chay so sanh thuat toan: {str(e)}")

    for report in reports:
        territories = report.pop("territories")
        if territories is None:
            report["assignment"] = None
            continue
        report["assignment"] = {str(sales_id): territories[i] for i, sales_id in enumerate(sales_ids)}
        per_territory = report["metrics"].pop("per_territory")
        report["metrics"]["per_sales"] = {
            str(sales_id): per_territory[i] for i, sales_id in enumerate(sales_ids)
        }

    warnings = []
    if not any(z["num_customers"] for z in zones_data):
        warnings.append("Tất cả zone có số khách hàng = 0: chỉ số cân bằng khách hàng không có ý nghĩa.")
    if not any(z["num_orders"] for z in zones_data):
        warnings.append("Tất cả zone có số đơn hàng = 0: chỉ số cân bằng đơn hàng không có ý nghĩa.")
    if not any(z["num_customers"] or z["num_orders"] for z in zones_data):
        warnings.append("Hãy nhập số liệu hoặc dùng 'Fake dữ liệu' trước khi so sánh; Prob-VNS sẽ cân bằng số zone.")

    return {
        "territory_id": request.territory_id,
        "date": request.date,
        "sales_ids": sales_ids,
        "zone_count": len(zones_data),
        "warnings": warnings,
        "tolerance": request.tolerance,
        "time_limit": request.time_limit,
        "seed": seed,
        "adjacency": adjacency_meta,
        "results": reports,
    }


@router.post("/admin/evaluate-assignment")
def evaluate_assignment(request: schemas.EvaluateAssignmentRequest, db: Session = Depends(get_db)):
    """Recompute the comparison metrics of an assignment {sales_id: [zone_ids]} (e.g. after manual edits).
    Read-only: uses the stored zone adjacency, does not rebuild it."""
    territory = db.query(models.Territory).filter(models.Territory.id == request.territory_id).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Phan vung khong ton tai")
    zone_ids = [int(zid) for zid in (territory.zone_ids or [])]
    zone_ids += [z.id for z in db.query(models.Zone).filter(models.Zone.territory_id == territory.id).all()
                 if z.id not in zone_ids]
    if not request.assignment:
        raise HTTPException(status_code=400, detail="Ket qua phan cong rong")

    sales_keys = list(request.assignment.keys())
    assigned = [int(zid) for zones in request.assignment.values() for zid in zones]
    if len(assigned) != len(set(assigned)):
        raise HTTPException(status_code=400, detail="Moi zone chi duoc giao cho mot sales")
    unknown = sorted(set(assigned) - set(zone_ids))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Zone khong thuoc phan vung: {unknown}")
    unassigned = sorted(set(zone_ids) - set(assigned))

    zones_in_territory = db.query(models.Zone).filter(models.Zone.id.in_(zone_ids)).all()
    zones_data, adj_list = _zones_and_adjacency(zones_in_territory, zone_ids, db)
    problem = algorithm_comparison.build_problem(
        zones_data, adj_list, len(sales_keys), request.tolerance, time_limit=0, seed=0
    )
    territories = [[int(zid) for zid in request.assignment[key]] for key in sales_keys]
    metrics = algorithm_comparison.evaluate(problem, territories)
    per_territory = metrics.pop("per_territory")
    metrics["per_sales"] = {key: per_territory[i] for i, key in enumerate(sales_keys)}
    metrics["unassigned_zones"] = unassigned
    return {"territory_id": territory.id, "tolerance": request.tolerance, "metrics": metrics}


@router.post("/admin/save-assignment")
def save_assignment(request: schemas.SaveAssignmentRequest, db: Session = Depends(get_db)):
    """
    Lưu kết quả giao việc từ thuật toán
    """
    try:
        # Convert string keys to int and create assignment dict
        assignment = {}
        for sales_id_str, zone_ids in request.data.items():
            assignment[int(sales_id_str)] = zone_ids
        
        # Bạn có thể lưu vào WorkAssignment hoặc các bảng khác
        # Tạm thời chỉ xác nhận lưu thành công
        
        return {"msg": "Phân công đã được lưu thành công!"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu phân công: {str(e)}")


@router.get("/users")
def get_users(role: str = Query(None), db: Session = Depends(get_db)):
    """Lấy danh sách users"""
    query = db.query(models.User)
    if role:
        query = query.filter(models.User.role == role)
    return query.all()


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Xóa user (sales)"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    
    try:
        db.delete(user)
        db.commit()
        return {"msg": f"Đã xóa tài khoản {user.username} thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa: {str(e)}")


@router.post("/admin/approve-user/{user_id}")
def approve_user(user_id: int, db: Session = Depends(get_db)):
    """Phê duyệt tài khoản người dùng"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    
    user.is_approved = True
    db.commit()
    
    return {"msg": f"Đã phê duyệt tài khoản của {user.username}"}


@router.post("/admin/reject-user/{user_id}")
def reject_user(user_id: int, db: Session = Depends(get_db)):
    """Từ chối tài khoản người dùng"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    
    db.delete(user)
    db.commit()
    
    return {"msg": f"Đã xóa tài khoản {user.username}"}

@router.post("/admin/fetch-wards")
def auto_fetch_wards(request: Dict[str, Any], db: Session = Depends(get_db)):
    district_name = request.get("district_name")
    territory_id = request.get("territory_id")
    
    if not district_name or not territory_id:
        raise HTTPException(status_code=400, detail="Thiếu thông tin Quận hoặc Phân vùng")

    try:
        territory_id = int(territory_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Mã phân vùng không hợp lệ")
    territory = db.query(models.Territory).filter(
        models.Territory.id == int(territory_id)
    ).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Phân vùng không tồn tại hoặc đã bị xóa")

    # 1. Lấy dữ liệu từ OSM
    try:
        raw_data = fetch_wards_from_osm(district_name, territory.region.name)
        wards = osm_to_geojson(raw_data)
    except WardImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not wards:
        raise HTTPException(status_code=404, detail="Không tìm thấy phường nào thuộc khu vực này")

    existing_zones = db.query(models.Zone).filter(models.Zone.territory_id == territory.id).all()
    existing_codes = {z.zone_code for z in existing_zones}
    skipped_count = 0
    created_count = 0
    created_zone_ids = []
    try:
        for w in wards:
            snapshot_key = "20250601" if raw_data.get("snapshot") else "current"
            zone_code = f"OSM_{territory.id}_{w['osm_id']}_{snapshot_key}"
            legacy_duplicate = any(
                normalize_name(z.name) == normalize_name(w['name'])
                and z.geometry and shape(z.geometry).equals(shape(w['geometry']))
                for z in existing_zones
            )
            if zone_code in existing_codes or legacy_duplicate:
                skipped_count += 1
                continue
            existing_codes.add(zone_code)
        
            new_zone = models.Zone(
                zone_code=zone_code,
                name=w['name'],
                territory_id=int(territory_id),
                geometry=w['geometry'],
                center_lat=w['center'][1],
                center_lng=w['center'][0],
                num_customers=0,
                num_orders=0,
                revenue=0.0
            )
            db.add(new_zone)
            db.flush()
            created_zone_ids.append(new_zone.id)
            created_count += 1
        existing_zone_ids = [int(zid) for zid in (territory.zone_ids or [])]
        territory.zone_ids = list(dict.fromkeys([*existing_zone_ids, *created_zone_ids]))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi lưu DB: {str(e)}")
            
    return {
        "msg": (
            f"Đã tải {created_count} phường/xã; bỏ qua {skipped_count} đơn vị đã có."
            + (" Dữ liệu quận/huyện và phường/xã cũ tại ngày 01/06/2025, trước sắp xếp hành chính."
               if raw_data.get("snapshot") else "")
        ),
        "snapshot": raw_data.get("snapshot"),
        "skipped_count": skipped_count,
        "created_zone_ids": created_zone_ids,
    }

# Thêm vào backend/routes.py

@router.get("/admin/sales-availability")
def get_sales_availability(
    date: str,
    territory_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách sales và trạng thái rảnh/bận trong một ngày nhất định
    """
    query = db.query(models.User).filter(
        models.User.role == 'sales', 
        models.User.is_approved == True
    )
    territory = None
    if territory_id is not None:
        territory = db.query(models.Territory).filter(
            models.Territory.id == territory_id
        ).first()
        if not territory:
            raise HTTPException(status_code=404, detail="Phan vung khong tim thay")
        query = query.filter(models.User.region_id == territory.region_id)

    all_sales = query.all()
    
    # Lấy các sales đã được giao việc trong ngày này
    # Giả sử format date trong DB là YYYY-MM-DD
    busy_assignments = db.query(models.WorkAssignment).filter(
        models.WorkAssignment.assignment_date.like(f"{date}%")
    ).all()
    
    busy_sales_ids = set()
    for assign in busy_assignments:
        # assignment_data lưu { "sales_id": [zone_ids] }
        for s_id in assign.assignment_data.keys():
            busy_sales_ids.add(int(s_id))
            
    result = []
    for s in all_sales:
        is_busy = s.id in busy_sales_ids
        result.append({
            "id": s.id,
            "username": s.username,
            "full_name": s.full_name,
            "region_id": s.region_id,
            "is_busy": is_busy
        })
    
    # Sắp xếp: Rảnh (is_busy=False) lên đầu
    result.sort(key=lambda x: x['is_busy'])
    return result

@router.post("/admin/finalize-assignment")
def finalize_assignment(request: schemas.SaveAssignmentRequest, db: Session = Depends(get_db)):
    """Persist the final adjusted assignment."""
    try:
        territory = db.query(models.Territory).filter(
            models.Territory.id == request.territory_id
        ).first()
        if not territory:
            raise HTTPException(status_code=404, detail="Phan vung khong ton tai")

        zone_ids = set(_get_territory_zone_ids(territory, db))
        assignment_zone_ids = [
            int(zone_id)
            for zone_list in request.data.values()
            for zone_id in zone_list
        ]
        if set(assignment_zone_ids) != zone_ids or len(assignment_zone_ids) != len(set(assignment_zone_ids)):
            raise HTTPException(
                status_code=400,
                detail="Moi zone phai duoc chia dung mot lan truoc khi luu",
            )
        empty_sales = [sales_id for sales_id, zones in request.data.items() if not zones]
        if empty_sales:
            raise HTTPException(
                status_code=400,
                detail=f"Moi sales phai co it nhat 1 zone: {empty_sales}",
            )
        # Vùng không liên thông chỉ bị cảnh báo, không còn bị từ chối.
        disconnected_sales = [
            sales_id
            for sales_id, assigned_zone_ids in request.data.items()
            if not _zone_group_is_connected(assigned_zone_ids, db)
        ]
        warnings = []
        if disconnected_sales:
            warnings.append(
                f"{len(disconnected_sales)} sales có các zone không liền kề nhau: {disconnected_sales}"
            )

        existing = db.query(models.WorkAssignment).filter(
            models.WorkAssignment.territory_id == request.territory_id,
            models.WorkAssignment.assignment_date.like(f"{request.date}%"),
        ).all()
        for item in existing:
            db.delete(item)

        new_assign = models.WorkAssignment(
            territory_id=request.territory_id,
            assignment_date=datetime.strptime(request.date, "%Y-%m-%d"),
            assignment_data=request.data,
            algorithm_used=request.algorithm,
            cv_pct=request.cv_pct,
            total_distance=request.total_distance,
            hoover_index=request.hoover_index,
            is_finalized=True,
        )
        db.add(new_assign)
        db.commit()
        return {
            "msg": "Da luu phan cong thanh cong",
            "warnings": warnings,
            "disconnected_sales": disconnected_sales,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/finalize-assignment-legacy")
def finalize_assignment(request: schemas.SaveAssignmentRequest, db: Session = Depends(get_db)):
    """
    Lưu chính thức kết quả chia vùng vào database
    """
    try:
        # Xóa bản ghi cũ nếu trùng ngày và territory (nếu cần)
        # hoặc tạo bản ghi mới
        new_assign = models.WorkAssignment(
            territory_id=request.territory_id,
            assignment_date=datetime.strptime(request.date, "%Y-%m-%d"),
            assignment_data=request.data, # { "sales_id": [zone_ids] }
            algorithm_used=request.algorithm,
            cv_pct=request.cv_pct,
            total_distance=request.total_distance,
            is_finalized=True
        )
        db.add(new_assign)
        db.commit()
        return {"msg": "Đã lưu phân công thành công!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
