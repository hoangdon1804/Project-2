import { useState, useEffect } from "react";
import "../styles/Dashboard.css";

const API_BASE = "http://localhost:8000";

export default function SalesDashboard() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [salesData, setSalesData] = useState(null);
  const [territories, setTerritories] = useState([]);
  const [selectedTerritory, setSelectedTerritory] = useState(null);
  const [loading, setLoading] = useState(true);

  const salesId = localStorage.getItem("user_id"); // Lấy user ID từ localStorage

  useEffect(() => {
    fetchSalesDashboard();
  }, []);

  const fetchSalesDashboard = async () => {
    try {
      if (!salesId) return;
      
      const res = await fetch(`${API_BASE}/sales/${salesId}/dashboard`);
      const data = await res.json();
      setSalesData(data);
      setTerritories(data.territories || []);
      setLoading(false);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Đang tải dữ liệu...</div>;
  }

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="header-content">
          <h1>Dashboard - Sales Person</h1>
          <div className="header-info">
        <span className="user-info">Sales</span>
            <button className="logout-btn" onClick={() => {
              localStorage.removeItem("token");
              localStorage.removeItem("user_id");
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
              className={`nav-item ${activeTab === "territories" ? "active" : ""}`}
              onClick={() => setActiveTab("territories")}
            >
            Phân Vùng Của Tôi
            </button>
            <button
              className={`nav-item ${activeTab === "stats" ? "active" : ""}`}
              onClick={() => setActiveTab("stats")}
            >
            Thống Kê
            </button>
          </nav>
        </aside>

        <main className="main-content">
          {/* Dashboard Tab */}
          {activeTab === "dashboard" && (
            <div className="content-section">
              <h2>Tổng Quan Phân Vùng Của Tôi</h2>
              <div className="stats-grid">
                <div className="stat-card">
          <div className="stat-icon">Phân vùng</div>
                  <div className="stat-info">
                    <h3>Số Phân Vùng</h3>
                    <p className="stat-number">{salesData?.num_territories || 0}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">Zone</div>
                  <div className="stat-info">
                    <h3>Tổng Zones</h3>
                    <p className="stat-number">{salesData?.total_zones || 0}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">Khách hàng</div>
                  <div className="stat-info">
                    <h3>Khách Hàng</h3>
                    <p className="stat-number">{salesData?.total_customers || 0}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">Đơn hàng</div>
                  <div className="stat-info">
                    <h3>Đơn Hàng</h3>
                    <p className="stat-number">{salesData?.total_orders || 0}</p>
                  </div>
                </div>
                <div className="stat-card">
          <div className="stat-icon">Doanh thu</div>
                  <div className="stat-info">
                    <h3>Doanh Thu</h3>
                    <p className="stat-number">${(salesData?.total_revenue || 0).toLocaleString()}</p>
                  </div>
                </div>
              </div>

              <div className="info-section">
                <h3>Hướng Dẫn</h3>
                <ul>
                  <li>Xem danh sách các phân vùng được giao cho bạn trong tab "Phân Vùng Của Tôi"</li>
                  <li>Mỗi phân vùng chứa một số zones (đơn vị cơ bản)</li>
                  <li>Xem số lượng khách hàng, đơn hàng và doanh thu cho mỗi phân vùng</li>
                  <li>Liên hệ Admin nếu cần điều chỉnh phân vùng</li>
                </ul>
              </div>
            </div>
          )}

          {/* Territories Tab */}
          {activeTab === "territories" && (
            <div className="content-section">
              <h2>Phân Vùng Được Giao Cho Tôi</h2>
              
              {territories.length === 0 ? (
                <p className="no-data">Bạn chưa được giao phân vùng nào</p>
              ) : (
                <>
                  <div className="territories-list">
                    {territories.map((territory) => (
                      <div
                        key={territory.id}
                        className={`territory-card ${selectedTerritory?.id === territory.id ? "active" : ""}`}
                        onClick={() => setSelectedTerritory(territory)}
                      >
                        <div className="territory-header">
                          <h3>{territory.territory_code}</h3>
                          <span className="badge">{territory.num_zones} Zones</span>
                        </div>
                        <div className="territory-stats">
                          <div className="stat-item">
                            <span>Khách Hàng:</span>
                            <strong>{territory.num_customers}</strong>
                          </div>
                          <div className="stat-item">
                            <span>Đơn Hàng:</span>
                            <strong>{territory.num_orders}</strong>
                          </div>
                          <div className="stat-item">
                            <span>Doanh Thu:</span>
                            <strong>${territory.total_revenue.toLocaleString()}</strong>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {selectedTerritory && (
                    <div className="territory-details">
                      <h3>Chi Tiết Phân Vùng: {selectedTerritory.territory_code}</h3>
                      <table className="details-table">
                        <tr>
                          <td>Mã Phân Vùng:</td>
                          <td>{selectedTerritory.territory_code}</td>
                        </tr>
                        <tr>
                          <td>Số Zones:</td>
                          <td>{selectedTerritory.num_zones}</td>
                        </tr>
                        <tr>
                          <td>Zone IDs:</td>
                          <td>{selectedTerritory.zone_ids?.join(", ") || "N/A"}</td>
                        </tr>
                        <tr>
                          <td>Tổng Khách Hàng:</td>
                          <td>{selectedTerritory.num_customers}</td>
                        </tr>
                        <tr>
                          <td>Tổng Đơn Hàng:</td>
                          <td>{selectedTerritory.num_orders}</td>
                        </tr>
                        <tr>
                          <td>Tổng Doanh Thu:</td>
                          <td>${selectedTerritory.total_revenue.toLocaleString()}</td>
                        </tr>
                        <tr>
                          <td>Thuật Toán Sử Dụng:</td>
                          <td>{selectedTerritory.algorithm_used || "Manual"}</td>
                        </tr>
                        <tr>
                          <td>Trạng Thái:</td>
                          <td>
                            <span className={selectedTerritory.is_active ? "status-active" : "status-inactive"}>
                              {selectedTerritory.is_active ? "Đang Hoạt Động" : "Không Hoạt Động"}
                            </span>
                          </td>
                        </tr>
                      </table>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Statistics Tab */}
          {activeTab === "stats" && (
            <div className="content-section">
              <h2>Thống Kê Phân Vùng</h2>
              
              {territories.length === 0 ? (
                <p className="no-data">Không có dữ liệu thống kê</p>
              ) : (
                <div className="stats-section">
                  <div className="stats-chart">
                    <h3>Phân Bố Khách Hàng</h3>
                    <div className="chart-placeholder">
                      {territories.map((t) => (
                        <div key={t.id} className="chart-bar">
                          <label>{t.territory_code}</label>
                          <div className="bar" style={{
                            height: `${(t.num_customers / Math.max(...territories.map(x => x.num_customers), 1)) * 200}px`,
                            backgroundColor: "#667eea"
                          }}></div>
                          <span>{t.num_customers}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="stats-table">
                    <h3>Chi Tiết Phân Vùng</h3>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Phân Vùng</th>
                          <th>Zones</th>
                          <th>Khách Hàng</th>
                          <th>Đơn Hàng</th>
                          <th>Doanh Thu</th>
                          <th>Tỷ Lệ %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {territories.map((t) => (
                          <tr key={t.id}>
                            <td>{t.territory_code}</td>
                            <td>{t.num_zones}</td>
                            <td>{t.num_customers}</td>
                            <td>{t.num_orders}</td>
                            <td>${t.total_revenue.toLocaleString()}</td>
                            <td>{((t.total_revenue / (salesData?.total_revenue || 1)) * 100).toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
