import { useState, useEffect } from "react";
import "../styles/Dashboard.css";

const API_BASE = "http://localhost:8000";

export default function CustomerDashboard() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);

  const customerId = localStorage.getItem("user_id");

  useEffect(() => {
    // Tải thông tin người dùng từ localStorage
    const userInfo = JSON.parse(localStorage.getItem("user_info") || "{}");
    setUserData(userInfo);
    setLoading(false);
  }, []);

  if (loading) {
    return <div className="loading">Đang tải dữ liệu...</div>;
  }

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="header-content">
          <h1>Dashboard - Khách Hàng</h1>
          <div className="header-info">
        <span className="user-info">Khách Hàng - {userData?.full_name || "Khách"}</span>
            <button className="logout-btn" onClick={() => {
              localStorage.removeItem("token");
              localStorage.removeItem("user_id");
              localStorage.removeItem("user_info");
              window.location.href = "/login";
            }}>
              Đăng xuất
            </button>
          </div>
        </div>
      </header>

      <div className="dashboard-wrapper">
        <aside className="sidebar">
          <nav className="nav-menu">
            <button
              className={`nav-item ${activeTab === "dashboard" ? "active" : ""}`}
              onClick={() => setActiveTab("dashboard")}
            >
            Dashboard
            </button>
            <button
              className={`nav-item ${activeTab === "profile" ? "active" : ""}`}
              onClick={() => setActiveTab("profile")}
            >
            Hồ Sơ Cá Nhân
            </button>
            <button
              className={`nav-item ${activeTab === "orders" ? "active" : ""}`}
              onClick={() => setActiveTab("orders")}
            >
            Đơn Hàng
            </button>
            <button
              className={`nav-item ${activeTab === "sales-rep" ? "active" : ""}`}
              onClick={() => setActiveTab("sales-rep")}
            >
            Sales Đảm Nhiệm
            </button>
          </nav>
        </aside>

        <main className="main-content">
          {/* Dashboard Tab */}
          {activeTab === "dashboard" && (
            <div className="content-section">
              <h2>Thông Tin Khách Hàng</h2>
              <div className="stats-grid">
                <div className="stat-card">
          <div className="stat-icon">ID</div>
                  <div className="stat-info">
                    <h3>Mã Khách Hàng</h3>
                    <p className="stat-number">#{customerId}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">Email</div>
                  <div className="stat-info">
                    <h3>Email</h3>
                    <p className="stat-number" style={{ fontSize: "14px" }}>{userData?.email || "N/A"}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">SĐT</div>
                  <div className="stat-info">
                    <h3>Điện Thoại</h3>
                    <p className="stat-number" style={{ fontSize: "14px" }}>{userData?.phone || "N/A"}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">Trạng thái</div>
                  <div className="stat-info">
                    <h3>Trạng Thái</h3>
                    <p className="stat-number" style={{ fontSize: "14px", color: "#4caf50" }}>Hoạt Động</p>
                  </div>
                </div>
              </div>

              <div className="info-section">
                <h3>Chào Mừng Bạn!</h3>
                <p>
                  Bạn đang sử dụng hệ thống quản lý territory design. 
                  Hãy kiểm tra thông tin sales person được giao cho khu vực của bạn, 
                  hoặc xem lịch sử đơn hàng của mình.
                </p>
              </div>
            </div>
          )}

          {/* Profile Tab */}
          {activeTab === "profile" && (
            <div className="content-section">
              <h2>Hồ Sơ Cá Nhân</h2>
              <div className="profile-card">
                <div className="profile-item">
                  <label>Tên Đầy Đủ:</label>
                  <p>{userData?.full_name || "Chưa cập nhật"}</p>
                </div>
                <div className="profile-item">
                  <label>Email:</label>
                  <p>{userData?.email || "Chưa cập nhật"}</p>
                </div>
                <div className="profile-item">
                  <label>Số Điện Thoại:</label>
                  <p>{userData?.phone || "Chưa cập nhật"}</p>
                </div>
                <div className="profile-item">
                  <label>Vai Trò:</label>
                  <p>
                    <span className="badge">Khách Hàng</span>
                  </p>
                </div>
                <div className="profile-item">
                  <label>Ngày Đăng Ký:</label>
                  <p>{userData?.created_at ? new Date(userData.created_at).toLocaleDateString("vi-VN") : "N/A"}</p>
                </div>
              </div>
            </div>
          )}

          {/* Orders Tab */}
          {activeTab === "orders" && (
            <div className="content-section">
              <h2>Lịch Sử Đơn Hàng</h2>
              <p className="info-text">
                Tính năng xem đơn hàng sẽ được tích hợp trong phiên bản tiếp theo của ứng dụng.
              </p>
              <div className="placeholder-section">
            <p>Đơn Hàng (Đang Phát Triển)</p>
              </div>
            </div>
          )}

          {/* Sales Rep Tab */}
          {activeTab === "sales-rep" && (
            <div className="content-section">
              <h2>Sales Person Đảm Nhiệm Khu Vực Của Tôi</h2>
              <p className="info-text">
                Thông tin về sales person được giao cho khu vực của bạn:
              </p>
              <div className="sales-rep-card">
                <div className="rep-item">
                  <label>Tên Sales:</label>
                  <p className="rep-info">Sẽ được cập nhật dựa trên vị trí của bạn</p>
                </div>
                <div className="rep-item">
                  <label>Email:</label>
                  <p className="rep-info">Sẽ được cập nhật dựa trên vị trí của bạn</p>
                </div>
                <div className="rep-item">
                  <label>Điện Thoại:</label>
                  <p className="rep-info">Sẽ được cập nhật dựa trên vị trí của bạn</p>
                </div>
                <div className="rep-item">
                  <label>Khu Vực Đảm Nhiệm:</label>
                  <p className="rep-info">Sẽ được cập nhật dựa trên vị trí của bạn</p>
                </div>
              </div>
              <p className="note">
            Hệ thống sẽ tự động xác định sales person phụ trách khu vực của bạn dựa trên vị trí địa lý.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
