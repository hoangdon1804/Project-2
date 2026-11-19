import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, Popup } from "react-leaflet";
import L from "leaflet";
import { API_BASE } from "../api";
import "../styles/AlgorithmComparison.css";

// Bảng màu dùng chung: sales thứ i (theo thứ tự đã chọn) có cùng màu trên mọi bản đồ.
const PALETTE = [
  "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
  "#42d4f4", "#f032e6", "#9a6324", "#469990", "#800000",
  "#808000", "#000075", "#bfef45", "#fabed4", "#dcbeff",
  "#aaffc3", "#ffd8b1", "#a9a9a9", "#fffac8", "#000000",
];
export const comparisonColor = (index) => PALETTE[index % PALETTE.length];

// Tính lại các chỉ số so sánh cho một phân công {sales_id: [zone_ids]} (dùng sau khi sửa tay).
export async function evaluateAssignment(territoryId, assignment, tolerance = 0.05) {
  const res = await fetch(`${API_BASE}/admin/evaluate-assignment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ territory_id: territoryId, assignment, tolerance: Number(tolerance) }),
  });
  const data = await res.json();
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : data.detail;
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return data.metrics;
}

// Chuyển zone sang sales khác (salesId = null: bỏ giao). Trả về object mới.
export function moveZone(assignment, zoneId, salesId) {
  const next = {};
  Object.entries(assignment || {}).forEach(([sid, zoneIds]) => {
    next[sid] = (zoneIds || []).map(Number).filter((id) => id !== Number(zoneId));
  });
  if (salesId !== null && salesId !== undefined && !Number.isNaN(Number(salesId))) {
    const key = String(salesId);
    next[key] = [...(next[key] || []), Number(zoneId)];
  }
  return next;
}

const DEFAULT_CENTER = [21.0285, 105.8542];
const DEFAULT_SELECTION = ["grasp", "probvns", "milp_center"];

const STATUS = {
  OK: { label: "Thành công", tone: "ok" },
  FEASIBLE_TIME_LIMIT: { label: "Có nghiệm, chưa chứng minh tối ưu", tone: "ok" },
  TIME_LIMIT: { label: "Hết thời gian", tone: "warn" },
  INFEASIBLE: { label: "Vô nghiệm", tone: "bad" },
  TIMEOUT: { label: "Bị dừng (quá giờ)", tone: "bad" },
  SKIPPED: { label: "Bỏ qua", tone: "warn" },
  UNAVAILABLE: { label: "Không khả dụng", tone: "bad" },
  FAILED: { label: "Thất bại", tone: "bad" },
  ERROR: { label: "Lỗi", tone: "bad" },
};
const statusInfo = (status) =>
  STATUS[status] ||
  (String(status).startsWith("NO_SOLUTION") || String(status).startsWith("GAMSPY")
    ? { label: "Không tìm được nghiệm", tone: "bad" }
    : { label: status, tone: "warn" });

// Hàng của bảng so sánh: better = "min" thì giá trị nhỏ nhất (trong các kết quả có nghiệm) được tô đậm.
export const METRIC_ROWS = [
  { key: "wall_seconds", label: "Thời gian chạy (s)", better: "min", digits: 1, fromReport: true },
  { key: "cv_pct", label: "CV workload (%)", better: "min", digits: 2 },
  { key: "hoover_index", label: "Chỉ số Hoover (%)", better: "min", digits: 2 },
  { key: "max_dev_customers_pct", label: "Lệch khách hàng lớn nhất (%)", better: "min", digits: 1 },
  { key: "max_dev_orders_pct", label: "Lệch đơn hàng lớn nhất (%)", better: "min", digits: 1 },
  { key: "balance_violation", label: "Vi phạm cân bằng ±τ (G)", better: "min", digits: 4 },
  { key: "max_diameter_km", label: "Đường kính vùng lớn nhất (km)", better: "min", digits: 2 },
  { key: "max_radius_km", label: "Bán kính vùng lớn nhất (km)", better: "min", digits: 2 },
  { key: "sum_median_km", label: "Tổng khoảng cách tới tâm vùng (km)", better: "min", digits: 2 },
  { key: "disconnected_territories", label: "Vùng không liên thông", better: "min", digits: 0 },
  { key: "empty_territories", label: "Sales không có zone", better: "min", digits: 0 },
];

const metricValue = (report, row) => {
  const source = row.fromReport ? report : report.metrics;
  const value = source ? source[row.key] : null;
  return typeof value === "number" ? value : null;
};

function ResultMap({ report, zones, salesIds, salesName, bounds, onReassign, disabled }) {
  const ownerOf = useMemo(() => {
    const owner = new Map();
    Object.entries(report.assignment || {}).forEach(([salesId, zoneIds]) => {
      (zoneIds || []).forEach((zoneId) => owner.set(Number(zoneId), Number(salesId)));
    });
    return owner;
  }, [report.assignment]);

  return (
    <MapContainer
      bounds={bounds || undefined}
      center={bounds ? undefined : DEFAULT_CENTER}
      zoom={bounds ? undefined : 13}
      scrollWheelZoom={false}
      className="algo-map"
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {zones.map((zone) => {
        if (!zone.geometry) return null;
        const salesId = ownerOf.get(Number(zone.id));
        const index = salesIds.indexOf(salesId);
        const color = index >= 0 ? comparisonColor(index) : "#999";
        return (
          <GeoJSON
            key={`${report.algorithm}-${zone.id}-${salesId}`}
            data={zone.geometry}
            style={{ color, weight: 1.5, fillColor: color, fillOpacity: index >= 0 ? 0.55 : 0.1 }}
          >
            <Popup>
              <strong>{zone.name}</strong>
              <br />
              Khách hàng: {Number(zone.num_customers) || 0} · Đơn hàng: {Number(zone.num_orders) || 0}
              <br />
              <label className="algo-popup-label">
                Sales phụ trách
                <select
                  value={index >= 0 ? salesId : ""}
                  disabled={disabled}
                  onChange={(e) => onReassign(zone.id, e.target.value === "" ? null : Number(e.target.value))}
                >
                  <option value="">-- Chưa giao --</option>
                  {salesIds.map((sid) => (
                    <option key={sid} value={sid}>
                      {salesName(sid)}
                    </option>
                  ))}
                </select>
              </label>
            </Popup>
          </GeoJSON>
        );
      })}
    </MapContainer>
  );
}

export default function AlgorithmComparison({ territoryId, salesIds, date, zones, salesName, onAdopt }) {
  const [catalog, setCatalog] = useState([]);
  const [catalogError, setCatalogError] = useState("");
  const [selected, setSelected] = useState(DEFAULT_SELECTION);
  const [tolerance, setTolerance] = useState(0.05);
  const [timeLimit, setTimeLimit] = useState(60);
  const [isRunning, setIsRunning] = useState(false);
  const [comparison, setComparison] = useState(null);
  const [adopted, setAdopted] = useState(null);
  // Sửa tay trên từng bản đồ: { [algorithm]: { assignment, metrics, pending, error } }
  const [edits, setEdits] = useState({});
  const requestSeq = useRef({});

  useEffect(() => {
    fetch(`${API_BASE}/admin/algorithms`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data) => {
        setCatalog(data.algorithms || []);
        const available = new Set((data.algorithms || []).filter((a) => a.available).map((a) => a.key));
        setSelected((prev) => prev.filter((key) => available.has(key)));
        if (data.defaults) {
          setTolerance(data.defaults.tolerance);
          setTimeLimit(data.defaults.time_limit);
        }
      })
      .catch((e) => setCatalogError(`Không tải được danh sách thuật toán: ${e.message}`));
  }, []);

  // Kết quả cũ không còn đúng khi đổi phân vùng.
  useEffect(() => {
    setComparison(null);
    setAdopted(null);
    setEdits({});
  }, [territoryId]);

  const bounds = useMemo(() => {
    const features = zones
      .filter((z) => z.geometry)
      .map((z) => ({ type: "Feature", properties: {}, geometry: z.geometry }));
    if (!features.length) return null;
    try {
      const b = L.geoJSON({ type: "FeatureCollection", features }).getBounds();
      return b.isValid() ? b.pad(0.05) : null;
    } catch (e) {
      return null;
    }
  }, [zones]);

  const toggle = (key) =>
    setSelected((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));

  const handleRun = async () => {
    if (!territoryId) return alert("Vui lòng chọn phân vùng trước");
    if (!zones.length) return alert("Phân vùng chưa có zones để chia");
    if (!salesIds.length) return alert("Vui lòng chọn ít nhất 1 Sales");
    if (salesIds.length > zones.length) return alert("Số Sales không được lớn hơn số zones");
    if (!selected.length) return alert("Vui lòng chọn ít nhất 1 thuật toán");
    const order = catalog.map((a) => a.key).filter((key) => selected.includes(key));
    setIsRunning(true);
    setAdopted(null);
    try {
      const res = await fetch(`${API_BASE}/admin/compare-algorithms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          territory_id: territoryId,
          sales_ids: salesIds,
          date,
          algorithms: order,
          tolerance: Number(tolerance),
          time_limit: Number(timeLimit),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg).join("; ")
          : data.detail;
        alert("Lỗi: " + (detail || "Không thể chạy so sánh"));
        return;
      }
      setEdits({});
      setComparison(data);
    } catch (e) {
      alert("Lỗi khi chạy so sánh: " + e.message);
    } finally {
      setIsRunning(false);
    }
  };

  // Kết quả đang hiển thị của một thuật toán (bản đã sửa tay nếu có).
  const view = (report) => {
    const edit = edits[report.algorithm];
    if (!edit) return report;
    return { ...report, assignment: edit.assignment, metrics: edit.metrics || report.metrics, edited: true };
  };

  const handleReassign = async (report, zoneId, salesId) => {
    const algorithm = report.algorithm;
    const current = view(report);
    const assignment = moveZone(current.assignment, zoneId, salesId);
    const seq = (requestSeq.current[algorithm] || 0) + 1;
    requestSeq.current[algorithm] = seq;
    setEdits((prev) => ({
      ...prev,
      [algorithm]: { assignment, metrics: current.metrics, pending: true, error: "" },
    }));
    try {
      const metrics = await evaluateAssignment(territoryId, assignment, comparison.tolerance);
      if (requestSeq.current[algorithm] !== seq) return; // một lần sửa mới hơn đang chạy
      setEdits((prev) =>
        prev[algorithm] ? { ...prev, [algorithm]: { assignment, metrics, pending: false, error: "" } } : prev,
      );
    } catch (e) {
      if (requestSeq.current[algorithm] !== seq) return;
      setEdits((prev) =>
        prev[algorithm]
          ? { ...prev, [algorithm]: { ...prev[algorithm], pending: false, error: e.message } }
          : prev,
      );
    }
  };

  const handleUndo = (report) => {
    requestSeq.current[report.algorithm] = (requestSeq.current[report.algorithm] || 0) + 1;
    setEdits((prev) => {
      const next = { ...prev };
      delete next[report.algorithm];
      return next;
    });
  };

  const results = useMemo(
    () => (comparison?.results || []).map((r) => view(r)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [comparison, edits],
  );
  const okResults = results.filter((r) => r.ok);
  const best = useMemo(() => {
    const out = {};
    METRIC_ROWS.forEach((row) => {
      const values = okResults.map((r) => metricValue(r, row)).filter((v) => v !== null);
      if (values.length > 1 && row.better === "min") out[row.key] = Math.min(...values);
    });
    return out;
  }, [okResults]);

  const handleAdopt = (report) => {
    const unassigned = report.metrics?.unassigned_zones || [];
    if (unassigned.length) {
      alert(`Còn ${unassigned.length} zone chưa giao trong kết quả này. Hãy giao hết trước khi chọn.`);
      return;
    }
    setAdopted(report.algorithm);
    onAdopt({
      ...report,
      label: report.edited ? `${report.label} (đã sửa tay)` : report.label,
      tolerance: comparison.tolerance,
    });
  };

  const responseSalesIds = (comparison?.sales_ids || []).map(Number);

  return (
    <div className="algo-compare">
      <div className="algo-compare-header">
        <h3>So sánh thuật toán chia vùng</h3>
        <span className="hint-text">
          Chạy song song các thuật toán trên cùng phân vùng và danh sách sales đang chọn. Bấm vào một zone trên
          bản đồ kết quả để đổi sales; chỉ số được tính lại ngay, có thể hoàn tác về kết quả ban đầu của thuật toán.
        </span>
      </div>

      {catalogError && <div className="algo-alert algo-alert-bad">{catalogError}</div>}

      <div className="algo-picker">
        {catalog.map((algo) => (
          <label
            key={algo.key}
            className={`algo-option ${algo.available ? "" : "algo-option-disabled"} ${
              selected.includes(algo.key) ? "algo-option-selected" : ""
            }`}
            title={algo.available ? algo.description : algo.reason}
          >
            <input
              type="checkbox"
              disabled={!algo.available}
              checked={selected.includes(algo.key)}
              onChange={() => toggle(algo.key)}
            />
            <span className="algo-option-text">
              <strong>{algo.label}</strong>
              <small>{algo.family}</small>
              <small>{algo.available ? algo.description : algo.reason}</small>
              {!algo.contiguous && <small className="algo-tag">Không bắt buộc liên thông</small>}
            </span>
          </label>
        ))}
      </div>

      <div className="algo-params">
        <label>
          Dung sai cân bằng τ
          <input
            type="number"
            min="0.01"
            max="1"
            step="0.01"
            value={tolerance}
            onChange={(e) => setTolerance(e.target.value)}
          />
        </label>
        <label>
          Giới hạn thời gian mỗi thuật toán (s)
          <input
            type="number"
            min="5"
            max="7200"
            step="5"
            value={timeLimit}
            onChange={(e) => setTimeLimit(e.target.value)}
          />
        </label>
        <span className="hint-text">
          τ và giới hạn thời gian áp dụng cho Prob-VNS, MILP, IQP (tối đa 7200 s như paper). GRASP dùng tham
          số mặc định của app. Phân vùng vài trăm zone cần giới hạn thời gian dài để MILP/IQP có nghiệm.
        </span>
        <button className="btn-primary" onClick={handleRun} disabled={isRunning || !territoryId}>
          {isRunning ? `Đang chạy ${selected.length} thuật toán...` : "Chạy & so sánh"}
        </button>
      </div>

      {comparison && (
        <>
          {(comparison.warnings || []).map((w) => (
            <div key={w} className="algo-alert algo-alert-warn">
              {w}
            </div>
          ))}
          <p className="hint-text">
            {comparison.zone_count} zone · {responseSalesIds.length} sales · τ = {comparison.tolerance} · giới
            hạn {comparison.time_limit} s · seed {comparison.seed}. Giá trị in đậm là tốt nhất trong các kết
            quả có nghiệm; cột có dấu ✎ là kết quả đã sửa tay.
          </p>

          <div className="algo-table-wrap">
            <table className="zone-table algo-table">
              <thead>
                <tr>
                  <th>Chỉ số</th>
                  {results.map((r) => (
                    <th key={r.algorithm}>
                      {r.label}
                      {r.edited ? " ✎" : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Trạng thái</td>
                  {results.map((r) => {
                    const info = statusInfo(r.status);
                    return (
                      <td key={r.algorithm}>
                        <span className={`algo-badge algo-badge-${info.tone}`}>{info.label}</span>
                      </td>
                    );
                  })}
                </tr>
                {METRIC_ROWS.map((row) => (
                  <tr key={row.key}>
                    <td>{row.label}</td>
                    {results.map((r) => {
                      const value = r.ok || row.fromReport ? metricValue(r, row) : null;
                      const isBest = r.ok && value !== null && best[row.key] === value;
                      return (
                        <td key={r.algorithm} className={isBest ? "algo-best" : ""}>
                          {value === null ? "–" : value.toFixed(row.digits)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                <tr>
                  <td>Số zone / sales</td>
                  {results.map((r) => (
                    <td key={r.algorithm}>
                      {r.ok
                        ? responseSalesIds
                            .map((sid) => ((r.assignment || {})[String(sid)] || []).length)
                            .join(" / ")
                        : "–"}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>

          <div className="algo-legend">
            {responseSalesIds.map((sid, index) => (
              <span key={sid} className="algo-legend-item">
                <span className="color-box" style={{ backgroundColor: comparisonColor(index) }} />
                {salesName(sid)}
              </span>
            ))}
          </div>

          <div className="algo-map-grid">
            {results.map((r) => {
              const info = statusInfo(r.status);
              const edit = edits[r.algorithm];
              const unassigned = r.metrics?.unassigned_zones || [];
              return (
                <div
                  key={r.algorithm}
                  className={`algo-card ${adopted === r.algorithm ? "algo-card-adopted" : ""}`}
                >
                  <div className="algo-card-head">
                    <strong>{r.label}</strong>
                    <span className="algo-card-badges">
                      {r.edited && <span className="algo-badge algo-badge-edit">Đã sửa tay</span>}
                      <span className={`algo-badge algo-badge-${info.tone}`}>{info.label}</span>
                    </span>
                  </div>
                  {r.ok ? (
                    <ResultMap
                      report={r}
                      zones={zones}
                      salesIds={responseSalesIds}
                      salesName={salesName}
                      bounds={bounds}
                      onReassign={(zoneId, salesId) => handleReassign(r, zoneId, salesId)}
                    />
                  ) : (
                    <div className="algo-map-empty">{r.message || "Không có nghiệm"}</div>
                  )}
                  <div className="algo-card-foot">
                    {r.ok && (
                      <span>
                        CV {r.metrics.cv_pct.toFixed(1)}% · ĐK {r.metrics.max_diameter_km.toFixed(1)} km ·{" "}
                        {r.metrics.disconnected_territories > 0
                          ? `${r.metrics.disconnected_territories} vùng không liên thông`
                          : "liên thông"}
                        {edit?.pending ? " · đang tính lại..." : ""}
                      </span>
                    )}
                    {unassigned.length > 0 && (
                      <small className="algo-warn-text">{unassigned.length} zone chưa giao</small>
                    )}
                    {edit?.error && <small className="algo-warn-text">Lỗi tính lại: {edit.error}</small>}
                    {r.ok && r.message && !r.edited && <small>{r.message}</small>}
                    {r.ok && (
                      <div className="algo-card-actions">
                        <button className="btn-small" onClick={() => handleAdopt(r)} disabled={edit?.pending}>
                          {adopted === r.algorithm ? "Đang dùng kết quả này" : "Chọn kết quả này"}
                        </button>
                        {r.edited && (
                          <button className="btn-small algo-btn-undo" onClick={() => handleUndo(r)}>
                            Hoàn tác về kết quả ban đầu
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
