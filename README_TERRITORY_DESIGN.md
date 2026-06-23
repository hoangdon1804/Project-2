# Commercial Territory Design System

## Tổng Quan

Hệ thống quản lý design-driven commercial territory cho phép chia phân vùng bán hàng tối ưu dựa trên 3 thuật toán tiên tiến.

## Kiến Trúc

### Backend (FastAPI)

- **Database Models**: Zone, District, Territory, User, ZoneActivity, ZoneAdjacency, ZoneDistance
- **Algorithms**:
  - K-means Clustering (dựa trên vị trí địa lý)
  - Greedy Seed Growth (cân bằng tải)
  - Local Search (tối ưu hóa cục bộ)

### Frontend (React)

- **Admin Dashboard**: Quản lý zones, districts, territories, thuật toán
- **Sales Dashboard**: Xem phân vùng được giao, thống kê
- **Customer Dashboard**: Thông tin cá nhân, sales person phụ trách

## Setup

### Backend

1. **Cài đặt PyPI**

```bash
cd backend
pip install fastapi sqlalchemy sqlalchemy-utils python-jose passlib bcrypt
```

2. **Chạy Server**

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

1. **Cài đặt Dependencies**

```bash
cd frontend
npm install
```

2. **Chạy Development Server**

```bash
npm start
```

## Hướng Dẫn Sử Dụng

### Admin

#### 1. Tạo District

- Vào Admin Dashboard
- Chọn "Thêm Quận" ở sidebar
- Nhập mã quận, tên quận, tọa độ

#### 2. Tạo Zones

- Chọn District
- Tab "Quản Lý Zones"
- Nhập mã zone, tên, tọa độ
- Nhập thông tin khách hàng, đơn hàng, doanh thu

#### 3. Cập Nhật Activity

- Chọn Zone trong danh sách
- Click "Cập Nhật"
- Nhập thông tin hoạt động (số khách hàng, đơn hàng, doanh thu)

#### 4. Chạy Thuật Toán

Tab "Thuật Toán" có 3 lựa chọn:

**K-Means Clustering**

- Chia zones dựa trên vị trí địa lý
- Tối ưu khoảng cách địa lý
- Click "Chạy K-Means", nhập số phân vùng

**Greedy Seed Growth**

- Cân bằng tải giữa các phân vùng
- Dựa trên số lượng khách hàng, đơn hàng, doanh thu
- Click "Chạy Greedy", nhập số phân vùng

**Local Search**

- Điều chỉnh và tối ưu phân vùng hiện tại
- Thử swap zones giữa các phân vùng
- Chạy tự động trên tab "Phân Vùng"

#### 5. Gán Sales

- Tab "Phân Vùng"
- Ghép phân vùng với sales person

### Sales

#### Dashboard

- Xem tổng số phân vùng, zones, khách hàng, đơn hàng
- Xem doanh thu tổng cộng

#### Phân Vùng Của Tôi

- Xem danh sách các phân vùng được giao
- Xem chi tiết: số zones, khách hàng, đơn hàng, doanh thu
- Thông tin từng zone trong phân vùng

#### Thống Kê

- Biểu đồ phân bố khách hàng
- Bảng chi tiết phân vùng
- Tỷ lệ doanh thu

### Customer

#### Dashboard

- Xem thông tin cá nhân
- Mã khách hàng, email, điện thoại

#### Hồ Sơ Cá Nhân

- Cập nhật thông tin cá nhân (tương lai)

#### Sales Person

- Xem sales person phụ trách khu vực của mình (tương lai)
- Sẽ tự động xác định dựa trên vị trị địa lý

## Database Models

### User

```
- id: int (PK)
- username: str (unique)
- email: str (unique)
- password: str (hashed)
- role: str (admin, sales, customer)
- full_name: str
- phone: str
- is_approved: bool
- created_at: datetime
```

### District

```
- id: int (PK)
- code: str (unique)
- name: str
- center_lat: float
- center_lng: float
- total_area: float
- created_at: datetime
- zones: List[Zone] (relationship)
- territories: List[Territory] (relationship)
```

### Zone (Basic Unit)

```
- id: int (PK)
- zone_code: str (unique)
- district_id: int (FK)
- name: str
- geometry: JSON (GeoJSON)
- center_lat: float
- center_lng: float
- area_size: float
- num_customers: int
- num_orders: int
- revenue: float
- created_at: datetime
- activity: ZoneActivity (relationship)
- adjacencies: List[ZoneAdjacency] (relationship)
- distances: List[ZoneDistance] (relationship)
```

### ZoneActivity

```
- id: int (PK)
- zone_id: int (FK)
- num_customers: int
- num_orders: int
- avg_order_value: float
- total_revenue: float
- population_density: float
- business_density: float
- traffic_density: float
- notes: str
- updated_by: int (FK)
- updated_at: datetime
```

### ZoneAdjacency (Ma trận kề)

```
- id: int (PK)
- zone_id1: int (FK)
- zone_id2: int (FK)
- is_adjacent: bool
```

### ZoneDistance (Ma trận khoảng cách)

```
- id: int (PK)
- zone_id1: int (FK)
- zone_id2: int (FK)
- distance: float (km)
- travel_time: float (min)
```

### Territory

