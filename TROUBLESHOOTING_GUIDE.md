# TROUBLESHOOTING GUIDE - Commercial Territory Design System

## 🔧 Hướng Dẫn Xử Lý Sự Cố

---

## 1️⃣ BACKEND ISSUES

### ❌ Error: "ModuleNotFoundError: No module named 'fastapi'"

**Symptoms:**

- Backend không start
- Terminal shows: `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**

```bash
# Install dependencies
pip install fastapi uvicorn sqlalchemy mysql-connector-python python-jose passlib bcrypt

# Or use requirements.txt if available
pip install -r requirements.txt

# Start backend
python -m uvicorn main:app --reload
```

---

### ❌ Error: "MySQL Connection Refused"

**Symptoms:**

- Backend starts but crashes with: `Connection refused on 127.0.0.1:3306`
- Database operations fail

**Solution:**

```bash
# Check if MySQL is running
# Windows
net start MySQL80
# or check Services → MySQL80 is started

# Check connection string in main.py
# DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/database_name"

# Verify credentials:
mysql -u root -p
# Enter password from DATABASE_URL

# If no password, update main.py:
DATABASE_URL = "mysql+pymysql://root@localhost:3306/database_name"
```

**MySQL Setup (if not installed):**

```bash
# Windows: Install MySQL Community Server
# https://dev.mysql.com/downloads/mysql/

# Create database
mysql -u root -p -e "CREATE DATABASE database_name;"

# Check creation
mysql -u root -p -e "SHOW DATABASES;"
```

---

### ❌ Error: "Port 8000 Already in Use"

**Symptoms:**

- `ERROR: Uvicorn server failed to start port 8000 is already in use`

**Solution:**

```bash
# Find process using port 8000
# Windows
netstat -ano | findstr :8000

# Kill process (if PID is 1234)
taskkill /PID 1234 /F

# Or use different port
python -m uvicorn main:app --reload --port 8001
```

---

### ❌ Error: "CORS Error - Blocked by CORS Policy"

**Symptoms:**

- Frontend can't call backend API
- Browser console: `Access to XMLHttpRequest blocked by CORS policy`

**Solution:**
Check main.py has CORS config:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

If CORS config missing:

1. Add above code after `app = FastAPI()`
2. Restart backend
3. Clear browser cache (Ctrl+Shift+Delete)

---

### ❌ Error: "Tables Not Created"

**Symptoms:**

- GET /zones returns empty
- Database queries fail
- `Table 'database_name.user' doesn't exist`

**Solution:**

```python
# In main.py, add at startup
from models import Base

# Create tables on startup
Base.metadata.create_all(bind=engine)

# Or manually in MySQL:
mysql -u root -p database_name < schema.sql
```

Verify tables created:

```bash
mysql -u root -p database_name -e "SHOW TABLES;"

# Output should show:
# users, districts, zones, territories, zone_activities, etc.
```

---

### ❌ Error: "JWT Token Invalid"

**Symptoms:**

- Login returns token but GET endpoints return `401 Unauthorized`
- Error: `InvalidSignatureError` or `ExpiredSignatureError`

**Solution:**
Check main.py JWT settings:

```python
SECRET_KEY = "your-secret-key-must-be-long"  # Min 32 chars
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Make sure SECRET_KEY is consistent
```

Test token:

```bash
# 1. Login
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin1","password":"Admin123!"}'

# 2. Copy token from response
# 3. Use token in requests
curl -X GET http://localhost:8000/admin/statistics \
  -H "Authorization: Bearer {token}"
```

---

### ❌ Error: "Algorithm Convergence Issues"

**Symptoms:**

- K-Means doesn't converge
- Quality score very low (< 30%)
- Execution time > 5 seconds

**Solution:**

