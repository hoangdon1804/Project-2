import { useState } from "react";
import "../styles/Dashboard.css";

export default function UserDashboard() {
  const [activeTab, setActiveTab] = useState("dashboard");

  const [orders, setOrders] = useState([
    { id: 1, product: "Sản phẩm A", date: "2026-03-10", amount: 500000, status: "Hoàn thành", shipper: "Nguyễn Văn C" },
    { id: 2, product: "Sản phẩm B", date: "2026-03-09", amount: 150000, status: "Hoàn thành", shipper: "Lê Văn D" },
    { id: 3, product: "Sản phẩm C", date: "2026-03-11", amount: 300000, status: "Chưa giao", shipper: "Nguyễn Văn C" },
    { id: 4, product: "Sản phẩm D", date: "2026-03-08", amount: 200000, status: "Hoàn thành", shipper: "Trần Văn E" },
  ]);

  const pendingOrders = orders.filter(o => o.status === "Chưa giao");
  const completedOrders = orders.filter(o => o.status === "Hoàn thành");

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="header-content">
          <h1>Dashboard Người dùng</h1>
          <div className="header-info">
        <span className="user-info">User</span>
            <button className="logout-btn">Đăng xuất</button>
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
              className={`nav-item ${activeTab === "pending" ? "active" : ""}`}
              onClick={() => setActiveTab("pending")}
            >
            Đơn hàng Chưa giao
            </button>
            <button
              className={`nav-item ${activeTab === "history" ? "active" : ""}`}
              onClick={() => setActiveTab("history")}
            >
            Lịch sử Đơn hàng
            </button>
          </nav>
        </aside>

        <main className="main-content">
          {/* Dashboard Tab */}
          {activeTab === "dashboard" && (
            <div className="content-section">
              <h2>Tổng quan Đơn hàng của bạn</h2>
              <div className="stats-grid">
                <div className="stat-card">
          <div className="stat-icon">Đơn hàng</div>
                  <div className="stat-info">
                    <h3>Tổng Đơn hàng</h3>
                    <p className="stat-number">{orders.length}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">Hoàn thành</div>
                  <div className="stat-info">
                    <h3>Hoàn thành</h3>
                    <p className="stat-number">{completedOrders.length}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">Đang chờ</div>
                  <div className="stat-info">
                    <h3>Chưa giao</h3>
                    <p className="stat-number">{pendingOrders.length}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">Doanh thu</div>
                  <div className="stat-info">
                    <h3>Tổng chi tiêu</h3>
                    <p className="stat-number">{orders.reduce((sum, o) => sum + o.amount, 0).toLocaleString()} ₫</p>
                  </div>
                </div>
              </div>

              <div className="dashboard-charts">
                <div className="chart-container">
                  <h3>Đơn hàng gần đây</h3>
                  {orders.slice(0, 5).map(order => (
                    <div key={order.id} className="order-summary">
                      <div className="order-summary-info">
                        <strong>{order.product}</strong>
                        <p>{order.date}</p>
                      </div>
                      <div className="order-summary-amount">
                        {order.amount.toLocaleString()} ₫
                      </div>
                      <div className="order-summary-status">
                        <span className={`status-badge status-${order.status.toLowerCase().replace(" ", "-")}`}>
                          {order.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Pending Orders Tab */}
          {activeTab === "pending" && (
            <div className="content-section">
              <div className="section-header">
                <h2>Đơn hàng Chưa giao</h2>
              </div>

              {pendingOrders.length === 0 ? (
                <div className="empty-state">
            <p>Không có đơn hàng chưa giao</p>
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Sản phẩm</th>
                      <th>Ngày đặt</th>
                      <th>Giá</th>
                      <th>Shipper</th>
                      <th>Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingOrders.map(order => (
                      <tr key={order.id}>
                        <td>{order.id}</td>
                        <td>{order.product}</td>
                        <td>{order.date}</td>
                        <td>{order.amount.toLocaleString()} ₫</td>
                        <td>{order.shipper}</td>
                        <td>
                          <span className="status-badge status-chưa-giao">
                            {order.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* Order History Tab */}
          {activeTab === "history" && (
            <div className="content-section">
              <div className="section-header">
                <h2>Lịch sử Đơn hàng</h2>
              </div>

              {orders.length === 0 ? (
                <div className="empty-state">
            <p>Không có lịch sử đơn hàng</p>
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Sản phẩm</th>
                      <th>Ngày đặt</th>
                      <th>Giá</th>
                      <th>Shipper</th>
                      <th>Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map(order => (
                      <tr key={order.id}>
                        <td>{order.id}</td>
                        <td>{order.product}</td>
                        <td>{order.date}</td>
                        <td>{order.amount.toLocaleString()} ₫</td>
                        <td>{order.shipper}</td>
                        <td>
                          <span className={`status-badge status-${order.status.toLowerCase().replace(" ", "-")}`}>
                            {order.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
