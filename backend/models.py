from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

# ============ USER MODELS ============
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin, sales, customer
    # is_approved: customer=True (auto-approved), sales=False (needs admin approval), admin=True (created by system)
    is_approved = Column(Boolean, default=False)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sales_territories = relationship("Territory", back_populates="sales_user", foreign_keys="Territory.sales_id")
    activities = relationship("ZoneActivity", back_populates="user")


# ============ ZONE & DISTRICT MODELS ============
class Zone(Base):
    """Basic units - các đơn vị cơ bản để chia phân vùng"""
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True)
    zone_code = Column(String, unique=True, nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"))
    name = Column(String, nullable=False)
    
    # Tọa độ (longitude, latitude hoặc GeoJSON)
    geometry = Column(JSON, nullable=True)  # GeoJSON format
    center_lat = Column(Float, nullable=True)
    center_lng = Column(Float, nullable=True)
    area_size = Column(Float, nullable=True)  # Diện tích (m2 hoặc km2)
    
    # Hoạt động và thông tin khách hàng
    num_customers = Column(Integer, default=0)
    num_orders = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    district = relationship("District", back_populates="zones")
    activity = relationship("ZoneActivity", uselist=False, back_populates="zone")
    adjacencies = relationship("ZoneAdjacency", foreign_keys="ZoneAdjacency.zone_id1", back_populates="zone1")
    distances = relationship("ZoneDistance", foreign_keys="ZoneDistance.zone_id1", back_populates="zone1")


class District(Base):
    """Huyện/quốc gia - chứa nhiều zones"""
    __tablename__ = "districts"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    center_lat = Column(Float, nullable=True)
    center_lng = Column(Float, nullable=True)
    total_area = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    zones = relationship("Zone", back_populates="district", cascade="all, delete-orphan")
    territories = relationship("Territory", back_populates="district")


# ============ ZONE ACTIVITY MODELS ============
class ZoneActivity(Base):
    """Thông tin hoạt động của từng zone"""
    __tablename__ = "zone_activities"

    id = Column(Integer, primary_key=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    
    # Thông tin khách hàng và đơn hàng
    num_customers = Column(Integer, default=0)
    num_orders = Column(Integer, default=0)
    avg_order_value = Column(Float, default=0.0)
    total_revenue = Column(Float, default=0.0)
    
    # Khác
    population_density = Column(Float, nullable=True)
    business_density = Column(Float, nullable=True)
    traffic_density = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    zone = relationship("Zone", back_populates="activity")
    user = relationship("User", back_populates="activities")


class ZoneAdjacency(Base):
    """Ma trận kề - các zones liền kề nhau"""
    __tablename__ = "zone_adjacencies"

    id = Column(Integer, primary_key=True)
    zone_id1 = Column(Integer, ForeignKey("zones.id"), nullable=False)
    zone_id2 = Column(Integer, ForeignKey("zones.id"), nullable=False)
    is_adjacent = Column(Boolean, default=True)  # True nếu hai zone liền kề
    
    # Relationships
    zone1 = relationship("Zone", foreign_keys=[zone_id1], back_populates="adjacencies")
    zone2 = relationship("Zone", foreign_keys=[zone_id2])


class ZoneDistance(Base):
    """Ma trận khoảng cách - khoảng cách giữa các zones"""
    __tablename__ = "zone_distances"

    id = Column(Integer, primary_key=True)
    zone_id1 = Column(Integer, ForeignKey("zones.id"), nullable=False)
    zone_id2 = Column(Integer, ForeignKey("zones.id"), nullable=False)
    distance = Column(Float, nullable=False)  # Tính bằng km
    travel_time = Column(Float, nullable=True)  # Tính bằng phút
    
    # Relationships
    zone1 = relationship("Zone", foreign_keys=[zone_id1], back_populates="distances")
    zone2 = relationship("Zone", foreign_keys=[zone_id2])


# ============ TERRITORY MODELS ============
class Territory(Base):
    """Phân vùng bán hàng được giao cho sales person"""
    __tablename__ = "territories"

    id = Column(Integer, primary_key=True)
    territory_code = Column(String, unique=True, nullable=False)
    sales_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    
    # Các zones trong phân vùng này
    zone_ids = Column(JSON, nullable=True)  # List of zone IDs
    
    # Thống kê
    num_zones = Column(Integer, default=0)
    num_customers = Column(Integer, default=0)
    num_orders = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    avg_distance = Column(Float, nullable=True)
    
    # Thuật toán được sử dụng
    algorithm_used = Column(String, nullable=True)  # kmeans, greedy, localsearch
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sales_user = relationship("User", back_populates="sales_territories", foreign_keys=[sales_id])
    district = relationship("District", back_populates="territories")


class TerritoryHistory(Base):
    """Lịch sử thay đổi phân vùng"""
    __tablename__ = "territory_histories"

    id = Column(Integer, primary_key=True)
    territory_id = Column(Integer, ForeignKey("territories.id"))
    action = Column(String, nullable=False)  # created, updated, zone_added, zone_removed
    changed_zones = Column(JSON, nullable=True)
    previous_zones = Column(JSON, nullable=True)
    changed_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)