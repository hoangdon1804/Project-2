from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_

import models
import schemas
import auth
from database import SessionLocal
from algorithms import KMeansClustering, GreedySeedGrowth, LocalSearch
from typing import List, Dict, Any

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ AUTH ROUTES ============
@router.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Register new user
    - customer: auto-approved (is_approved = True)
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

        # Determine approval status based on role
        is_approved = (user.role == 'customer')  # Only customer is auto-approved

        new_user = models.User(
            username=user.username,
            email=user.email,
            password=hashed,
            role=user.role,
            full_name=user.full_name,
            phone=user.phone,
            is_approved=is_approved
        )

        db.add(new_user)
        db.commit()
        
        # Different messages based on role
        if user.role == 'customer':
            msg = "Đăng ký thành công! Bạn có thể đăng nhập ngay."
        else:  # sales
            msg = "Đăng ký thành công! Vui lòng chờ admin duyệt tài khoản của bạn."
        
        return {"msg": msg}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(
        models.User.username == user.username
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
        
        hashed = auth.hash_password(user_data.password)

        new_sales = models.User(
            username=user_data.username,
            email=user_data.email,
            password=hashed,
            role='sales',
            full_name=user_data.full_name,
            phone=user_data.phone,
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


# ============ DISTRICT ROUTES ============
@router.post("/districts")
def create_district(district: schemas.DistrictCreate, db: Session = Depends(get_db)):
    """Tạo district"""
    existing = db.query(models.District).filter(
        models.District.code == district.code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mã quận đã tồn tại")
    
    new_district = models.District(
        code=district.code,
        name=district.name,
        center_lat=district.center_lat,
        center_lng=district.center_lng,
        total_area=district.total_area
    )
    db.add(new_district)
    db.commit()
    return new_district


@router.get("/districts")
def get_districts(db: Session = Depends(get_db)):
    """Lấy danh sách districts"""
    districts = db.query(models.District).all()
    return districts


@router.get("/districts/{district_id}")
def get_district(district_id: int, db: Session = Depends(get_db)):
    """Lấy chi tiết district"""
    district = db.query(models.District).filter(
        models.District.id == district_id
    ).first()
    
    if not district:
        raise HTTPException(status_code=404, detail="District không tìm thấy")
    
    return district


@router.delete("/districts/{district_id}")
def delete_district(district_id: int, db: Session = Depends(get_db)):
    """Xóa district và tất cả zones, activities, territories liên quan"""
    district = db.query(models.District).filter(
        models.District.id == district_id
    ).first()
    
    if not district:
        raise HTTPException(status_code=404, detail="District không tìm thấy")
    
    # 1. Xóa tất cả territories liên quan
    territories = db.query(models.Territory).filter(
        models.Territory.district_id == district_id
    ).all()
    for territory in territories:
        db.delete(territory)
    
    # 2. Xóa tất cả zones và activities liên quan
    zones = db.query(models.Zone).filter(
        models.Zone.district_id == district_id
    ).all()
    
    for zone in zones:
        # Xóa zone activities
        activities = db.query(models.ZoneActivity).filter(
            models.ZoneActivity.zone_id == zone.id
        ).all()
        for activity in activities:
            db.delete(activity)
        
        # Xóa zone adjacencies
        adjacencies = db.query(models.ZoneAdjacency).filter(
            (models.ZoneAdjacency.zone_id1 == zone.id) | (models.ZoneAdjacency.zone_id2 == zone.id)
        ).all()
        for adjacency in adjacencies:
            db.delete(adjacency)
        
        # Xóa zone distances
        distances = db.query(models.ZoneDistance).filter(
            (models.ZoneDistance.zone_id1 == zone.id) | (models.ZoneDistance.zone_id2 == zone.id)
        ).all()
        for distance in distances:
            db.delete(distance)
        
        # Xóa zone
        db.delete(zone)
    
    # 3. Xóa district
    db.delete(district)
    db.commit()
    
    return {"msg": "Đã xóa District và tất cả dữ liệu liên quan thành công"}


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
        district_id=zone.district_id,
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
    return new_zone


@router.get("/zones")
def get_zones(district_id: int = Query(None), db: Session = Depends(get_db)):
    """Lấy danh sách zones"""
    query = db.query(models.Zone)
    if district_id:
        query = query.filter(models.Zone.district_id == district_id)
    return query.all()


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


@router.post("/zones/{zone_id}/activities")
def create_zone_activity(zone_id: int, activity: schemas.ZoneActivityCreate, 
                        db: Session = Depends(get_db)):
    """Tạo hoạt động cho zone"""
    zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone không tìm thấy")
    
    # Xóa activity cũ nếu có
    existing = db.query(models.ZoneActivity).filter(
        models.ZoneActivity.zone_id == zone_id
    ).first()
    
    if existing:
        db.delete(existing)
    
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
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Hoạt động zone không tìm thấy")
    
    return activity

@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    """Xóa zone và các activity liên quan"""
    zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone không tìm thấy")
    
    # 1. Xóa Activity của Zone này (nếu có) để tránh lỗi khóa ngoại (Foreign Key)
    activity = db.query(models.ZoneActivity).filter(models.ZoneActivity.zone_id == zone_id).first()
    if activity:
        db.delete(activity)
        
    # 2. Xóa Zone
    db.delete(zone)
    db.commit()
    return {"msg": "Đã xóa Zone thành công"}

# ============ ZONE ADJACENCY & DISTANCE ROUTES ============
@router.post("/zones/adjacency")
def create_adjacency(zone_id1: int, zone_id2: int, db: Session = Depends(get_db)):
    """Đánh dấu 2 zones liền kề"""
    adj = models.ZoneAdjacency(
        zone_id1=zone_id1,
        zone_id2=zone_id2,
        is_adjacent=True
    )
    db.add(adj)
    db.commit()
    return adj


@router.post("/zones/distance")
def create_distance(zone_id1: int, zone_id2: int, distance: float, 
                   travel_time: float = None, db: Session = Depends(get_db)):
    """Tạo khoảng cách giữa 2 zones"""
    dist = models.ZoneDistance(
        zone_id1=zone_id1,
        zone_id2=zone_id2,
        distance=distance,
        travel_time=travel_time
    )
    db.add(dist)
    db.commit()
    return dist


@router.get("/districts/{district_id}/adjacency-matrix")
def get_adjacency_matrix(district_id: int, db: Session = Depends(get_db)):
    """Lấy ma trận kề của district"""
    zones = db.query(models.Zone).filter(
        models.Zone.district_id == district_id
    ).all()
    
    zone_ids = [z.id for z in zones]
    n = len(zone_ids)
    
    # Khởi tạo ma trận 0
    matrix = [[0] * n for _ in range(n)]
    
    # Điền thông tin adjacency
    adjacencies = db.query(models.ZoneAdjacency).filter(
        models.ZoneAdjacency.zone_id1.in_(zone_ids),
        models.ZoneAdjacency.zone_id2.in_(zone_ids)
    ).all()
    
    id_to_idx = {zid: i for i, zid in enumerate(zone_ids)}
    
    for adj in adjacencies:
        if adj.zone_id1 in id_to_idx and adj.zone_id2 in id_to_idx:
            i, j = id_to_idx[adj.zone_id1], id_to_idx[adj.zone_id2]
            matrix[i][j] = 1
            matrix[j][i] = 1
    
    return {
        'zone_ids': zone_ids,
        'matrix': matrix
    }


@router.get("/districts/{district_id}/distance-matrix")
def get_distance_matrix(district_id: int, db: Session = Depends(get_db)):
    """Lấy ma trận khoảng cách của district"""
    zones = db.query(models.Zone).filter(
        models.Zone.district_id == district_id
    ).all()
    
    zone_ids = [z.id for z in zones]
    n = len(zone_ids)
    
    # Khởi tạo ma trận
    matrix = [[0.0] * n for _ in range(n)]
    
    # Điền thông tin distance
    distances = db.query(models.ZoneDistance).filter(
        models.ZoneDistance.zone_id1.in_(zone_ids),
        models.ZoneDistance.zone_id2.in_(zone_ids)
    ).all()
    
    id_to_idx = {zid: i for i, zid in enumerate(zone_ids)}
    
    for dist in distances:
        if dist.zone_id1 in id_to_idx and dist.zone_id2 in id_to_idx:
            i, j = id_to_idx[dist.zone_id1], id_to_idx[dist.zone_id2]
            matrix[i][j] = dist.distance
            matrix[j][i] = dist.distance
    
    return {
        'zone_ids': zone_ids,
        'matrix': matrix
    }


# ============ TERRITORY ROUTES ============
@router.post("/territories")
def create_territory(territory: schemas.TerritoryCreate, db: Session = Depends(get_db)):
    """Tạo phân vùng"""
    existing = db.query(models.Territory).filter(
        models.Territory.territory_code == territory.territory_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mã phân vùng đã tồn tại")
    
    # Tính thống kê
    zones = db.query(models.Zone).filter(models.Zone.id.in_(territory.zone_ids)).all()
    num_customers = sum(z.num_customers for z in zones)
    num_orders = sum(z.num_orders for z in zones)
    total_revenue = sum(z.revenue for z in zones)
    
    new_territory = models.Territory(
        territory_code=territory.territory_code,
        sales_id=territory.sales_id,
        district_id=territory.district_id,
        zone_ids=territory.zone_ids,
        num_zones=len(territory.zone_ids),
        num_customers=num_customers,
        num_orders=num_orders,
        total_revenue=total_revenue,
        algorithm_used=territory.algorithm_used
    )
    
    db.add(new_territory)
    db.commit()
    return new_territory


@router.get("/territories")
def get_territories(sales_id: int = Query(None), district_id: int = Query(None),
                   db: Session = Depends(get_db)):
    """Lấy danh sách phân vùng"""
    query = db.query(models.Territory)
    if sales_id:
        query = query.filter(models.Territory.sales_id == sales_id)
    if district_id:
        query = query.filter(models.Territory.district_id == district_id)
    return query.all()


@router.get("/territories/{territory_id}")
def get_territory(territory_id: int, db: Session = Depends(get_db)):
    """Lấy chi tiết phân vùng"""
    territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id
    ).first()
    if not territory:
        raise HTTPException(status_code=404, detail="Phân vùng không tìm thấy")
    return territory


@router.put("/territories/{territory_id}")
def update_territory(territory_id: int, territory: schemas.TerritoryUpdate, 
                    db: Session = Depends(get_db)):
    """Cập nhật phân vùng"""
    db_territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id
    ).first()
    if not db_territory:
        raise HTTPException(status_code=404, detail="Phân vùng không tìm thấy")
    
    if territory.zone_ids:
        zones = db.query(models.Zone).filter(models.Zone.id.in_(territory.zone_ids)).all()
        db_territory.zone_ids = territory.zone_ids
        db_territory.num_zones = len(territory.zone_ids)
        db_territory.num_customers = sum(z.num_customers for z in zones)
        db_territory.num_orders = sum(z.num_orders for z in zones)
        db_territory.total_revenue = sum(z.revenue for z in zones)
    
    if territory.is_active is not None:
        db_territory.is_active = territory.is_active
    
    db.commit()
    return db_territory


@router.delete("/territories/{territory_id}")
def delete_territory(territory_id: int, db: Session = Depends(get_db)):
    """Xóa phân vùng"""
    territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id
    ).first()
    
    if not territory:
        raise HTTPException(status_code=404, detail="Phân vùng không tìm thấy")
    
    db.delete(territory)
    db.commit()
    
    return {"msg": "Đã xóa Territory thành công"}


# ============ ALGORITHM ROUTES ============
@router.post("/algorithms/kmeans")
def run_kmeans(input_data: schemas.KMeansInput, db: Session = Depends(get_db)):
    """Chạy thuật toán K-means Clustering"""
    try:
        # Lấy zones của district
        zones = db.query(models.Zone).filter(
            models.Zone.district_id == input_data.district_id
        ).all()
        
        if not zones:
            raise HTTPException(status_code=404, detail="Không tìm thấy zones trong district")
        
        # Chuẩn bị dữ liệu cho thuật toán
        zones_data = [
            {
                'id': z.id,
                'code': z.zone_code,
                'lat': z.center_lat or 0,
                'lng': z.center_lng or 0,
                'num_customers': z.num_customers,
                'num_orders': z.num_orders,
                'revenue': z.revenue
            }
            for z in zones
        ]
        
        # Lấy ma trận khoảng cách
        distances = db.query(models.ZoneDistance).filter(
            models.ZoneDistance.zone_id1.in_([z.id for z in zones]),
            models.ZoneDistance.zone_id2.in_([z.id for z in zones])
        ).all()
        
        distance_dict = {}
        for d in distances:
            if d.zone_id1 not in distance_dict:
                distance_dict[d.zone_id1] = {}
            distance_dict[d.zone_id1][d.zone_id2] = d.distance
        
        # Chạy thuật toán
        algo = KMeansClustering(zones_data, distance_dict)
        result = algo.solve(input_data.num_clusters, input_data.max_iterations)
        
        # Lưu territories vào DB
        saved_territories = []
        for i, (territory_id, zone_ids) in enumerate(result['territories'].items()):
            # Chọn sales ngẫu nhiên hoặc để trống
            sales_users = db.query(models.User).filter(
                models.User.role == 'sales'
            ).all()
            
            sales_id = sales_users[i % len(sales_users)].id if sales_users else None
            
            territory = models.Territory(
                territory_code=f"KMEANS_{input_data.district_id}_{i}",
                sales_id=sales_id,
                district_id=input_data.district_id,
                zone_ids=zone_ids,
                num_zones=len(zone_ids),
                algorithm_used='kmeans'
            )
            
            # Tính thống kê
            zones_in_territory = db.query(models.Zone).filter(
                models.Zone.id.in_(zone_ids)
            ).all()
            territory.num_customers = sum(z.num_customers for z in zones_in_territory)
            territory.num_orders = sum(z.num_orders for z in zones_in_territory)
            territory.total_revenue = sum(z.revenue for z in zones_in_territory)
            
            db.add(territory)
            saved_territories.append(territory)
        
        db.commit()
        
        return {
            'algorithm': 'kmeans',
            'execution_time': result['execution_time'],
            'quality_score': result['quality_score'],
            'num_territories': len(result['territories']),
            'territories': [t.id for t in saved_territories],
            'message': result['message']
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/algorithms/greedy")
def run_greedy(input_data: schemas.GreedySeedInput, db: Session = Depends(get_db)):
    """Chạy thuật toán Greedy Seed Growth"""
    try:
        # Lấy zones của district
        zones = db.query(models.Zone).filter(
            models.Zone.district_id == input_data.district_id
        ).all()
        
        if not zones:
            raise HTTPException(status_code=404, detail="Không tìm thấy zones trong district")
        
        # Chuẩn bị dữ liệu
        zones_data = [
            {
                'id': z.id,
                'code': z.zone_code,
                'lat': z.center_lat or 0,
                'lng': z.center_lng or 0,
                'num_customers': z.num_customers,
                'num_orders': z.num_orders,
                'revenue': z.revenue
            }
            for z in zones
        ]
        
        distance_dict = {}
        distances = db.query(models.ZoneDistance).filter(
            models.ZoneDistance.zone_id1.in_([z.id for z in zones]),
            models.ZoneDistance.zone_id2.in_([z.id for z in zones])
        ).all()
        
        for d in distances:
            if d.zone_id1 not in distance_dict:
                distance_dict[d.zone_id1] = {}
            distance_dict[d.zone_id1][d.zone_id2] = d.distance
        
        # Chạy thuật toán
        algo = GreedySeedGrowth(zones_data, distance_dict)
        result = algo.solve(input_data.num_territories, input_data.max_zones_per_territory)
        
        # Lưu territories
        saved_territories = []
        for i, (territory_id, zone_ids) in enumerate(result['territories'].items()):
            sales_users = db.query(models.User).filter(
                models.User.role == 'sales'
            ).all()
            
            sales_id = sales_users[i % len(sales_users)].id if sales_users else None
            
            territory = models.Territory(
                territory_code=f"GREEDY_{input_data.district_id}_{i}",
                sales_id=sales_id,
                district_id=input_data.district_id,
                zone_ids=zone_ids,
                num_zones=len(zone_ids),
                algorithm_used='greedy'
            )
            
            zones_in_territory = db.query(models.Zone).filter(
                models.Zone.id.in_(zone_ids)
            ).all()
            territory.num_customers = sum(z.num_customers for z in zones_in_territory)
            territory.num_orders = sum(z.num_orders for z in zones_in_territory)
            territory.total_revenue = sum(z.revenue for z in zones_in_territory)
            
            db.add(territory)
            saved_territories.append(territory)
        
        db.commit()
        
        return {
            'algorithm': 'greedy',
            'execution_time': result['execution_time'],
            'quality_score': result['quality_score'],
            'num_territories': len(result['territories']),
            'territories': [t.id for t in saved_territories],
            'message': result['message']
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/algorithms/localsearch")
def run_local_search(input_data: schemas.LocalSearchInput, db: Session = Depends(get_db)):
    """Chạy thuật toán Local Search"""
    try:
        # Lấy territory hiện tại
        territory = db.query(models.Territory).filter(
            models.Territory.id == input_data.territory_id
        ).first()
        
        if not territory:
            raise HTTPException(status_code=404, detail="Phân vùng không tìm thấy")
        
        # Lấy tất cả zones của district này
        district_zones = db.query(models.Zone).filter(
            models.Zone.district_id == territory.district_id
        ).all()
        
        # Lấy tất cả territories của district
        all_territories = db.query(models.Territory).filter(
            models.Territory.district_id == territory.district_id,
            models.Territory.is_active == True
        ).all()
        
        # Chuẩn bị dữ liệu
        zones_data = [
            {
                'id': z.id,
                'code': z.zone_code,
                'lat': z.center_lat or 0,
                'lng': z.center_lng or 0,
                'num_customers': z.num_customers,
                'num_orders': z.num_orders,
                'revenue': z.revenue
            }
            for z in district_zones
        ]
        
        distance_dict = {}
        distances = db.query(models.ZoneDistance).all()
        for d in distances:
            if d.zone_id1 not in distance_dict:
                distance_dict[d.zone_id1] = {}
            distance_dict[d.zone_id1][d.zone_id2] = d.distance
        
        # Chuẩn bị initial territories
        initial_territories = {t.id: t.zone_ids for t in all_territories}
        
        # Chạy thuật toán
        algo = LocalSearch(zones_data, distance_dict)
        result = algo.solve(initial_territories, input_data.swap_iterations)
        
        # Cập nhật territories trong DB
        for t in all_territories:
            if t.id in result['territories']:
                new_zone_ids = result['territories'][t.id]
                t.zone_ids = new_zone_ids
                t.num_zones = len(new_zone_ids)
                
                zones_in_territory = db.query(models.Zone).filter(
                    models.Zone.id.in_(new_zone_ids)
                ).all()
                t.num_customers = sum(z.num_customers for z in zones_in_territory)
                t.num_orders = sum(z.num_orders for z in zones_in_territory)
                t.total_revenue = sum(z.revenue for z in zones_in_territory)
        
        db.commit()
        
        return {
            'algorithm': 'localsearch',
            'execution_time': result['execution_time'],
            'quality_score': result['quality_score'],
            'iterations': result['iterations'],
            'message': result['message']
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============ SALES ROUTES ============
@router.get("/sales/{sales_id}/territories")
def get_sales_territories(sales_id: int, db: Session = Depends(get_db)):
    """Lấy phân vùng của sales person"""
    territories = db.query(models.Territory).filter(
        models.Territory.sales_id == sales_id,
        models.Territory.is_active == True
    ).all()
    
    return territories


@router.get("/sales/{sales_id}/dashboard")
def get_sales_dashboard(sales_id: int, db: Session = Depends(get_db)):
    """Lấy dashboard cho sales person"""
    territories = db.query(models.Territory).filter(
        models.Territory.sales_id == sales_id,
        models.Territory.is_active == True
    ).all()
    
    total_customers = sum(t.num_customers for t in territories)
    total_orders = sum(t.num_orders for t in territories)
    total_revenue = sum(t.total_revenue for t in territories)
    total_zones = sum(t.num_zones for t in territories)
    
    return {
        'sales_id': sales_id,
        'num_territories': len(territories),
        'total_zones': total_zones,
        'total_customers': total_customers,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'territories': territories
    }


# ============ ADMIN ROUTES ============
@router.get("/admin/statistics")
def get_admin_statistics(db: Session = Depends(get_db)):
    """Lấy thống kê cho admin"""
    total_zones = db.query(models.Zone).count()
    total_territories = db.query(models.Territory).filter(
        models.Territory.is_active == True
    ).count()
    total_sales = db.query(models.User).filter(models.User.role == 'sales').count()
    total_customers = db.query(models.User).filter(models.User.role == 'customer').count()
    
    all_zones = db.query(models.Zone).all()
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


@router.get("/users")
def get_users(role: str = Query(None), db: Session = Depends(get_db)):
    """Lấy danh sách users"""
    query = db.query(models.User)
    if role:
        query = query.filter(models.User.role == role)
    return query.all()



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