```python
# In algorithms.py, adjust parameters:

# K-Means - reduce iterations or clusters
KMeansClustering.solve(
    num_clusters=2,  # Start small
    max_iterations=50  # Reduce iterations
)

# Check zone data quality:
GET /zones
# Zones should have:
# - Valid coordinates (lat/lng)
# - num_customers > 0
# - num_orders > 0
# - revenue > 0

# If data missing:
PUT /zones/{id}
{
  "num_customers": 100,
  "num_orders": 200,
  "revenue": 5000000
}
```

---

## 2️⃣ FRONTEND ISSUES

### ❌ Error: "npm ERR! code ERESOLVE"

**Symptoms:**

- `npm install` fails with dependency conflict

**Solution:**

```bash
# Use force flag
npm install --force

# Or use legacy peer deps
npm install --legacy-peer-deps

# If still fails, clear cache
npm cache clean --force
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

---

### ❌ Error: "Port 3000 Already in Use"

**Symptoms:**

- `Something is already running on port 3000`

**Solution:**

```bash
# Windows - find and kill process
netstat -ano | findstr :3000
taskkill /PID {PID} /F

# Or use different port
PORT=3001 npm start

# Or check if Node process running
Get-Process node | Stop-Process -Force
```

---

### ❌ Error: "API Not Found / 404"

**Symptoms:**

- Frontend shows: `API call failed: 404 Not Found`
- Check Network tab in DevTools

**Cause 1: Wrong API URL**

```javascript
// In api.js, check:
const API_BASE = "http://localhost:8000";

// Should NOT be:
// const API_BASE = "http://localhost:3000";
// const API_BASE = "http://example.com";
```

**Cause 2: Endpoint doesn't exist**

```bash
# Check what endpoints actually exist
curl http://localhost:8000/docs

# You'll see Swagger UI with all available endpoints
# Common endpoints:
POST /register
POST /login
GET /districts
POST /zones
GET /admin/statistics
```

**Cause 3: Backend not running**

```bash
# Check backend status
curl http://localhost:8000/docs

# If times out, backend not running
# Start it:
python -m uvicorn main:app --reload
```

---

### ❌ Error: "Login Not Working"

**Symptoms:**

- Login button doesn't respond
- Page stays on /login
- No error message

**Solution:**
Check browser DevTools (F12) → Network tab:

1. Click login
2. Look for POST request to `/login`
3. Check Response:
   - Should return `{"token": "...", "role": "...", "id": ...}`
   - If error, check backend logs

**Common causes:**

```javascript
// Check api.js has correct BASE URL
const API_BASE = "http://localhost:8000";

// Check credentials match registered user
// Username: admin1
// Password: Admin123!  (Case sensitive!)

// Check localStorage is enabled
localStorage.setItem("test", "test");
localStorage.getItem("test"); // Should return "test"
```

---

### ❌ Error: "Protected Route Not Working"

**Symptoms:**

- Can access /admin without logging in
- Or logged in but can't access /admin
- Redirects to /login incorrectly

**Solution:**
Check App.js ProtectedRoute component:

```javascript
// Should check token AND role
function ProtectedRoute({ children, requiredRole }) {
  const token = localStorage.getItem("token");
  const role = localStorage.getItem("role");

  if (!token || role !== requiredRole) {
    return <Navigate to="/login" />;
  }

  return children;
}

// Usage:
<Route
  path="/admin"
  element={
    <ProtectedRoute requiredRole="admin">
      <AdminDashboard />
    </ProtectedRoute>
  }
/>;
```

**Debug:**

```javascript
// In browser console (F12)
localStorage.getItem("token"); // Should exist and not be null
localStorage.getItem("role"); // Should be "admin", "sales", or "customer"
localStorage.getItem("user_id"); // Should be a number like "1"
```

---

### ❌ Error: "Dashboard Not Loading Data"

**Symptoms:**

- Dashboard page loads but no data displays
- Statistics showing 0
- Zones list empty

**Causes & Solutions:**

**Cause 1: No data in database**

```bash
# Check if data exists
GET /districts
GET /zones?district_id=1

