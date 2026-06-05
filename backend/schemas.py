from pydantic import BaseModel, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import re

# ============ USER SCHEMAS ============
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str  # sales, customer (admin cannot be created through registration)
    full_name: Optional[str] = None
    phone: Optional[str] = None

    @validator('role')
    def validate_role(cls, v):
        if v not in ['sales', 'customer']:
            raise ValueError('Role phải là sales hoặc customer. Admin phải được tạo bởi hệ thống.')
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Mật khẩu phải có ít nhất 8 ký tự')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 ký tự in hoa')
        if not re.search(r'[0-9]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 chữ số')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt')
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    full_name: Optional[str]
    phone: Optional[str]
    region_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminCreateSales(BaseModel):
    """Admin creates sales account directly"""
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    region_id: Optional[int] = None  # Khu vực cho sales

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Mật khẩu phải có ít nhất 8 ký tự')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 ký tự in hoa')
        if not re.search(r'[0-9]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 chữ số')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt')
        return v


class AdminUpdateSales(BaseModel):
    """Admin updates an existing sales account"""
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    region_id: Optional[int] = None


class AdminCreateAdmin(BaseModel):
    """Admin creates another admin account"""
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Mật khẩu phải có ít nhất 8 ký tự')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 ký tự in hoa')
        if not re.search(r'[0-9]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 chữ số')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt')
        return v


class ApproveSalesRequest(BaseModel):
    """Admin approves or rejects sales registration"""
    user_id: int
    is_approved: bool


# ============ REGION SCHEMAS ============
class RegionCreate(BaseModel):
    name: str  # Tên khu vực (Hà Nội, TP HCM, ...)


class RegionUpdate(BaseModel):
    name: Optional[str] = None


class RegionResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RegionDetailResponse(BaseModel):
    id: int
    name: str
    territories: List["TerritoryDetailResponse"] = []
    sales_users: List[UserResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class AssignRegionToSalesRequest(BaseModel):
    sales_id: int
    region_id: Optional[int] = None  # None để xóa khu vực


# ============ ZONE SCHEMAS ============
class ZoneActivityCreate(BaseModel):
    num_customers: int
    num_orders: int
    avg_order_value: float
    total_revenue: float
    population_density: Optional[float] = None
    business_density: Optional[float] = None
    traffic_density: Optional[float] = None
    notes: Optional[str] = None


class ZoneActivityUpdate(BaseModel):
    num_customers: Optional[int] = None
    num_orders: Optional[int] = None
    avg_order_value: Optional[float] = None
    total_revenue: Optional[float] = None
    population_density: Optional[float] = None
    business_density: Optional[float] = None
    traffic_density: Optional[float] = None
    notes: Optional[str] = None


class ZoneActivityResponse(BaseModel):
    id: int
    zone_id: int
    num_customers: int
    num_orders: int
    avg_order_value: float
    total_revenue: float
    updated_at: datetime

    class Config:
        from_attributes = True


class ZoneCreate(BaseModel):
    zone_code: str
    territory_id: int
    name: str
    geometry: Optional[Dict[str, Any]] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    area_size: Optional[float] = None
    num_customers: int = 0
    num_orders: int = 0
    revenue: float = 0.0


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    area_size: Optional[float] = None
    num_customers: Optional[int] = None
    num_orders: Optional[int] = None
    revenue: Optional[float] = None


class ZoneResponse(BaseModel):
    id: int
    zone_code: str
    territory_id: int
    name: str
    center_lat: Optional[float]
    center_lng: Optional[float]
    num_customers: int
    num_orders: int
    revenue: float
    created_at: datetime

    class Config:
        from_attributes = True


class ZoneMetricsUpdate(BaseModel):
    num_customers: int
    num_orders: int
    revenue: float
    notes: Optional[str] = None


# ============ DISTRICT SCHEMAS ============
class DistrictCreate(BaseModel):
    code: str
    name: str
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    total_area: Optional[float] = None


class DistrictResponse(BaseModel):
    id: int
    code: str
    name: str
    center_lat: Optional[float]
    center_lng: Optional[float]
    total_area: Optional[float]
    zones: List[ZoneResponse] = []

    class Config:
        from_attributes = True


# ============ TERRITORY SCHEMAS ============
class TerritoryCreate(BaseModel):
    name: str
    region_id: int  # Khu vực cho phân vùng
    zone_ids: List[int]

    source_territory_ids: List[int] = []


class TerritoryUpdate(BaseModel):
    name: Optional[str] = None
    region_id: Optional[int] = None
    zone_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None


class TerritoryResponse(BaseModel):
    id: int
    name: str
    region_id: Optional[int] = None
    parent_territory_id: Optional[int] = None
    version_no: int = 1
    zone_ids: List[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TerritoryDetailResponse(BaseModel):
    id: int
    name: str
    region_id: int
    parent_territory_id: Optional[int] = None
    version_no: int = 1
    zone_ids: List[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TerritoryVersionCreate(BaseModel):
    name: Optional[str] = None


# ============ ALGORITHM SCHEMAS ============
class KMeansInput(BaseModel):
    territory_id: int
    num_clusters: int
    max_iterations: int = 100


class GreedySeedInput(BaseModel):
    territory_id: int
    num_territories: int
    max_zones_per_territory: int = 50


class LocalSearchInput(BaseModel):
    territory_id: int
    swap_iterations: int = 10


class AlgorithmResult(BaseModel):
    territories: List[TerritoryResponse]
    algorithm: str
    execution_time: float
    quality_score: float
    message: str


# ============ WORK ASSIGNMENT SCHEMAS ============
class AssignWorkRequest(BaseModel):
    """Request to assign work using algorithm"""
    territory_id: int
    sales_ids: List[int]
    date: str  # YYYY-MM-DD
    algorithm: str  # local_search, tabu_search, grasp


class WorkAssignmentResponse(BaseModel):
    """Response from work assignment"""
    assignment: Dict[int, List[int]]  # {sales_id: [zone_ids], ...}
    cv_pct: float
    total_distance: float
    hoover_index: float
    algorithm: str


class SaveAssignmentRequest(BaseModel):
    """Request to save/finalize assignment"""
    territory_id: int
    date: str
    algorithm: str = "manual_adjusted"
    cv_pct: Optional[float] = None
    total_distance: Optional[float] = None
    hoover_index: Optional[float] = None
    # {sales_id: [zone_ids], ...}
    data: Dict[str, List[int]]
