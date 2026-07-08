# Territory Design System

Ứng dụng web hỗ trợ quản lý khu vực bán hàng, quản lý phân vùng/zone và phân công công việc hằng ngày cho đội ngũ sale. Hệ thống gồm frontend React, backend FastAPI và cơ sở dữ liệu SQLite.

## Chức năng chính

- Đăng nhập, đăng ký tài khoản sale và duyệt tài khoản sale.
- Admin quản lý khu vực, phân vùng và zone.
- Admin lấy dữ liệu phường/xã từ OpenStreetMap.
- Admin tự vẽ zone mới trên bản đồ.
- Admin chạy thuật toán phân công zone cho sale theo ngày.
- Admin lưu/chốt kết quả phân công.
- Sale xem ca làm việc, zone được giao và ghi nhận hóa đơn/doanh thu.

## Công nghệ

### Backend

- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- JWT
- Shapely
- OpenStreetMap / Overpass API

### Frontend

- React
- React Router
- Axios / Fetch API
- Leaflet / React-Leaflet
- CSS

## Cấu trúc thư mục

```text
.
├── backend/
│   ├── main.py
│   ├── routes.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── auth.py
│   ├── algorithms.py
│   └── external_services.py
├── frontend/
│   ├── package.json
│   └── src/
├── requirements.txt
└── README.md
```

## Cài đặt và chạy dự án

### 1. Clone repository

```bash
git clone <repo-url>
cd <repo-folder>
```

### 2. Chạy backend

Tạo môi trường ảo:

```bash
python -m venv .venv
```

Kích hoạt môi trường ảo trên Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Hoặc trên macOS/Linux:

```bash
source .venv/bin/activate
```

Cài dependencies:

```bash
pip install -r requirements.txt
```

Chạy backend:

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend chạy tại:

```text
http://localhost:8000
```

Swagger docs:

```text
http://localhost:8000/docs
```

### 3. Tạo dữ liệu tài khoản mẫu

Mở terminal khác, kích hoạt môi trường ảo rồi chạy:

```bash
cd backend
python create_test_accounts.py
```

Script này tạo tài khoản mẫu để đăng nhập thử.

### 4. Chạy frontend

```bash
cd frontend
npm install
npm start
```

Frontend chạy tại:

```text
http://localhost:3000
```

## Tài khoản mẫu

Sau khi chạy `backend/create_test_accounts.py`, có thể dùng:

```text
Admin: admin1 / Admin123!
Sales: sales1 / Sales123!
```

## Ghi chú dữ liệu

- File `app.db` là database SQLite local và không nên push lên GitHub.
- Khi chạy backend lần đầu, SQLAlchemy sẽ tự tạo các bảng cần thiết.
- Nếu cần reset dữ liệu, có thể xóa `app.db` ở máy local rồi chạy lại backend và script tạo tài khoản mẫu.

## Build frontend

```bash
cd frontend
npm run build
```

Thư mục `frontend/build` là output build và không cần commit.

## Lưu ý khi push GitHub

Các thư mục/file sau đã được đưa vào `.gitignore`:

- `.venv/`
- `app.db`
- `__pycache__/`
- `frontend/node_modules/`
- `frontend/build/`
- log dev server
- `.env`

Chỉ nên commit source code, file cấu hình, `README.md`, `requirements.txt`, `frontend/package.json` và `frontend/package-lock.json`.
