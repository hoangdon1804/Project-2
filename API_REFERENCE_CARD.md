# API REFERENCE CARD - Quick Lookup

## Authentication Endpoints

### POST /register

Register new user

```json
{
  "username": "string",
  "email": "string",
  "password": "string (8+, upper, number, special)",
  "role": "admin|sales|customer",
  "full_name": "string",
  "phone": "string"
}
→ 200: {"msg": "Đăng ký thành công!"}
```

### POST /login

Login user

```json
{"username": "string", "password": "string"}
→ 200: {"token": "string", "role": "string", "id": int}
```

---

## District Endpoints

### POST /districts

Create district

```json
{
  "code": "string (unique)",
  "name": "string",
  "center_lat": float,
  "center_lng": float,
  "total_area": float
}
→ 200: District{id, code, name, ...}
```

### GET /districts

List all districts

```
→ 200: [District, ...]
```

### GET /districts/{id}

Get district by ID

```
→ 200: District{id, code, name, ...}
```

---

## Zone Endpoints

### POST /zones

Create zone

```json
{
  "zone_code": "string (unique)",
  "district_id": int,
  "name": "string",
  "center_lat": float,
  "center_lng": float,
  "area_size": float,
  "num_customers": int,
  "num_orders": int,
  "revenue": float
}
→ 200: Zone{id, zone_code, ...}
```

### GET /zones?district_id=1

Get zones by district

```
→ 200: [Zone, ...]
```

### GET /zones/{id}

Get zone by ID

```
→ 200: Zone{id, zone_code, ...}
```

### PUT /zones/{id}

Update zone

```json
{
  "num_customers": int,
  "num_orders": int,
  "revenue": float
}
→ 200: Zone{...updated...}
```

### POST /zones/{id}/activities

Add zone activity

```json
{
  "num_customers": int,
  "num_orders": int,
  "avg_order_value": float,
  "total_revenue": float,
  "population_density": float,
  "business_density": float,
  "traffic_density": float,
  "notes": "string"
}
→ 200: ZoneActivity{...}
```

### GET /zones/{id}/activities

Get zone activities

```
→ 200: ZoneActivity{...}
```

---

## Adjacency & Distance Endpoints

### POST /zones/adjacency

Create adjacency relationship

```json
{"zone_id1": int, "zone_id2": int}
→ 200: ZoneAdjacency{...}
```

### POST /zones/distance

Create distance relationship

```json
{
  "zone_id1": int,
  "zone_id2": int,
  "distance": float,
  "travel_time": int
}
→ 200: ZoneDistance{...}
```

### GET /districts/{id}/adjacency-matrix

Get adjacency matrix

```
→ 200: {
  "zone_ids": [1, 2, 3, ...],
  "matrix": [[0,1,0,...], [1,0,1,...], ...]
}
```

### GET /districts/{id}/distance-matrix

Get distance matrix

```
→ 200: {
  "zone_ids": [1, 2, 3, ...],
  "matrix": [[0,5.2,10.1,...], [5.2,0,6.3,...], ...]
}
```

---

## Territory Endpoints

### POST /territories

Create territory

```json
{
  "sales_id": int,
  "district_id": int,
  "zone_ids": [1, 2, 3],
  "algorithm_used": "manual|kmeans|greedy|localsearch"
}
→ 201: Territory{id, territory_code, ...}
```

### GET /territories?sales_id={id}&district_id={id}

Get territories with filters

```
→ 200: [Territory, ...]
```

### GET /territories/{id}

Get territory by ID

```
→ 200: Territory{id, territory_code, ...}
```

### PUT /territories/{id}

Update territory

```json
{
  "zone_ids": [1, 2, 3],
  "is_active": true
}
→ 200: Territory{...updated...}
```

---

## Algorithm Endpoints

### POST /algorithms/kmeans

Run K-Means clustering

```json
{
  "district_id": int,
  "num_clusters": int,
  "max_iterations": int
}
→ 200: {
  "algorithm": "kmeans",
  "execution_time": float,
  "quality_score": float,
  "num_territories": int,
  "territories": [1, 2, 3],
  "message": "string"
}
```

### POST /algorithms/greedy

Run Greedy Seed Growth

```json
{
  "district_id": int,
  "num_territories": int,
  "max_zones_per_territory": int
}
→ 200: {
  "algorithm": "greedy",
  "execution_time": float,
  "quality_score": float,
  "num_territories": int,
  "territories": [1, 2, 3],
  "message": "string"
}
```

### POST /algorithms/localsearch

Run Local Search optimization

```json
{
  "territory_id": int,
  "swap_iterations": int
}
→ 200: {
  "algorithm": "localsearch",
  "execution_time": float,
  "quality_score": float,
  "iterations": int,
  "message": "string"
}
```

---

## Dashboard & Analytics Endpoints

### GET /admin/statistics

Get system statistics

```
→ 200: {
  "total_zones": int,
  "total_territories": int,
  "total_sales": int,
  "total_customers": int,
  "total_orders": int,
  "total_revenue": float
}
```

### GET /sales/{id}/dashboard