# If empty, create test data first
POST /districts
POST /zones
```

**Cause 2: Authentication failing**

```javascript
// Check in browser console
const response = await fetch("http://localhost:8000/admin/statistics", {
  headers: {
    Authorization: "Bearer " + localStorage.getItem("token"),
  },
});
// If 401, token is invalid
```

**Cause 3: Wrong district selected**

```javascript
// In AdminDashboard.js
const [selectedDistrict, setSelectedDistrict] = useState(null);

// Make sure district is actually selected
if (!selectedDistrict) {
  // Wait for district to be selected
  return <p>Select a district</p>;
}
```

---

### ❌ Error: "Algorithms Not Running"

**Symptoms:**

- Click "Run K-Means" but nothing happens
- Loading spinner stuck forever
- No error message

**Debug steps:**

```javascript
// Check in browser DevTools → Network tab:
// 1. Look for POST request to /algorithms/kmeans
// 2. Check status code:
//    - 200: Success
//    - 400: Bad request (missing parameters)
//    - 401: Not authenticated
//    - 500: Server error

// 3. Check Response tab for error message
```

**Verify required data:**

```bash
# K-Means requires:
POST /algorithms/kmeans
{
  "district_id": 1,        # Must exist
  "num_clusters": 2,      # > 0 and < num_zones
  "max_iterations": 100
}

# Required: At least num_clusters zones in district
GET /zones?district_id=1
# Should return at least 2 zones if asking for 2 clusters
```

---

## 3️⃣ DATABASE ISSUES

### ❌ Error: "Duplicate Entry"

**Symptoms:**

- `Duplicate entry 'admin1' for key 'username'`
- Can't create user/zone/district with same code

**Solution:**

```bash
# Check existing data
SELECT * FROM users WHERE username = 'admin1';

# Delete if needed
DELETE FROM users WHERE username = 'admin1';

# Or use different username
POST /register
{
  "username": "admin2",  # Different username
  ...
}
```

---

### ❌ Error: "Foreign Key Constraint Failed"

**Symptoms:**

- `Cannot add or update a child row: a foreign key constraint fails`
- Error when creating zone with non-existent district

**Solution:**

```bash
# Verify parent exists
POST /zones
{
  "district_id": 999  # This district doesn't exist!
}

# Fix:
# 1. Create district first
POST /districts
{
  "code": "HN001",
  ...
}

# 2. Note the returned id
# 3. Then create zone with that id
POST /zones
{
  "district_id": 1,  # Use real district id
  ...
}
```

---

### ❌ Error: "JSON Field Error"

**Symptoms:**

- `json.JSONDecodeError` in backend
- Zone geometry not saving correctly

**Solution:**

```python
# Ensure zone_ids and geometry are valid JSON strings

POST /zones
{
  "zone_code": "Z001",
  "geometry": {  # Use object, backend converts to JSON string
    "type": "Polygon",
    "coordinates": [[[105.8, 21.05], [105.9, 21.05], ...]]
  }
}
```

---

## 4️⃣ PERFORMANCE ISSUES

### ⚠️ Problem: "Slow Algorithm Execution"

**Symptoms:**

- K-Means takes > 5 seconds
- UI freezes during algorithm run

**Solutions:**

```python
# 1. Reduce iterations
POST /algorithms/kmeans
{
  "num_clusters": 2,
  "max_iterations": 20  # Reduce from 100
}

# 2. Reduce number of zones (filter by parent district)
# Only algorithms on one district at a time

# 3. Add caching
# Store results to avoid recomputation
```

---

### ⚠️ Problem: "Memory Issues"

**Symptoms:**

- Backend crashes after running multiple algorithms
- "Memory Error" or "Out of Memory"

**Solutions:**

```python
# In algorithms.py, add memory cleanup
def solve(self, ...):
    try:
        result = self._run_algorithm()
        return result
    finally:
        # Cleanup large objects
        self.zones = []
        self.assignments = {}
