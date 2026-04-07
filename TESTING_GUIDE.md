# TESTING GUIDE - Commercial Territory Design System

## 🧪 Hướng Dẫn Kiểm Tra

### Prerequisites

- Backend running: `http://localhost:8000`
- Frontend running: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`

---

## 1️⃣ AUTH TESTS

### Test 1.1: Register New Admin

```
POST /register
{
  "username": "admin1",
  "email": "admin@example.com",
  "password": "Admin123!",
  "role": "admin",
  "full_name": "Admin User",
  "phone": "0123456789"
}

Expected: 200, msg: "Đăng ký thành công!"
```

### Test 1.2: Register New Sales

```
POST /register
{
  "username": "sales1",
  "email": "sales@example.com",
  "password": "Sales123!",
  "role": "sales",
  "full_name": "Sales Person",
  "phone": "0987654321"
}

Expected: 200, msg: "Đăng ký thành công!"
```

### Test 1.3: Register New Customer

```
POST /register
{
  "username": "customer1",
  "email": "customer@example.com",
  "password": "Customer123!",
  "role": "customer",
  "full_name": "John Doe",
  "phone": "0912345678"
}

Expected: 200, msg: "Đăng ký thành công!"
```

### Test 1.4: Login Admin

```
POST /login
{
  "username": "admin1",
  "password": "Admin123!"
}

Expected: 200
Response:
{
  "token": "...",
  "role": "admin",
  "id": 1
}
```

### Test 1.5: Login Sales

```
POST /login
{
  "username": "sales1",
  "password": "Sales123!"
}

Expected: 200, role: "sales", id: 2
```

---

## 2️⃣ DISTRICT TESTS

### Test 2.1: Create District

```
POST /districts
Headers: Authorization: Bearer {token}
{
  "code": "HN001",
  "name": "Hà Nội",
  "center_lat": 21.0285,
  "center_lng": 105.8542,
  "total_area": 3324.0
}

Expected: 200
Response: District object with id
```

### Test 2.2: Get All Districts

```
GET /districts

Expected: 200
Response: Array of districts
```

### Test 2.3: Get District by ID

```
GET /districts/{id}

Expected: 200
Response: Single district object
```

---

## 3️⃣ ZONE TESTS

### Test 3.1: Create Zone 1

```
POST /zones
{
  "zone_code": "Z001",
  "district_id": 1,
  "name": "Bắc Từ Liêm - Zone 1",
  "center_lat": 21.05,
  "center_lng": 105.80,
  "area_size": 50.5,
  "num_customers": 150,
  "num_orders": 300,
  "revenue": 15000000
}

Expected: 200 + zone object
```

### Test 3.2: Create 5 Zones (Total)

```
Tạo 5 zones với data khác nhau:
- Z001, Z002, Z003, Z004, Z005
- Mỗi zone có tọa độ khác nhau
- Khách hàng từ 100-300
- Đơn hàng từ 200-500
```

### Test 3.3: Get Zones by District

```
GET /zones?district_id=1

Expected: 200
Response: Array of 5 zones
```

### Test 3.4: Update Zone

```
PUT /zones/1
{
  "num_customers": 200,
  "num_orders": 400,
  "revenue": 20000000
}

Expected: 200 + updated zone
```

### Test 3.5: Add Zone Activity

```
POST /zones/1/activities
{
  "num_customers": 200,
  "num_orders": 400,
  "avg_order_value": 50000,
  "total_revenue": 20000000,
  "population_density": 5000.0,
  "business_density": 100.0,
  "traffic_density": 75.0,
  "notes": "High potential area"
}

Expected: 200 + activity object
```

### Test 3.6: Get Zone Activity

```
GET /zones/1/activities

Expected: 200
Response: ZoneActivity object
```

---

## 4️⃣ ADJACENCY & DISTANCE TESTS

### Test 4.1: Create Adjacency

```
POST /zones/adjacency
{
  "zone_id1": 1,
  "zone_id2": 2
}