Get sales dashboard

```
→ 200: {
  "sales_id": int,
  "num_territories": int,
  "total_zones": int,
  "total_customers": int,
  "total_orders": int,
  "total_revenue": float,
  "territories": [...]
}
```

### GET /sales/{id}/territories

Get sales territories

```
→ 200: [Territory, ...]
```

### GET /users?role={role}

Get users by role

```
→ 200: [User, ...]
```

---

## Error Responses

### 400 Bad Request

```json
{ "detail": "Validation error message" }
```

### 401 Unauthorized

```json
{ "detail": "Not authenticated" }
```

### 403 Forbidden

```json
{ "detail": "Not authorized" }
```

### 404 Not Found

```json
{ "detail": "Resource not found" }
```

### 409 Conflict

```json
{ "detail": "Duplicate entry error" }
```

### 500 Internal Server Error

```json
{ "detail": "Server error message" }
```

---

## Common Request Headers

```
Content-Type: application/json
Authorization: Bearer {token}
```

---

## Authentication Example

```bash
# 1. Register
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin1",
    "email": "admin@example.com",
    "password": "Admin123!",
    "role": "admin",
    "full_name": "Admin User",
    "phone": "0123456789"
  }'

# 2. Login
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin1", "password": "Admin123!"}'

# 3. Use token
TOKEN=$(curl -s -X POST http://localhost:8000/login ... | jq -r '.token')
curl -X GET http://localhost:8000/admin/statistics \
  -H "Authorization: Bearer $TOKEN"
```

---

## Workload Calculation Formula

```
Workload = (num_customers × 0.4) + (num_orders × 0.3) + (revenue / 100000 × 0.3)
```

Examples:

- Zone A: 100 customers, 200 orders, 5,000,000 revenue
  - Workload = (100 × 0.4) + (200 × 0.3) + (50 × 0.3) = 40 + 60 + 15 = 115
- Zone B: 200 customers, 400 orders, 10,000,000 revenue
  - Workload = (200 × 0.4) + (400 × 0.3) + (100 × 0.3) = 80 + 120 + 30 = 230

---

## Algorithm Return Format

All algorithms return this structure:

```json
{
  "algorithm": "string (kmeans|greedy|localsearch)",
  "execution_time": float (seconds),
  "quality_score": float (0-100, higher is better),
  "iterations": int (optional, for local search),
  "num_territories": int,
  "territories": [1, 2, 3],
  "message": "string (summary of what happened)"
}
```

---

## Model Relationships

```
User (admin/sales/customer)
  ├── Territory (sales)
  └── (no direct zones)

Territory
  ├── Sales: User (m-to-1)
  ├── District: District (m-to-1)
  └── zone_ids: [zones] (JSON array)

District
  ├── zones: [Zone] (1-to-m)
  └── territories: [Territory] (1-to-m)

Zone
  ├── district: District (m-to-1)
  ├── activity: ZoneActivity (1-to-1)
  ├── adjacencies: [ZoneAdjacency] (1-to-m)
  └── distances: [ZoneDistance] (1-to-m)
```

---

## Frontend Integration

```javascript
const API_BASE = "http://localhost:8000";

// Get token from login
const token = localStorage.getItem("token");

// Make authenticated request
const response = await fetch(`${API_BASE}/admin/statistics`, {
  headers: {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  },
});

const data = await response.json();
```

---

## Test Credentials

```
Admin:
  Username: admin1
  Password: Admin123!
  Role: admin

Sales:
  Username: sales1
  Password: Sales123!
  Role: sales

Customer:
  Username: customer1
  Password: Customer123!
  Role: customer
```

---

## Quick Validation

```javascript
// Password validation
/^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*])[\w!@#$%^&*]{8,}$/.test(password);

// Coordinate validation
lat >= -90 &&
  lat <= 90 &&
  lng >= -180 &&
  lng <=
    (180)[
      // Role validation
      ("admin", "sales", "customer")
    ].includes(role);
```

---

## Environment Variables

```
Backend (.env):
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/db_name
SECRET_KEY=your-secret-key-min-32-characters
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

Frontend (.env):
REACT_APP_API_BASE=http://localhost:8000
```

---

## Performance Tips

- **K-Means:** Use clusters = zones/5 for balanced results
- **Greedy:** Faster than K-Means, good for real-time
- **Local Search:** Run after greedy for 5-10 iterations to polish
- **Matrices:** Create adjacency/distance once, then reuse
- **Caching:** Store algorithm results for same district

---

## Status Codes Summary

| Code | Meaning                                   |
| ---- | ----------------------------------------- |
| 200  | Success - GET, PUT                        |
| 201  | Created - POST creates new resource       |
| 400  | Bad request - validation error            |
| 401  | Unauthorized - invalid/missing token      |
| 403  | Forbidden - not allowed for this resource |
| 404  | Not found - resource doesn't exist        |
| 409  | Conflict - duplicate entry                |
| 500  | Server error - bug in code                |

---

**Last Updated:** 2024
**API Version:** 1.0
**Backend:** FastAPI
**Frontend:** React
