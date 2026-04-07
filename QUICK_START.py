#!/usr/bin/env python3
"""
Quick Start Guide - Commercial Territory Design System
Hướng dẫn bắt đầu nhanh chóng
"""

import os
import sys

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def print_section(text):
    print(f"\n📌 {text}")
    print("-" * 60)

def main():
    print_header("🎯 COMMERCIAL TERRITORY DESIGN SYSTEM")
    
    print("""
    Hệ thống quản lý và tối ưu hóa phân vùng bán hàng dựa trên:
    ✓ K-Means Clustering (vị trí địa lý)
    ✓ Greedy Seed Growth (cân bằng tải)
    ✓ Local Search (tối ưu hóa)
    """)

    # Step 1: Setup Backend
    print_section("Bước 1: CẤU HÌNH BACKEND")
    print("""
    1.1 Cài đặt dependencies:
        $ cd backend
        $ pip install fastapi sqlalchemy sqlalchemy-utils python-jose passlib bcrypt
        
    1.2 Kiểm tra MySQL/Database:
        - Đảm bảo MySQL đang chạy
        - Tạo database (nếu cần)
        
    1.3 Chạy backend server:
        $ cd backend
        $ python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
        
        ✓ Server sẽ chạy tại http://localhost:8000
        ✓ API docs: http://localhost:8000/docs
    """)

    # Step 2: Setup Frontend
    print_section("Bước 2: CẤU HÌNH FRONTEND")
    print("""
    2.1 Cài đặt Node.js dependencies:
        $ cd frontend
        $ npm install
        
    2.2 Chạy frontend development server:
        $ npm start
        
        ✓ App sẽ chạy tại http://localhost:3000
        ✓ Tự động reload khi có thay đổi
    """)

    # Step 3: Test
    print_section("Bước 3: KIỂM TRA HỆ THỐNG")
    print("""
    3.1 Đăng nhập:
        - Vào http://localhost:3000
        - Đăng ký tài khoản mới hoặc dùng tài khoản test
        
    3.2 Quyền truy cập:
        - admin   → /admin    → Dashboard quản lý
        - sales   → /sales    → Xem phân vùng được giao
        - customer → /customer → Thông tin khách hàng
    """)

    # Step 4: Test Data
    print_section("Bước 4: TẠO DỮ LIỆU TEST")
    print("""
    4.1 Admin: Tạo District
        - Vào Admin Dashboard
        - Sidebar → Thêm Quận
        - Nhập thông tin: Mã, Tên, Tọa độ
        
    4.2 Admin: Tạo Zones
        - Chọn District
        - Tab "Quản Lý Zones" → Thêm Zone
        - Nhập: Mã, Tên, Tọa độ (lat, lng)
        - Nhập: Số khách hàng, đơn hàng, doanh thu
        
    4.3 Admin: Cập nhật Activity
        - Chọn Zone → Cập Nhật
        - Nhập thông tin hoạt động
        
    4.4 Admin: Chạy Thuật Toán
        - Tab "Thuật Toán"
        - Chọn thuật toán
        - Nhập số phân vùng
        - Xem kết quả
    """)

    # Key Features
    print_section("🌟 CÁC TÍNH NĂNG CHÍNH")
    print("""
    ADMIN:
    ✓ Quản lý districts (quận/huyện)
    ✓ Quản lý zones (đơn vị cơ bản)
    ✓ Nhập thông tin activity cho zones
    ✓ Chạy 3 thuật toán chia phân vùng
    ✓ Gán phân vùng cho sales person
    ✓ Xem thống kê hệ thống
    
    SALES:
    ✓ Xem phân vùng được giao
    ✓ Xem thông tin zones trong phân vùng
    ✓ Xem thống kê doanh số
    ✓ Biểu đồ phân bố khách hàng
    
    CUSTOMER:
    ✓ Xem thông tin cá nhân
    ✓ Xem sales person phụ trách (tương lai)
    ✓ Xem lịch sử đơn hàng (tương lai)
    """)

    # API Tests
    print_section("🔧 TEST API")
    print("""
    Dùng Postman hoặc curl để test:
    
    1. Đăng ký:
       POST /register
       {
         "username": "admin1",
         "email": "admin@example.com",
         "password": "Admin123!",
         "role": "admin",
         "full_name": "Admin User",
         "phone": "0123456789"
       }
    
    2. Đăng nhập:
       POST /login
       {
         "username": "admin1",
         "password": "Admin123!"
       }
    
    3. Tạo District:
       POST /districts
       {
         "code": "HN001",
         "name": "Hà Nội",
         "center_lat": 21.0285,
         "center_lng": 105.8542
       }
    
    4. Tạo Zone:
       POST /zones
       {
         "zone_code": "Z001",
         "district_id": 1,
         "name": "Zone 1",
         "center_lat": 21.03,
         "center_lng": 105.85,
         "num_customers": 50,
         "num_orders": 100,
         "revenue": 5000000
       }
    
    5. Chạy K-Means:
       POST /algorithms/kmeans
       {
         "district_id": 1,
         "num_clusters": 3,
         "max_iterations": 100
       }
    """)

    # Troubleshooting
    print_section("⚠️  KHẮC PHỤC SỰ CỐ")
    print("""
    Backend không kết nối:
    - Kiểm tra port 8000 có bị chiếm không
    - Kiểm tra CORS configuration trong main.py
    - Xem logs: python -m uvicorn main:app --reload --log-level debug
    
    Database errors:
    - Kiểm tra MySQL running
    - Kiểm tra database.py connection string
    - Chạy: alembic upgrade head (nếu có migrations)
    
    Frontend không load:
    - Xóa node_modules: rm -rf node_modules
    - Reinstall: npm install
    - Xóa cache: npm cache clean --force
    - Chạy lại: npm start
    
    API 404 errors:
    - Kiểm tra API endpoint URL
    - Kiểm tra route definition trong routes.py
    - Kiểm tra API_BASE trong file JavaScript (phải là http://localhost:8000)
    """)

    # Performance Tips
    print_section("⚡ TỐI ƯU HIỆU NĂNG")
    print("""
    1. Database:
       - Tạo indexes cho fields hay query
       - Optimize queries n+1
       - Pagination cho large datasets
    
    2. Frontend:
       - Code splitting
       - Lazy loading
       - Memoization cho components
    
    3. Algorithms:
       - Adjust max_iterations
       - Optimize distance calculations
       - Cache results
    
    4. Deployment:
       - Use production ASGI server (gunicorn)
       - Enable gzip compression
       - Cache responses
       - CDN for static assets
    """)

    # Next Steps
    print_section("📚 BƯỚC TIẾP THEO")
    print("""
    Tích hợp Map:
    1. Install leaflet hoặc Google Maps API
    2. Tạo component để vẽ zones
    3. Thêm drag-and-drop để điều chỉnh
    
    Cải Thiện Thuật Toán:
    1. Thêm constraints (max distance, max zones)
    2. Implement Genetic Algorithm
    3. Add visualizations cho kết quả
    
    DevOps:
    1. Dockerize application
    2. Setup CI/CD pipeline
    3. Deploy lên cloud (AWS, Azure, GCP)
    """)

    # Support
    print_section("💬 HỖ TRỢ VÀ TÀI LIỆU")
    print("""
    - README_TERRITORY_DESIGN.md - Tài liệu chi tiết
    - backend/algorithms.py - Chi tiết thuật toán
    - API Documentation: http://localhost:8000/docs
    - Frontend Components: src/pages/
    """)

    print_header("✅ SẴN SÀNG BẮT ĐẦU!")
    print("""
    Chúc bạn thành công! 🚀
    
    Nếu có vấn đề:
    1. Kiểm tra logs
    2. Đọc README_TERRITORY_DESIGN.md
    3. Test API endpoints bằng Postman
    4. Kiểm tra network tab trong DevTools
    """)

if __name__ == "__main__":
    main()