Expected: 200 + adjacency object
```

### Test 4.2: Create Distance

```
POST /zones/distance
{
  "zone_id1": 1,
  "zone_id2": 2,
  "distance": 5.2,
  "travel_time": 15
}

Expected: 200 + distance object
```

### Test 4.3: Get Adjacency Matrix

```
GET /districts/1/adjacency-matrix

Expected: 200
Response:
{
  "zone_ids": [1, 2, 3, 4, 5],
  "matrix": [
    [0, 1, 0, 0, 1],
    [1, 0, 1, 0, 0],
    ...
  ]
}
```

### Test 4.4: Get Distance Matrix

```
GET /districts/1/distance-matrix

Expected: 200
Response:
{
  "zone_ids": [1, 2, 3, 4, 5],
  "matrix": [
    [0, 5.2, 10.1, 15.3, 20.5],
    [5.2, 0, 6.3, 12.4, 18.6],
    ...
  ]
}
```

---

## 5️⃣ ALGORITHM TESTS

### Test 5.1: K-Means Clustering

```
POST /algorithms/kmeans
{
  "district_id": 1,
  "num_clusters": 2,
  "max_iterations": 100
}

Expected: 200
Response:
{
  "algorithm": "kmeans",
  "execution_time": 0.123,
  "quality_score": 75.5,
  "num_territories": 2,
  "territories": [1, 2],
  "message": "KMeans clustering completed in 5 iterations"
}

Verify:
- Territories được tạo với 2-3 zones mỗi cái
- Quality score > 50%
- Execution time < 1 second
```

### Test 5.2: Greedy Seed Growth

```
POST /algorithms/greedy
{
  "district_id": 1,
  "num_territories": 3,
  "max_zones_per_territory": 50
}

Expected: 200
Response:
{
  "algorithm": "greedy",
  "execution_time": 0.089,
  "quality_score": 82.3,
  "num_territories": 3,
  "territories": [3, 4, 5],
  "message": "Greedy Seed Growth completed"
}

Verify:
- 3 territories được tạo
- Mỗi cái chia đều zones
- Workload cân bằng hơn K-Means
```

### Test 5.3: Local Search

```
POST /algorithms/localsearch
{
  "territory_id": 1,
  "swap_iterations": 10
}

Expected: 200
Response:
{
  "algorithm": "localsearch",
  "execution_time": 0.045,
  "quality_score": 85.1,
  "iterations": 3,
  "message": "Local Search completed in 3 iterations"
}

Verify:
- Quality score tăng so với ban đầu
- Iterations < swap_iterations (converged)
```

---

## 6️⃣ TERRITORY TESTS

### Test 6.1: Get Admin Statistics

```
GET /admin/statistics

Expected: 200
Response:
{
  "total_zones": 5,
  "total_territories": 3,
  "total_sales": 1,
  "total_customers": 1,
  "total_orders": 1200,
  "total_revenue": 60000000
}

Verify:
- Tất cả stats > 0
- Tổng cộng khớp với data
```

### Test 6.2: Get Sales Territories

```
GET /sales/2/territories

Expected: 200
Response: Array of 1-2 territories

Verify:
- Mỗi territory có zone_ids
- Num_zones > 0
```

### Test 6.3: Get Sales Dashboard

```
GET /sales/2/dashboard

Expected: 200
Response:
{
  "sales_id": 2,
  "num_territories": 1,
  "total_zones": 3,
  "total_customers": 450,
  "total_orders": 900,
  "total_revenue": 45000000,
  "territories": [...]
}

Verify:
- Dashboard stats khớp territories
```

---

## 7️⃣ FRONTEND TESTS

### Test 7.1: Admin Dashboard

```
1. Đăng nhập với admin1
2. Vào /admin
3. Kiểm tra:
   - Sidebar hiển thị districts ✓
   - Statistics panel hiển thị ✓
   - Có thể tạo district ✓
   - Có thể tạo zone ✓
   - Có thể chạy algorithms ✓
   - Kết quả algorithms hiển thị ✓
