import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CircleMarker,
  GeoJSON,
  MapContainer,
  Popup,
  TileLayer,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "../styles/Dashboard.css";
import { API_BASE } from "../api";

const today = () => new Date().toISOString().slice(0, 10);

const currency = (value) =>
  new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));

const formatDateTime = (value) => {
  if (!value) return "N/A";
  return new Date(value).toLocaleString("vi-VN");
};

const getZoneCenter = (zone) => [
  Number(zone.center_lat || 21.0285),
  Number(zone.center_lng || 105.8542),
];

export default function SalesDashboard() {
  const salesId = localStorage.getItem("user_id");
  const [activeTab, setActiveTab] = useState("shift");
  const [profile, setProfile] = useState(null);
  const [profileForm, setProfileForm] = useState({
    email: "",
    full_name: "",
    phone: "",
  });
  const [shiftDate, setShiftDate] = useState(today());
  const [shift, setShift] = useState(null);
  const [history, setHistory] = useState([]);
  const [selectedZoneId, setSelectedZoneId] = useState("");
  const [position, setPosition] = useState(null);
  const [invoiceForm, setInvoiceForm] = useState({
    order_count: 1,
    customer_count: 1,
    amount: "",
    notes: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const zones = useMemo(() => shift?.zones || [], [shift]);
  const selectedZone = zones.find((zone) => Number(zone.id) === Number(selectedZoneId));

  const mapCenter = useMemo(() => {
    if (position) return [position.lat, position.lng];
    if (selectedZone) return getZoneCenter(selectedZone);
    if (zones.length) return getZoneCenter(zones[0]);
    return [21.0285, 105.8542];
  }, [position, selectedZone, zones]);

  const historySummary = useMemo(() => {
    return history.reduce(
      (sum, item) => ({
        zones: sum.zones.add(item.zone_id),
        revenue: sum.revenue + Number(item.total_revenue || 0),
        orders: sum.orders + Number(item.num_orders || 0),
        customers: sum.customers + Number(item.num_customers || 0),
      }),
      { zones: new Set(), revenue: 0, orders: 0, customers: 0 },
    );
  }, [history]);

  const loadProfile = useCallback(async () => {
    const res = await fetch(`${API_BASE}/sales/${salesId}/profile`);
    if (!res.ok) return;
    const data = await res.json();
    setProfile(data);
    setProfileForm({
      email: data.email || "",
      full_name: data.full_name || "",
      phone: data.phone || "",
    });
  }, [salesId]);

  const loadShift = useCallback(async () => {
    const res = await fetch(`${API_BASE}/sales/${salesId}/work-shift?date=${shiftDate}`);
    if (!res.ok) return;
    const data = await res.json();
    setShift(data);
    if (!selectedZoneId && data.zones?.length) {
      setSelectedZoneId(String(data.zones[0].id));
    }
  }, [salesId, selectedZoneId, shiftDate]);

  const loadHistory = useCallback(async () => {
    const res = await fetch(`${API_BASE}/sales/${salesId}/sales-history`);
    if (!res.ok) return;
    setHistory(await res.json());
  }, [salesId]);

  const loadInitialData = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadProfile(), loadShift(), loadHistory()]);
    setLoading(false);
  }, [loadHistory, loadProfile, loadShift]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  useEffect(() => {
    loadShift();
  }, [loadShift]);

  useEffect(() => {
    const timer = setInterval(loadShift, 30000);
    return () => clearInterval(timer);
  }, [loadShift]);

  const getCurrentLocation = () => {
    if (!navigator.geolocation) {
      setMessage("Trình duyệt không hỗ trợ lấy vị trí.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPosition({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
        setMessage("Đã cập nhật vị trí hiện tại.");
      },
      () => setMessage("Không thể lấy vị trí. Hãy kiểm tra quyền truy cập."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const saveProfile = async (event) => {
    event.preventDefault();
    setSaving(true);
    const res = await fetch(`${API_BASE}/sales/${salesId}/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profileForm),
    });
    const data = await res.json();
    setSaving(false);
    setMessage(res.ok ? data.msg : data.detail || "Không thể cập nhật hồ sơ");
    if (res.ok) await loadProfile();
  };

  const createInvoice = async (event) => {
    event.preventDefault();
    if (!selectedZoneId) {
      setMessage("Hãy chọn zone trước khi tạo hóa đơn.");
      return;
    }
    setSaving(true);
    const res = await fetch(`${API_BASE}/sales/${salesId}/invoices`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        zone_id: Number(selectedZoneId),
        order_count: Number(invoiceForm.order_count || 1),
        customer_count: Number(invoiceForm.customer_count || 1),
        amount: Number(invoiceForm.amount || 0),
        sold_at: new Date().toISOString(),
        current_lat: position?.lat,
        current_lng: position?.lng,
        notes: invoiceForm.notes,
      }),
    });
    const data = await res.json();
    setSaving(false);
    setMessage(res.ok ? data.msg : data.detail || "Không thể tạo hóa đơn");
    if (res.ok) {
      setInvoiceForm({ order_count: 1, customer_count: 1, amount: "", notes: "" });
      await Promise.all([loadShift(), loadHistory()]);
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("user_id");
    window.location.href = "/login";
  };

  if (loading) {
    return <div className="loading">Đang tải dữ liệu...</div>;
  }

  return (
    <div className="dashboard-container sales-dashboard">
      <header className="dashboard-header sales-header">
        <div className="header-content">
          <div>
            <h1>Sales Workspace</h1>
            <p>{profile?.full_name || profile?.username || "Sales"}</p>
          </div>
          <div className="header-info">
            <span className="user-info">{profile?.region_name || "Chưa gán khu vực"}</span>
            <button className="logout-btn" onClick={logout}>
              Đăng xuất
            </button>
          </div>
        </div>
      </header>

      <div className="dashboard-wrapper">
        <aside className="sidebar">
          <nav className="nav-menu">
            <button
              className={`nav-item ${activeTab === "shift" ? "active" : ""}`}
              onClick={() => setActiveTab("shift")}
            >
              Ca làm việc
            </button>
            <button
              className={`nav-item ${activeTab === "history" ? "active" : ""}`}
              onClick={() => setActiveTab("history")}
            >
              Lịch sử bán hàng
            </button>
            <button
              className={`nav-item ${activeTab === "profile" ? "active" : ""}`}
              onClick={() => setActiveTab("profile")}
            >
              Hồ sơ
            </button>
          </nav>
        </aside>

        <main className="main-content">
          {message && <div className="notice-bar">{message}</div>}

          {activeTab === "shift" && (
            <section className="content-section">
              <div className="section-header">
                <div>
                  <h2>Ca làm việc được giao</h2>
                  <p className="muted-text">
                    {shift?.has_shift
                      ? `${shift.territory?.name || "Phân vùng"} - ${shift.territory?.region_name || ""}`
                      : "Chưa có phân công cho ngày đã chọn"}
                  </p>
                </div>
                <div className="inline-actions">
                  <input
                    type="date"
                    value={shiftDate}
                    onChange={(event) => setShiftDate(event.target.value)}
                  />
                  <button className="btn-secondary" onClick={getCurrentLocation}>
                    Lấy vị trí
                  </button>
                </div>
              </div>

              <div className="stats-grid sales-stats-grid">
                <div className="stat-card calm-card">
                  <div className="stat-info">
                    <h3>Zones được chia</h3>
                    <p className="stat-number">{shift?.summary?.total_zones || 0}</p>
                  </div>
                </div>
                <div className="stat-card green-card">
                  <div className="stat-info">
                    <h3>Doanh thu</h3>
                    <p className="stat-number">{currency(shift?.summary?.total_revenue)}</p>
                  </div>
                </div>
                <div className="stat-card amber-card">
                  <div className="stat-info">
                    <h3>Đơn hàng</h3>
                    <p className="stat-number">{shift?.summary?.total_orders || 0}</p>
                  </div>
                </div>
                <div className="stat-card teal-card">
                  <div className="stat-info">
                    <h3>Khách hàng</h3>
                    <p className="stat-number">{shift?.summary?.total_customers || 0}</p>
                  </div>
                </div>
              </div>

              {!shift?.has_shift ? (
                <div className="empty-state">
                  <p>Admin chưa giao ca cho ngày này. Màn hình sẽ tự cập nhật mỗi 30 giây.</p>
                </div>
              ) : (
                <div className="sales-work-grid">
                  <div className="sales-map-panel">
                    <MapContainer center={mapCenter} zoom={13} className="sales-map">
                      <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                      />
                      {zones.map((zone) =>
                        zone.geometry ? (
                          <GeoJSON
                            key={`${zone.id}-${selectedZoneId}`}
                            data={zone.geometry}
                            style={{
                              color: Number(zone.id) === Number(selectedZoneId) ? "#0f766e" : "#2563eb",
                              weight: Number(zone.id) === Number(selectedZoneId) ? 3 : 2,
                              fillOpacity: 0.18,
                            }}
                            eventHandlers={{
                              click: () => setSelectedZoneId(String(zone.id)),
                            }}
                          >
                            <Popup>{zone.name}</Popup>
                          </GeoJSON>
                        ) : (
                          <CircleMarker
                            key={zone.id}
                            center={getZoneCenter(zone)}
                            radius={Number(zone.id) === Number(selectedZoneId) ? 10 : 7}
                            pathOptions={{ color: "#2563eb", fillOpacity: 0.7 }}
                            eventHandlers={{
                              click: () => setSelectedZoneId(String(zone.id)),
                            }}
                          >
                            <Popup>{zone.name}</Popup>
                          </CircleMarker>
                        ),
                      )}
                      {position && (
                        <CircleMarker
                          center={[position.lat, position.lng]}
                          radius={9}
                          pathOptions={{ color: "#dc2626", fillColor: "#dc2626", fillOpacity: 0.9 }}
                        >
                          <Popup>Vị trí hiện tại</Popup>
                        </CircleMarker>
                      )}
                    </MapContainer>
                  </div>

                  <div className="work-panel">
                    <h3>Zones trong ca</h3>
                    <div className="zone-pick-list">
                      {zones.map((zone) => (
                        <button
                          key={zone.id}
                          className={`zone-pick ${Number(zone.id) === Number(selectedZoneId) ? "active" : ""}`}
                          onClick={() => setSelectedZoneId(String(zone.id))}
                        >
                          <strong>{zone.name}</strong>
                          <span>
                            {zone.num_orders || 0} đơn - {currency(zone.revenue)}
                          </span>
                        </button>
                      ))}
                    </div>

                    <form className="invoice-form" onSubmit={createInvoice}>
                      <h3>Tạo hóa đơn</h3>
                      <label>
                        Zone hiện tại
                        <select
                          value={selectedZoneId}
                          onChange={(event) => setSelectedZoneId(event.target.value)}
                        >
                          {zones.map((zone) => (
                            <option key={zone.id} value={zone.id}>
                              {zone.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="form-row">
                        <label>
                          Số đơn
                          <input
                            type="number"
                            min="1"
                            value={invoiceForm.order_count}
                            onChange={(event) =>
                              setInvoiceForm({ ...invoiceForm, order_count: event.target.value })
                            }
                          />
                        </label>
                        <label>
                          Số khách
                          <input
                            type="number"
                            min="0"
                            value={invoiceForm.customer_count}
                            onChange={(event) =>
                              setInvoiceForm({ ...invoiceForm, customer_count: event.target.value })
                            }
                          />
                        </label>
                      </div>
                      <label>
                        Giá tiền
                        <input
                          type="number"
                          min="0"
                          value={invoiceForm.amount}
                          onChange={(event) =>
                            setInvoiceForm({ ...invoiceForm, amount: event.target.value })
                          }
                          required
                        />
                      </label>
                      <label>
                        Ghi chú
                        <textarea
                          rows="3"
                          value={invoiceForm.notes}
                          onChange={(event) =>
                            setInvoiceForm({ ...invoiceForm, notes: event.target.value })
                          }
                        />
                      </label>
                      <div className="location-readout">
                        Vi tri:{" "}
                        {position
                          ? `${position.lat.toFixed(5)}, ${position.lng.toFixed(5)}`
                          : "Chưa lấy vị trí"}
                      </div>
                      <button className="btn-success full-width" disabled={saving}>
                        {saving ? "Đang lưu..." : "Lưu hóa đơn"}
                      </button>
                    </form>
                  </div>
                </div>
              )}
            </section>
          )}

          {activeTab === "history" && (
            <section className="content-section">
              <h2>Lịch sử bán hàng</h2>
              <div className="stats-grid sales-stats-grid">
                <div className="stat-card calm-card">
                  <div className="stat-info">
                    <h3>Phân vùng đã ghi nhận</h3>
                    <p className="stat-number">{historySummary.zones.size}</p>
                  </div>
                </div>
                <div className="stat-card green-card">
                  <div className="stat-info">
                    <h3>Doanh thu lịch sử</h3>
                    <p className="stat-number">{currency(historySummary.revenue)}</p>
                  </div>
                </div>
                <div className="stat-card amber-card">
                  <div className="stat-info">
                    <h3>Đơn hàng</h3>
                    <p className="stat-number">{historySummary.orders}</p>
                  </div>
                </div>
                <div className="stat-card teal-card">
                  <div className="stat-info">
                    <h3>Khách hàng</h3>
                    <p className="stat-number">{historySummary.customers}</p>
                  </div>
                </div>
              </div>

              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Thời gian</th>
                      <th>Phân vùng</th>
                      <th>Zone</th>
                      <th>Doanh thu</th>
                      <th>Số đơn</th>
                      <th>Khách hàng</th>
                      <th>Ghi chú</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((item) => (
                      <tr key={item.id}>
                        <td>{formatDateTime(item.updated_at)}</td>
                        <td>{item.territory_name || "N/A"}</td>
                        <td>{item.zone_name || item.zone_code || item.zone_id}</td>
                        <td>{currency(item.total_revenue)}</td>
                        <td>{item.num_orders}</td>
                        <td>{item.num_customers}</td>
                        <td>{item.notes || ""}</td>
                      </tr>
                    ))}
                    {!history.length && (
                      <tr>
                        <td colSpan="7">Chưa có lịch sử bán hàng.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {activeTab === "profile" && (
            <section className="content-section profile-section">
              <h2>Chỉnh sửa hồ sơ</h2>
              <form className="profile-form" onSubmit={saveProfile}>
                <label>
                  Username
                  <input value={profile?.username || ""} disabled />
                </label>
                <label>
                  Họ và tên
                  <input
                    value={profileForm.full_name}
                    onChange={(event) =>
                      setProfileForm({ ...profileForm, full_name: event.target.value })
                    }
                  />
                </label>
                <label>
                  Email
                  <input
                    type="email"
                    value={profileForm.email}
                    onChange={(event) =>
                      setProfileForm({ ...profileForm, email: event.target.value })
                    }
                  />
                </label>
                <label>
                  Số điện thoại
                  <input
                    value={profileForm.phone}
                    onChange={(event) =>
                      setProfileForm({ ...profileForm, phone: event.target.value })
                    }
                  />
                </label>
                <label>
                  Khu vực
                  <input value={profile?.region_name || "Chưa gán khu vực"} disabled />
                </label>
                <button className="btn-success" disabled={saving}>
                  {saving ? "Đang lưu..." : "Lưu hồ sơ"}
                </button>
              </form>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
