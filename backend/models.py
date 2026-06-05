from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

# ============ REGION MODEL ============
class Region(Base):
    __tablename__ = "regions"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # Hà Nội, TP HCM, v.v.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    territories = relationship("Territory", back_populates="region")
    sales_users = relationship("User", back_populates="region")

# ============ USER MODELS (GIỮ LẠI) ============
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin, sales, customer
    is_approved = Column(Boolean, default=False)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True)  # Chỉ áp dụng cho sales
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    region = relationship("Region", back_populates="sales_users")
    activities = relationship("ZoneActivity", back_populates="user")

# ============ ZONE MODELS ============
class Zone(Base):
    __tablename__ = "zones"
    id = Column(Integer, primary_key=True)
    zone_code = Column(String, unique=True, nullable=False)
    
    # THAY ĐỔI: district_id -> territory_id
    territory_id = Column(Integer, ForeignKey("territories.id"), nullable=True)
    
    name = Column(String, nullable=False)
    geometry = Column(JSON, nullable=True)
    center_lat = Column(Float, nullable=True)
    center_lng = Column(Float, nullable=True)
    area_size = Column(Float, nullable=True)
    num_customers = Column(Integer, default=0)
    num_orders = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    territory = relationship("Territory", back_populates="zones")
    activities = relationship("ZoneActivity", back_populates="zone", order_by="desc(ZoneActivity.updated_at)")
    adjacencies = relationship("ZoneAdjacency", foreign_keys="ZoneAdjacency.zone_id1", back_populates="zone1")
    distances = relationship("ZoneDistance", foreign_keys="ZoneDistance.zone_id1", back_populates="zone1")

# ============ ZONE SUPPORT MODELS ============
class ZoneActivity(Base):
    __tablename__ = "zone_activities"
    id = Column(Integer, primary_key=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    num_customers = Column(Integer, default=0)
    num_orders = Column(Integer, default=0)
    avg_order_value = Column(Float, default=0.0)
    total_revenue = Column(Float, default=0.0)
    population_density = Column(Float, nullable=True)
    business_density = Column(Float, nullable=True)
    traffic_density = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow)
    zone = relationship("Zone", back_populates="activities")
    user = relationship("User", back_populates="activities")

class ZoneAdjacency(Base):
    __tablename__ = "zone_adjacencies"
    id = Column(Integer, primary_key=True)
    zone_id1 = Column(Integer, ForeignKey("zones.id"), nullable=False)
    zone_id2 = Column(Integer, ForeignKey("zones.id"), nullable=False)
    is_adjacent = Column(Boolean, default=True)
    zone1 = relationship("Zone", foreign_keys=[zone_id1], back_populates="adjacencies")
    zone2 = relationship("Zone", foreign_keys=[zone_id2])

class ZoneDistance(Base):
    __tablename__ = "zone_distances"
    id = Column(Integer, primary_key=True)
    zone_id1 = Column(Integer, ForeignKey("zones.id"), nullable=False)
    zone_id2 = Column(Integer, ForeignKey("zones.id"), nullable=False)
    distance = Column(Float, nullable=False)
    zone1 = relationship("Zone", foreign_keys=[zone_id1], back_populates="distances")
    zone2 = relationship("Zone", foreign_keys=[zone_id2])

# ============ TERRITORY MODELS ============
class Territory(Base):
    __tablename__ = "territories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    parent_territory_id = Column(Integer, ForeignKey("territories.id"), nullable=True)
    version_no = Column(Integer, default=1)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)  # Phân vùng thuộc khu vực nào
    zone_ids = Column(JSON, nullable=True) # Giữ lại để hỗ trợ logic cũ nếu cần
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    region = relationship("Region", back_populates="territories")
    parent = relationship("Territory", remote_side=[id])
    zones = relationship("Zone", back_populates="territory")
    work_assignments = relationship("WorkAssignment", back_populates="territory")

class WorkAssignment(Base):
    __tablename__ = "work_assignments"
    id = Column(Integer, primary_key=True)
    territory_id = Column(Integer, ForeignKey("territories.id"), nullable=False)
    assignment_date = Column(DateTime, nullable=False)
    assignment_data = Column(JSON, nullable=False)
    algorithm_used = Column(String, nullable=False)
    cv_pct = Column(Float, nullable=True)
    total_distance = Column(Float, nullable=True)
    hoover_index = Column(Float, nullable=True)
    is_finalized = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    territory = relationship("Territory", back_populates="work_assignments")