```

### Test 7.2: Sales Dashboard

```
1. Đăng nhập với sales1
2. Vào /sales
3. Kiểm tra:
   - Summary stats hiển thị ✓
   - Danh sách territories ✓
   - Chi tiết territory khi click ✓
   - Tab Thống Kê hiển thị chart ✓
   - Dữ liệu khớp backend ✓
```

### Test 7.3: Customer Dashboard

```
1. Đăng nhập với customer1
2. Vào /customer
3. Kiểm tra:
   - Customer ID hiển thị ✓
   - Thông tin cá nhân hiển thị ✓
   - 4 tabs đều có ✓
   - Có thể xem profile ✓
```

---

## 8️⃣ INTEGRATION TESTS

### Test 8.1: Complete Flow

```
1. Register admin → Login → /admin
2. Tạo district HN
3. Tạo 5 zones
4. Thêm activity cho mỗi zone
5. Chạy K-Means (num=2)
6. Kiểm tra territories tạo ra
7. Chạy Greedy (num=3)
8. Kiểm tra territories cập nhật
9. Chạy Local Search
10. Kiểm tra quality score cải thiện

Expected: Toàn bộ flow hoạt động mượt
```

### Test 8.2: Multi-User Flow

```
1. Admin tạo 2 districts
2. Admin tạo 10 zones
3. Admin chạy algorithms tạo territories
4. Sales1 login, xem territories của mình
5. Sales2 login, xem territories của mình
6. Customer1 login, xem info

Expected: Mỗi user chỉ thấy dữ liệu của mình
```

---

## 📋 TEST RESULTS TEMPLATE

```
Test Date: ___________
Tester: ________________

AUTHENTICATION:
[ ] Register Admin - PASS/FAIL
[ ] Register Sales - PASS/FAIL
[ ] Register Customer - PASS/FAIL
[ ] Login Admin - PASS/FAIL
[ ] Login Sales - PASS/FAIL

DISTRICTS:
[ ] Create District - PASS/FAIL
[ ] Get Districts - PASS/FAIL
[ ] Get District by ID - PASS/FAIL

ZONES:
[ ] Create Zones - PASS/FAIL
[ ] Get Zones - PASS/FAIL
[ ] Update Zone - PASS/FAIL
[ ] Add Activity - PASS/FAIL

MATRICES:
[ ] Adjacency Matrix - PASS/FAIL
[ ] Distance Matrix - PASS/FAIL

ALGORITHMS:
[ ] K-Means - PASS/FAIL
[ ] Greedy Seed Growth - PASS/FAIL
[ ] Local Search - PASS/FAIL

FRONTEND:
[ ] Admin Dashboard - PASS/FAIL
[ ] Sales Dashboard - PASS/FAIL
[ ] Customer Dashboard - PASS/FAIL

INTEGRATION:
[ ] Complete Flow - PASS/FAIL
[ ] Multi-User Flow - PASS/FAIL

Notes:
_________________________________
_________________________________
```

---

## 🐛 DEBUGGING TIPS

### Network Issues:

```bash
# Check if backend is running
curl http://localhost:8000/docs

# Check CORS
curl -i -X OPTIONS http://localhost:8000/algorithms/kmeans
```

### Database Issues:

```bash
# Check MySQL status
mysql -u root -p -e "SHOW DATABASES;"

# Check tables
mysql -u root -p database_name -e "SHOW TABLES;"
```

### Algorithm Issues:

```python
# Test locally
from algorithms import KMeansClustering
zones = [{"id": 1, "lat": 21, "lng": 105, ...}, ...]
algo = KMeansClustering(zones, {})
result = algo.solve(3)
print(result)
```

---

## ✅ SIGN-OFF

By following this testing guide, you should be able to:

- ✓ Verify all API endpoints work correctly
- ✓ Test all 3 algorithms produce reasonable results
- ✓ Confirm frontend dashboards display correct data
- ✓ Validate role-based access control
- ✓ Ensure data consistency across system

Happy testing! 🎉