```

---

## 5️⃣ DATA VALIDATION ISSUES

### ❌ Error: "Invalid Password Format"

**Symptoms:**

- `password: Password must contain...`
- Registration fails

**Requirements:**

```
Password must be:
✓ Minimum 8 characters
✓ At least 1 UPPERCASE letter (A-Z)
✓ At least 1 number (0-9)
✓ At least 1 special character (!@#$%^&*)

Examples of VALID passwords:
- Admin123!
- Sales@2024
- Customer#999

Examples of INVALID passwords:
- admin123!        (no uppercase)
- ADMIN123!        (no lowercase)
- Admin!           (no number)
- Admin123         (no special char)
```

---

### ❌ Error: "Invalid Coordinates"

**Symptoms:**

- Zone/District creation fails with coordinate error
- `latitude must be between -90 and 90`

**Solution:**

```javascript
// Valid ranges:
Latitude: -90 to +90    (North-South)
Longitude: -180 to +180 (East-West)

// Examples:
// Hanoi: lat=21.0285, lng=105.8542 ✓
// Vietnam: lat=10-24, lng=102-108 ✓
// Invalid: lat=100, lng=200 ✗

// Test coordinate:
const isValidCoord = (lat, lng) => {
  return lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}
```

---

## 6️⃣ BROWSER ISSUES

### ❌ Error: "localStorage is not available"

**Symptoms:**

- `localStorage is not defined`
- Happens in private/incognito browsing

**Solution:**

```javascript
// Use safe wrapper
function getToken() {
  try {
    return localStorage.getItem("token");
  } catch (e) {
    return null; // Incognito mode
  }
}

// Or detect and warn user
if (!localStorage) {
  alert("Please disable private browsing mode");
}
```

---

### ❌ Error: "CORS Preflight Failed"

**Symptoms:**

- OPTIONS request returns 405
- Complex requests (with headers) fail

**Solution:**
Backend main.py should have:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows OPTIONS
    allow_headers=["*"],
)
```

---

## 7️⃣ DIAGNOSTIC COMMANDS

### Quick Health Check:

```bash
# 1. Check backend running and healthy
curl http://localhost:8000/docs

# 2. Check database connection
curl -X GET http://localhost:8000/districts

# 3. Test login
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin1","password":"Admin123!"}'

# 4. Check frontend
curl http://localhost:3000
```

### Enable Debug Logging:

**Backend:**

```python
# Add to main.py
import logging
logging.basicConfig(level=logging.DEBUG)

# See all SQL queries
export SQLALCHEMY_ECHO=True
```

**Frontend:**

```javascript
// Add to api.js
console.log("API Request:", method, path, data);
fetch(...)
  .then(r => {
    console.log("API Response:", r.status, r.data);
    return r;
  })
```

---

## ✅ FINAL CHECKLIST

Before asking for help, verify:

- [ ] Backend running: `http://localhost:8000/docs`
- [ ] Frontend running: `http://localhost:3000`
- [ ] MySQL running and accessible
- [ ] Database tables created
- [ ] CORS enabled in main.py
- [ ] API_BASE correct in api.js
- [ ] Browser localhost:3000 not blocked
- [ ] localStorage enabled
- [ ] No firewall blocking ports 3000/8000
- [ ] Clear browser cache (Ctrl+Shift+Delete)
- [ ] Restart browser after changes

---

## 📞 GETTING HELP

If issue persists, provide:

1. **Error message** (full text from console/terminal)
2. **Steps to reproduce** (exact steps causing the error)
3. **Screenshots** (browser console F12, terminal output)
4. **Environment** (OS, Python version, Node version)
5. **Backend logs** (from terminal running uvicorn)
6. **Browser console logs** (F12 → Console tab)

Good luck! 🚀