```
- id: int (PK)
- territory_code: str (unique)
- sales_id: int (FK)
- district_id: int (FK)
- zone_ids: JSON (List[int])
- num_zones: int
- num_customers: int
- num_orders: int
- total_revenue: float
- avg_distance: float
- algorithm_used: str (kmeans, greedy, localsearch)
- is_active: bool
- created_at: datetime
- updated_at: datetime
- sales_user: User (relationship)
- district: District (relationship)
```

## API Endpoints

### Auth

- `POST /register` - Đăng ký user mới
- `POST /login` - Đăng nhập

### Districts

- `POST /districts` - Tạo district
- `GET /districts` - Lấy danh sách districts
- `GET /districts/{id}` - Lấy chi tiết district

### Zones

- `POST /zones` - Tạo zone
- `GET /zones?district_id=...` - Lấy danh sách zones
- `GET /zones/{id}` - Lấy chi tiết zone
- `PUT /zones/{id}` - Cập nhật zone
- `POST /zones/{id}/activities` - Tạo activity cho zone
- `GET /zones/{id}/activities` - Lấy activity của zone

### Adjacency & Distance

- `POST /zones/adjacency` - Tạo quan hệ adjacent
- `POST /zones/distance` - Tạo thông tin khoảng cách
- `GET /districts/{id}/adjacency-matrix` - Lấy ma trận kề
- `GET /districts/{id}/distance-matrix` - Lấy ma trận khoảng cách

### Territories

- `POST /territories` - Tạo territory
- `GET /territories?district_id=...` - Lấy danh sách territories
- `GET /territories/{id}` - Lấy chi tiết territory
- `PUT /territories/{id}` - Cập nhật territory

### Algorithms

- `POST /algorithms/kmeans` - Chạy K-Means
- `POST /algorithms/greedy` - Chạy Greedy Seed Growth
- `POST /algorithms/localsearch` - Chạy Local Search

### Sales & Admin

- `GET /sales/{id}/territories` - Lấy territories của sales
- `GET /sales/{id}/dashboard` - Lấy dashboard sales
- `GET /admin/statistics` - Lấy thống kê admin
- `GET /users?role=...` - Lấy danh sách users

## Thuật Toán

### K-Means Clustering

**Mục đích**: Chia zones dựa trên vị trí địa lý

**Quy trình**:

1. Chọn k centroids ngẫu nhiên (k = số phân vùng)
2. Gán từng zone đến centroid gần nhất
3. Cập nhật centroid = trung bình tọa độ các zones
4. Lặp lại cho đến hội tụ

**Ưu điểm**:

- Tối ưu khoảng cách địa lý
- Phân vùng compact
- Nhanh chóng

**Nhược điểm**:

- Không cân bằng tải
- Phụ thuộc khởi tạo ngẫu nhiên

### Greedy Seed Growth

**Mục đích**: Cân bằng tải giữa các phân vùng

**Quy trình**:

1. Tính workload cho mỗi zone (customers _ 0.4 + orders _ 0.3 + revenue \* 0.3)
2. Chọn k zones có workload cao nhất làm seeds
3. Gán các zones còn lại vào phân vùng có workload thấp nhất
4. Cân bằng tải tự động

**Ưu điểm**:

- Cân bằng tải tốt
- Tính toán công lý cho sales
- Hiệu quả cao

**Nhược điểm**:

- Có thể không compact địa lý
- Phức tạp hơn K-Means

### Local Search

**Mục đích**: Tối ưu hóa phân vùng hiện tại

**Quy trình**:

1. Bắt đầu từ phân vùng hiện tại
2. Thử swap zones giữa các phân vùng liên tiếp
3. Giữ lại swap nếu cải thiện chất lượng
4. Lặp lại cho đến không còn cải thiện

**Ưu điểm**:

- Cải thiện giải pháp hiện tại
- Linh hoạt
- Có thể tùy chỉnh

**Nhược điểm**:

- Có thể stuck tại local optimum
- Phụ thuộc vào giải pháp ban đầu

## Các Bước Tiếp Theo

### Tích Hợp Map

- [ ] Tích hợp Google Maps hoặc OpenStreetMap
- [ ] Vẽ zones trực tiếp trên bản đồ
- [ ] Hiển thị territories trên bản đồ
- [ ] Drag-and-drop zones để điều chỉnh

### Cải Thiện Thuật Toán

- [ ] Tối ưu hóa tham số thuật toán
- [ ] Thêm constraints (max zones per territory, max distance, etc.)
- [ ] Genetic Algorithm cho tối ưu hóa toàn cục
- [ ] Ant Colony Optimization (ACO)

### Tính Năng Khác

- [ ] Lịch sử thay đổi territory
- [ ] Báo cáo chi tiết
- [ ] Export dữ liệu (Excel, PDF)
- [ ] Integration với CRM/ERP
- [ ] Real-time tracking

### DevOps

- [ ] Containerize (Docker)
- [ ] CI/CD Pipeline
- [ ] Cloud deployment (AWS, Azure, GCP)
- [ ] Monitoring & Logging
- [ ] Backup & Recovery

## Hỗ Trợ

Nếu có vấn đề, vui lòng:

1. Kiểm tra logs backend
2. Kiểm tra network tab trong DevTools
3. Liên hệ team support

## Giấy Phép

MIT License
