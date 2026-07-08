import { useState, useEffect, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  Popup,
  GeoJSON,
  useMapEvents,
  Polyline,
  CircleMarker,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useNavigate } from "react-router-dom";
import "../styles/AdminDashboard.css";
import { API_BASE } from "../api";

function MapEvents({ drawingMode, currentPoints, setCurrentPoints }) {
  useMapEvents({
    click(e) {
      if (drawingMode) {
        const { lat, lng } = e.latlng;
        setCurrentPoints((points) => [...points, [lat, lng]]);
      }
    },
  });
  return null;
}

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("territories");
  const [territories, setTerritories] = useState([]);
  const [allZones, setAllZones] = useState([]);
  const [regions, setRegions] = useState([]);

  const [selectedTerritoryId, setSelectedTerritoryId] = useState(null);
  const [showTerritoryForm, setShowTerritoryForm] = useState(false);
  const [newTerritoryName, setNewTerritoryName] = useState("");
  const [selectedRegionIdForTerritory, setSelectedRegionIdForTerritory] =
    useState(null);
  const [mergeSourceTerritoryIds, setMergeSourceTerritoryIds] = useState([]);
  const [expandedRootTerritoryId, setExpandedRootTerritoryId] = useState(null);

  const [isDrawing, setIsDrawing] = useState(false);
  const [editingZoneId, setEditingZoneId] = useState(null);
  const [tempPoints, setTempPoints] = useState([]);
  const [newZoneName, setNewZoneName] = useState("");

  const [assignDate, setAssignDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [availableSales, setAvailableSales] = useState([]);
  const [selectedSalesIds, setSelectedSalesIds] = useState([]);
  const [assignmentResult, setAssignmentResult] = useState(null); // { salesId: [zoneIds] }
  const [assignmentMetrics, setAssignmentMetrics] = useState(null);
  const [isAssigning, setIsAssigning] = useState(false);
  const [isUpdatingAdjacency, setIsUpdatingAdjacency] = useState(false);
  const [isFakingMetrics, setIsFakingMetrics] = useState(false);
  // --- THÊM MỚI: State cho chức năng tải tự động ---
  const [searchDistrict, setSearchDistrict] = useState("");
  const [isFetching, setIsFetching] = useState(false);

  const [salesList, setSalesList] = useState([]);
  const [pendingSales, setPendingSales] = useState([]);
  const [showSalesForm, setShowSalesForm] = useState(false);
  const [editingSales, setEditingSales] = useState(null); // null = tạo mới, !null = chỉnh sửa
  const [salesFormData, setSalesFormData] = useState({
    username: "",
    email: "",
    password: "",
    full_name: "",
    phone: "",
    region_id: null,
  });

  // Region management state
  const [showRegionForm, setShowRegionForm] = useState(false);
  const [newRegionName, setNewRegionName] = useState("");
  const [selectedRegionId, setSelectedRegionId] = useState(null);
  const [regionDetail, setRegionDetail] = useState(null);
  const [showZoneMetricsForm, setShowZoneMetricsForm] = useState(false);
  const [editingZoneMetrics, setEditingZoneMetrics] = useState(null);
  const [zoneMetricsForm, setZoneMetricsForm] = useState({
    num_customers: 0,
    num_orders: 0,
    revenue: 0,
    notes: "",
  });
  const [showZoneHistory, setShowZoneHistory] = useState(false);
  const [zoneHistoryTarget, setZoneHistoryTarget] = useState(null);
  const [zoneHistory, setZoneHistory] = useState([]);

  useEffect(() => {
    refreshData();
  }, []);

  const fetchAvailableSales = async (date, territoryId = selectedTerritoryId) => {
    try {
      const territoryQuery = territoryId ? `&territory_id=${territoryId}` : "";
      const res = await fetch(
        `${API_BASE}/admin/sales-availability?date=${date}${territoryQuery}`,
      );
      if (res.ok) setAvailableSales(await res.json());
    } catch (e) {
      console.error("Lỗi tải sales:", e);
    }
  };

  useEffect(() => {
    if (activeTab === "territories") fetchAvailableSales(assignDate);
  }, [assignDate, activeTab, selectedTerritoryId]);

  useEffect(() => {
    setSelectedSalesIds([]);
    setAssignmentResult(null);
    setAssignmentMetrics(null);
  }, [selectedTerritoryId]);

  // 2. Hàm chạy thuật toán chia vùng
  const handleRunAlgorithm = async () => {
    if (!selectedTerritoryId)
      return alert("Vui lòng chọn phân vùng trước");
    if (activeZones.length === 0)
      return alert("Phân vùng chưa có zones để chia");
    if (selectedSalesIds.length === 0)
      return alert("Vui lòng chọn ít nhất 1 Sales");
    if (selectedSalesIds.length > activeZones.length)
      return alert("Số Sales không được lớn hơn số zones");
    setIsAssigning(true);
    try {
      const res = await fetch(`${API_BASE}/admin/assign-work`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          territory_id: selectedTerritoryId,
          sales_ids: selectedSalesIds,
          date: assignDate,
          algorithm: "grasp", // Mặc định dùng GRASP tốt nhất
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setAssignmentResult(data.assignment);
        setAssignmentMetrics({
          cv_pct: data.cv_pct,
          total_distance: data.total_distance,
          hoover_index: data.hoover_index,
          algorithm: data.algorithm,
        });
        alert("Đã chia vùng xong! Xem kết quả trên bản đồ phía dưới.");
      }
    } catch (e) {
      alert("Lỗi khi chia vùng");
    } finally {
      setIsAssigning(false);
    }
  };

  // 3. Hàm chỉnh sửa thủ công: Đổi sales cho 1 zone
  const updateZoneAssignment = (zoneId, newSalesId) => {
    const newResult = { ...assignmentResult };
    // Xóa zone khỏi sales cũ
    Object.keys(newResult).forEach((sId) => {
      newResult[sId] = newResult[sId].filter((id) => id !== zoneId);
    });
    // Thêm vào sales mới
    const targetKey = String(newSalesId);
    if (!newResult[targetKey]) newResult[targetKey] = [];
    newResult[targetKey].push(zoneId);
    setAssignmentResult(newResult);
  };

  const handleRebuildAdjacency = async () => {
    if (!selectedTerritoryId)
      return alert("Vui lòng chọn phân vùng trước");
    setIsUpdatingAdjacency(true);
    try {
      const res = await fetch(
        `${API_BASE}/territories/${selectedTerritoryId}/rebuild-adjacency`,
        { method: "POST" },
      );
      const data = await res.json();
      if (!res.ok) {
        alert("Lỗi: " + (data.detail || "Không thể cập nhật ma trận kề"));
        return;
      }
      alert(`Đã cập nhật ma trận kề: ${data.adjacency_count || 0} cặp kề`);
    } catch (e) {
      alert("Lỗi cập nhật ma trận kề");
    } finally {
      setIsUpdatingAdjacency(false);
    }
  };

  const handleFakeZoneMetrics = async () => {
    if (!selectedTerritoryId)
      return alert("Vui lòng chọn phân vùng trước");
    setIsFakingMetrics(true);
    try {
      const res = await fetch(
        `${API_BASE}/territories/${selectedTerritoryId}/fake-zone-metrics`,
        { method: "POST" },
      );
      const data = await res.json();
      if (!res.ok) {
        alert("Lỗi: " + (data.detail || "Không thể fake dữ liệu"));
        return;
      }
      if (res.ok) {
        await refreshData();
        alert(`Đã fake dữ liệu cho ${data.updated_zones || 0} zones`);
      } else {
        alert("Lỗi: " + (data.detail || "Không thể fake dữ liệu"));
      }
    } catch (e) {
      alert("Lỗi fake dữ liệu");
    } finally {
      setIsFakingMetrics(false);
    }
  };

  const handleFinalizeAssignment = async () => {
    if (!assignmentResult) return;
    const assignedZoneIds = Object.values(assignmentResult).flat().map(Number);
    const activeZoneIds = activeZones.map((z) => Number(z.id));
    const hasAllZones =
      assignedZoneIds.length === activeZoneIds.length &&
      activeZoneIds.every((id) => assignedZoneIds.includes(id));
    const hasEmptySales = selectedSalesIds.some(
      (salesId) => !(assignmentResult[String(salesId)] || []).length,
    );
    if (!hasAllZones) return alert("Vui lòng chia tất cả zones trước khi lưu");
    if (hasEmptySales) return alert("Mỗi sales phải có ít nhất 1 zone");

    const res = await fetch(`${API_BASE}/admin/finalize-assignment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        territory_id: selectedTerritoryId,
        date: assignDate,
        data: assignmentResult,
        algorithm: "manual_adjusted",
        cv_pct: assignmentMetrics?.cv_pct,
        total_distance: assignmentMetrics?.total_distance,
        hoover_index: assignmentMetrics?.hoover_index,
      }),
    });
    const data = await res.json();
    if (res.ok) {
      await refreshData();
      await fetchAvailableSales(assignDate, selectedTerritoryId);
      alert("Đã lưu kết quả giao việc thành công!");
    } else {
      alert("Lỗi: " + (data.detail || "Không thể lưu phân công"));
    }
  };

  // 4. Tìm Sales ID của một Zone để tô màu
  const getSalesIdOfZone = (zoneId) => {
    if (!assignmentResult) return null;
    return Object.keys(assignmentResult).find((sId) =>
      assignmentResult[sId].includes(zoneId),
    );
  };

  // Màu sắc cố định cho từng Sales dựa trên ID
  const getSalesColor = (salesId) => {
    const colors = [
      "#FF5733",
      "#33FF57",
      "#3357FF",
      "#F333FF",
      "#FF33A1",
      "#33FFF6",
      "#FF8333",
    ];
    return colors[salesId % colors.length];
  };

  const refreshData = async () => {
    try {
      const [tRes, zRes, sRes, pRes, rRes] = await Promise.all([
        fetch(`${API_BASE}/territories`),
        fetch(`${API_BASE}/zones`),
        fetch(`${API_BASE}/admin/all-sales`),
        fetch(`${API_BASE}/admin/pending-sales`),
        fetch(`${API_BASE}/regions`),
      ]);
      if (tRes.ok) setTerritories(await tRes.json());
      if (zRes.ok) setAllZones(await zRes.json());
      if (sRes.ok) setSalesList(await sRes.json());
      if (pRes.ok) setPendingSales(await pRes.json());
      if (rRes.ok) setRegions(await rRes.json());
    } catch (e) {
      console.error("Lỗi tải dữ liệu:", e);
    }
  };

  // --- THÊM MỚI: Hàm xử lý tải phường tự động ---
  const handleAutoFetch = async () => {
    if (!selectedTerritoryId)
      return alert("Vui lòng chọn một Phân vùng trước!");
    if (!searchDistrict)
      return alert("Vui lòng nhập tên Quận (ví dụ: Quận Cầu Giấy)");

    setIsFetching(true);
    const targetTerritoryId = selectedTerritoryId;
    try {
      const res = await fetch(`${API_BASE}/admin/fetch-wards`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          district_name: searchDistrict,
          territory_id: targetTerritoryId,
        }),
      });

      if (res.ok) {
        alert("Tải dữ liệu các phường thành công!");
        setSearchDistrict("");
        await refreshData();
        setSelectedTerritoryId(targetTerritoryId);
        const selectedTerritory = territories.find(
          (t) => Number(t.id) === Number(targetTerritoryId),
        );
        if (selectedTerritory) {
          setExpandedRootTerritoryId(getRootTerritoryId(selectedTerritory));
        }
      } else {
        const err = await res.json();
        alert(
          "Lỗi: " +
            (err.detail || "Không tìm thấy dữ liệu. Hãy thử: 'Quận Cầu Giấy'"),
        );
      }
    } catch (e) {
      alert("Lỗi kết nối server!");
    } finally {
      setIsFetching(false);
    }
  };

  // --- KHÔI PHỤC: Xử lý xóa phân vùng ---
  const handleDeleteTerritory = async (id) => {
    if (
      !window.confirm(
        "Bạn có chắc chắn muốn xóa phân vùng này và toàn bộ dữ liệu liên quan?",
      )
    )
      return;
    try {
      const res = await fetch(`${API_BASE}/territories/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        if (selectedTerritoryId === id) setSelectedTerritoryId(null);
        refreshData();
      }
    } catch (e) {
      alert("Lỗi khi xóa phân vùng");
    }
  };

  const handleCreateTerritory = async () => {
    if (!newTerritoryName) return;
    if (!selectedRegionIdForTerritory)
      return alert("Vui lòng chọn khu vực cho phân vùng");
    try {
      const res = await fetch(`${API_BASE}/territories`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newTerritoryName,
          region_id: selectedRegionIdForTerritory,
          zone_ids: [],
          source_territory_ids: mergeSourceTerritoryIds,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể tạo phân vùng"));
        return;
      }
      if (res.ok) {
        const createdTerritory = await res.json();
        setNewTerritoryName("");
        setSelectedRegionIdForTerritory(null);
        setMergeSourceTerritoryIds([]);
        setShowTerritoryForm(false);
        setSelectedTerritoryId(createdTerritory.id);
        setExpandedRootTerritoryId(createdTerritory.id);
        await refreshData();
      } else {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể tạo phân vùng"));
      }
    } catch (e) {
      alert("Lỗi tạo phân vùng");
    }
  };

  // Region management functions
  const handleCreateRegion = async () => {
    if (!newRegionName) return alert("Vui lòng nhập tên khu vực");
    try {
      const res = await fetch(`${API_BASE}/regions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newRegionName }),
      });
      if (res.ok) {
        setNewRegionName("");
        setShowRegionForm(false);
        refreshData();
      } else {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể tạo khu vực"));
      }
    } catch (e) {
      alert("Lỗi tạo khu vực");
    }
  };

  const handleDeleteRegion = async (id) => {
    if (!window.confirm("Bạn có chắc chắn muốn xóa khu vực này?")) return;
    try {
      const res = await fetch(`${API_BASE}/regions/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        if (selectedRegionId === id) setSelectedRegionId(null);
        refreshData();
      } else {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể xóa khu vực"));
      }
    } catch (e) {
      alert("Lỗi khi xóa khu vực");
    }
  };

  const handleSelectRegion = async (regionId) => {
    setSelectedRegionId(regionId);
    try {
      const res = await fetch(`${API_BASE}/regions/${regionId}`);
      if (res.ok) {
        setRegionDetail(await res.json());
      }
    } catch (e) {
      console.error("Lỗi tải chi tiết khu vực:", e);
    }
  };

  const handleAssignRegionToSales = async (salesId, regionId) => {
    try {
      const res = await fetch(`${API_BASE}/admin/assign-region-to-sales`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sales_id: salesId, region_id: regionId }),
      });
      if (res.ok) {
        alert("Đã gán khu vực cho sales!");
        await refreshData();
        if (selectedRegionId) {
          handleSelectRegion(selectedRegionId);
        }
      } else {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể gán khu vực"));
      }
    } catch (e) {
      alert("Lỗi gán khu vực");
    }
  };

  // --- SỬA LỖI: Xử lý Vẽ & Liên kết Zone với Territory ---
  const saveDrawnZone = async () => {
    if (tempPoints.length < 3) return alert("Cần ít nhất 3 điểm");
    if (!newZoneName) return alert("Vui lòng nhập tên vùng");

    const coords = [...tempPoints, tempPoints[0]].map((p) => [p[1], p[0]]);
    const geometry = { type: "Polygon", coordinates: [coords] };

    try {
      let res;
      if (editingZoneId) {
        // Cập nhật Zone cũ
        res = await fetch(`${API_BASE}/zones/${editingZoneId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: newZoneName,
            geometry: geometry,
            center_lat: tempPoints[0][0],
            center_lng: tempPoints[0][1],
          }),
        });
      } else {
        // TẠO MỚI Zone
        res = await fetch(`${API_BASE}/zones`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            zone_code: `Z-${Date.now()}`,
            name: newZoneName,
            territory_id: Number(selectedTerritoryId), // Đã có liên kết ở đây
            geometry: geometry,
            center_lat: tempPoints[0][0],
            center_lng: tempPoints[0][1],
            num_customers: 0,
            num_orders: 0,
            revenue: 0,
          }),
        });
      }

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Lỗi từ Server");
      }

      const savedZone = await res.json();
      setAllZones((prev) =>
        editingZoneId
          ? prev.map((z) =>
              Number(z.id) === Number(editingZoneId) ? savedZone : z,
            )
          : [...prev, savedZone],
      );
      alert("Lưu thành công!");
      setIsDrawing(false);
      setTempPoints([]);
      setEditingZoneId(null);
      setNewZoneName("");
      await refreshData(); // Tải lại toàn bộ để cập nhật Map
    } catch (e) {
      console.error("Chi tiết lỗi:", e);
      alert("Lỗi: " + e.message);
    }
  };

  const deleteZone = async (zoneId) => {
    if (!window.confirm("Xóa vùng này?")) return;
    try {
      await fetch(`${API_BASE}/zones/${zoneId}`, { method: "DELETE" });
      refreshData();
    } catch (e) {
      alert("Lỗi khi xóa zone");
    }
  };

  // --- SỬA LỖI: Logic lọc Zones (ép kiểu ID để so khớp chính xác) ---
  const formatDateTime = (value) => {
    if (!value) return "N/A";
    return new Date(value).toLocaleString("vi-VN");
  };

  const handleCreateTerritoryVersion = async (territory) => {
    const rootId = getRootTerritoryId(territory);
    const nextVersion =
      Math.max(
        territory.version_no || 1,
        ...(versionsByRootId.get(rootId) || []).map((t) => t.version_no || 1),
      ) + 1;
    const versionName = window.prompt(
      "Tên version mới:",
      `${territory.name} v${nextVersion}`,
    );
    if (!versionName) return;

    try {
      const res = await fetch(`${API_BASE}/territories/${territory.id}/versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: versionName }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể tạo version mới"));
        return;
      }
      if (res.ok) {
        const newVersion = await res.json();
        setSelectedTerritoryId(newVersion.id);
        setExpandedRootTerritoryId(rootId);
        await refreshData();
      } else {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể tạo version mới"));
      }
    } catch (e) {
      alert("Lỗi tạo version phân vùng");
    }
  };

  const openZoneMetricsForm = (zone) => {
    setEditingZoneMetrics(zone);
    setZoneMetricsForm({
      num_customers: zone.num_customers || 0,
      num_orders: zone.num_orders || 0,
      revenue: zone.revenue || 0,
      notes: "",
    });
    setShowZoneMetricsForm(true);
  };

  const saveZoneMetrics = async () => {
    if (!editingZoneMetrics) return;
    try {
      const res = await fetch(`${API_BASE}/zones/${editingZoneMetrics.id}/metrics`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          num_customers: Number(zoneMetricsForm.num_customers) || 0,
          num_orders: Number(zoneMetricsForm.num_orders) || 0,
          revenue: Number(zoneMetricsForm.revenue) || 0,
          notes: zoneMetricsForm.notes,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể cập nhật thông tin zone"));
        return;
      }
      if (res.ok) {
        const updatedZone = await res.json();
        setAllZones((prev) =>
          prev.map((z) => (Number(z.id) === Number(updatedZone.id) ? updatedZone : z)),
        );
        setShowZoneMetricsForm(false);
        setEditingZoneMetrics(null);
        await refreshData();
      } else {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể cập nhật thông tin zone"));
      }
    } catch (e) {
      alert("Lỗi cập nhật thông tin zone");
    }
  };

  const openZoneHistory = async (zone) => {
    setZoneHistoryTarget(zone);
    setShowZoneHistory(true);
    setZoneHistory([]);
    try {
      const res = await fetch(`${API_BASE}/zones/${zone.id}/activities`);
      if (res.ok) {
        const data = await res.json();
        setZoneHistory(Array.isArray(data) ? data : [data]);
      }
    } catch (e) {
      alert("Lỗi tải lịch sử bán hàng");
    }
  };

  const activeZones = useMemo(() => {
    if (!selectedTerritoryId) return [];
    return allZones.filter(
      (z) => Number(z.territory_id) === Number(selectedTerritoryId),
    );
  }, [selectedTerritoryId, allZones]);

  const selectedTerritory = useMemo(
    () =>
      territories.find((t) => Number(t.id) === Number(selectedTerritoryId)) ||
      null,
    [territories, selectedTerritoryId],
  );

  const assignableSales = useMemo(() => {
    if (!selectedTerritory) return [];
    return availableSales.filter(
      (s) =>
        !s.is_busy &&
        Number(s.region_id) === Number(selectedTerritory.region_id),
    );
  }, [availableSales, selectedTerritory]);

  useEffect(() => {
    const assignableIds = new Set(assignableSales.map((s) => Number(s.id)));
    setSelectedSalesIds((prev) =>
      prev.filter((salesId) => assignableIds.has(Number(salesId))),
    );
  }, [assignableSales]);

  const salesWorkloadRanking = useMemo(() => {
    if (!assignmentResult) return [];
    const zoneById = new Map(activeZones.map((zone) => [Number(zone.id), zone]));
    const salesById = new Map(
      [...availableSales, ...salesList].map((sales) => [
        Number(sales.id),
        sales,
      ]),
    );

    return Object.entries(assignmentResult)
      .map(([salesId, zoneIds]) => {
        const zones = (zoneIds || [])
          .map((zoneId) => zoneById.get(Number(zoneId)))
          .filter(Boolean);
        const totalCustomers = zones.reduce(
          (sum, zone) => sum + (Number(zone.num_customers) || 0),
          0,
        );
        const totalOrders = zones.reduce(
          (sum, zone) => sum + (Number(zone.num_orders) || 0),
          0,
        );
        const totalRevenue = zones.reduce(
          (sum, zone) => sum + (Number(zone.revenue) || 0),
          0,
        );
        const workload = totalCustomers + totalOrders * 0.2;
        const sales = salesById.get(Number(salesId));

        return {
          salesId,
          salesName: sales?.full_name || sales?.username || `Sales ${salesId}`,
          zoneCount: zones.length,
          totalCustomers,
          totalOrders,
          totalRevenue,
          workload,
        };
      })
      .sort((a, b) => b.workload - a.workload);
  }, [assignmentResult, activeZones, availableSales, salesList]);

  const rootTerritories = useMemo(
    () => territories.filter((t) => !t.parent_territory_id),
    [territories],
  );

  const versionsByRootId = useMemo(() => {
    const grouped = new Map();
    territories.forEach((t) => {
      if (!t.parent_territory_id) return;
      const rootId = Number(t.parent_territory_id);
      if (!grouped.has(rootId)) grouped.set(rootId, []);
      grouped.get(rootId).push(t);
    });
    grouped.forEach((items) =>
      items.sort(
        (a, b) =>
          (a.version_no || 1) - (b.version_no || 1) ||
          new Date(a.created_at) - new Date(b.created_at),
      ),
    );
    return grouped;
  }, [territories]);

  const getRootTerritoryId = (territory) =>
    Number(territory.parent_territory_id || territory.id);

  const mergeCandidateTerritories = useMemo(() => {
    return rootTerritories.flatMap((root) => [
      root,
      ...(versionsByRootId.get(Number(root.id)) || []),
    ]);
  }, [rootTerritories, versionsByRootId]);

  const regionNameById = useMemo(
    () => new Map(regions.map((r) => [Number(r.id), r.name])),
    [regions],
  );

  const getSalesRegionName = (regionId) => {
    if (!regionId) return "Chua gan";
    return regionNameById.get(Number(regionId)) || "Khong tim thay";
  };

  const getZoneColor = (index) => {
    const colors = [
      "#e74c3c",
      "#3498db",
      "#2ecc71",
      "#f1c40f",
      "#9b59b6",
      "#1abc9c",
      "#e67e22",
    ];
    return colors[index % colors.length];
  };

  const handleSalesAction = async (action, id, data = null) => {
    try {
      let res;
      switch (action) {
        case "approve":
          res = await fetch(`${API_BASE}/admin/approve-user/${id}`, {
            method: "POST",
          });
          break;
        case "reject":
        case "delete":
          if (!window.confirm("Bạn có chắc chắn muốn thực hiện thao tác này?"))
            return;
          res = await fetch(`${API_BASE}/users/${id}`, { method: "DELETE" });
          break;
        case "create":
          res = await fetch(`${API_BASE}/admin/create-sales`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          });
          break;
        case "update":
          res = await fetch(`${API_BASE}/admin/sales/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: data.email,
              full_name: data.full_name,
              phone: data.phone,
              region_id: data.region_id,
            }),
          });
          break;
        default:
          break;
      }

      if (res && res.ok) {
        alert("Thao tác thành công!");
        setShowSalesForm(false);
        setEditingSales(null);
        setSalesFormData({
          username: "",
          email: "",
          password: "",
          full_name: "",
          phone: "",
          region_id: null,
        });
        refreshData();
      } else {
        const err = await res.json();
        alert("Lỗi: " + (err.detail || "Không thể thực hiện"));
      }
    } catch (e) {
      alert("Lỗi kết nối server!");
    }
  };
  return (
    <div className="admin-container">
      <aside className="admin-sidebar">
        <div className="logo">Territory System</div>
        <nav className="main-nav">
          <button
            className={activeTab === "territories" ? "active" : ""}
            onClick={() => setActiveTab("territories")}
          >
            Quản lý Phân vùng
          </button>
          <button
            className={activeTab === "regions" ? "active" : ""}
            onClick={() => setActiveTab("regions")}
          >
            Quản lý Khu vực
          </button>
          <button
            className={activeTab === "sales" ? "active" : ""}
            onClick={() => setActiveTab("sales")}
          >
            Sales
          </button>
        </nav>
        <button className="logout-btn" onClick={() => navigate("/")}>
          Đăng xuất
        </button>
      </aside>

      <main className="admin-main">
        {/* --- TAB 1: QUẢN LÝ PHÂN VÙNG --- */}
        {activeTab === "territories" && (
          <div className="tab-content">
            <div className="zone-mgr-header">
              <h2>Thiết kế Phân vùng</h2>
              <button
                className="btn-primary"
                onClick={() => {
                  setMergeSourceTerritoryIds([]);
                  setShowTerritoryForm(true);
                }}
              >
              Tạo Phân vùng mới
              </button>
            </div>

            <div className="zone-mgr-layout">
              <div className="district-list">
                {/* Công cụ tải phường tự động */}
                <div
                  className="auto-fetch-container"
                  style={{
                    padding: "15px",
                    marginBottom: "20px",
                    backgroundColor: "#f8f9fa",
                    borderRadius: "8px",
                    border: "1px solid #ddd",
                  }}
                >
                  <h5
                    style={{
                      marginBottom: "10px",
                      fontSize: "14px",
                      color: "#2c3e50",
                    }}
                  >
                    Tải Phường tự động
                  </h5>
                  <input
                    type="text"
                    placeholder="Tên Quận (vd: Quận Cầu Giấy)"
                    value={searchDistrict}
                    onChange={(e) => setSearchDistrict(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      marginBottom: "10px",
                      border: "1px solid #ccc",
                      borderRadius: "4px",
                      fontSize: "13px",
                    }}
                  />
                  <button
                    onClick={handleAutoFetch}
                    disabled={isFetching || !selectedTerritoryId}
                    className="btn-fetch-auto"
                    style={{
                      width: "100%",
                      padding: "10px",
                      backgroundColor: isFetching ? "#ccc" : "#2ecc71",
                      color: "white",
                      border: "none",
                      borderRadius: "4px",
                      cursor: isFetching ? "not-allowed" : "pointer",
                      fontWeight: "bold",
                    }}
                  >
                    {isFetching
                      ? "Đang tải dữ liệu..."
                      : "Tải toàn bộ Phường"}
                  </button>
                  {!selectedTerritoryId && (
                    <p
                      style={{
                        fontSize: "11px",
                        color: "#e74c3c",
                        marginTop: "5px",
                        fontWeight: "500",
                      }}
                    >
                      * Hãy chọn 1 phân vùng để tải vào
                    </p>
                  )}
                </div>

                <h4>Phân vùng mục tiêu</h4>
                <div className="territory-scroll-list">
                  {rootTerritories.map((t) => {
                    const rootVersions = versionsByRootId.get(Number(t.id)) || [];
                    const rootExpanded =
                      Number(expandedRootTerritoryId) === Number(t.id);
                    return (
                  <div className="territory-tree-item" key={t.id}>
                  <div
                    className={`dist-item-card ${selectedTerritoryId === t.id ? "selected-active" : ""}`}
                    onClick={() => {
                      setSelectedTerritoryId(t.id);
                      setExpandedRootTerritoryId(t.id);
                    }}
                  >
                    <div className="dist-info">
                      <span className="name">
                        {t.name}
                        <small className="territory-meta">
                          v{t.version_no || 1} - {formatDateTime(t.created_at)}
                        </small>
                      </span>
                    </div>
                    <div className="dist-actions">
                      <span className="count">{t.zone_ids?.length || 0}</span>
                      <button
                        className="btn-small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCreateTerritoryVersion(t);
                        }}
                      >
                        Version
                      </button>
                      <button
                        className="btn-icon-del"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteTerritory(t.id);
                        }}
                      >
                        X
                      </button>
                    </div>
                  </div>
                  {rootExpanded && rootVersions.length > 0 && (
                    <div className="territory-children">
                      {rootVersions.map((version) => (
                        <div
                          key={version.id}
                          className={`dist-item-card version-child ${selectedTerritoryId === version.id ? "selected-active" : ""}`}
                          onClick={() => {
                            setSelectedTerritoryId(version.id);
                            setExpandedRootTerritoryId(t.id);
                          }}
                        >
                          <div className="dist-info">
                            <span className="name">
                              {version.name}
                              <small className="territory-meta">
                                v{version.version_no || 1} - {formatDateTime(version.created_at)}
                              </small>
                            </span>
                          </div>
                          <div className="dist-actions">
                            <span className="count">
                              {version.zone_ids?.length || 0}
                            </span>
                            <button
                              className="btn-icon-del"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteTerritory(version.id);
                              }}
                            >
                              X
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  </div>
                  );
                  })}
                </div>
              </div>

              <div className="zone-display">
                <div className="map-toolbar">
                  {isDrawing ? (
                    <div className="drawing-controls">
                      <input
                        type="text"
                        placeholder="Tên vùng..."
                        value={newZoneName}
                        onChange={(e) => setNewZoneName(e.target.value)}
                      />
                      <button className="btn-success" onClick={saveDrawnZone}>
                        Lưu
                      </button>
                      <button
                        className="btn-draw"
                        onClick={() =>
                          setTempPoints((prev) => prev.slice(0, -1))
                        }
                      >
                        Hoàn tác
                      </button>
                      <button
                        className="btn-reject"
                        onClick={() => {
                          setIsDrawing(false);
                          setTempPoints([]);
                          setEditingZoneId(null);
                          setNewZoneName("");
                        }}
                      >
                        Hủy
                      </button>
                    </div>
                  ) : (
                    <div className="toolbar-info">
                      {selectedTerritoryId ? (
                        <button
                          className="btn-draw"
                          onClick={() => {
                            setIsDrawing(true);
                            setEditingZoneId(null);
                            setTempPoints([]);
                            setNewZoneName("");
                          }}
                        >
                          Vẽ vùng mới cho "
                          {
                            territories.find(
                              (t) => t.id === selectedTerritoryId,
                            )?.name
                          }
                          "
                        </button>
                      ) : (
                        <span className="hint-text">
                          Chọn một phân vùng để quản lý Zones
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="map-box">
                  <MapContainer
                    center={[21.0285, 105.8542]}
                    zoom={13}
                    style={{ height: "450px", width: "100%" }}
                  >
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    <MapEvents
                      drawingMode={isDrawing}
                      currentPoints={tempPoints}
                      setCurrentPoints={setTempPoints}
                    />
                    {isDrawing && tempPoints.length > 0 && (
                      <>
                        <Polyline
                          positions={tempPoints}
                          pathOptions={{ color: "blue", dashArray: "5, 5" }}
                        />
                        {tempPoints.map((point, idx) => (
                          <CircleMarker
                            key={idx}
                            center={point}
                            radius={4}
                            pathOptions={{ color: "red" }}
                          />
                        ))}
                      </>
                    )}
                    {activeZones.map((z, idx) => {
                      const isRedrawingZone =
                        Number(z.id) === Number(editingZoneId);

                      return (
                        <GeoJSON
                          key={`zone-${z.id}-${idx}-${isDrawing ? "drawing" : "view"}-${isRedrawingZone ? "editing" : "idle"}`}
                          data={z.geometry}
                          interactive={!isDrawing}
                          style={{
                            color: getZoneColor(idx),
                            weight: isRedrawingZone ? 3 : 2,
                            fillOpacity: isRedrawingZone ? 0 : 0.3,
                            dashArray: isRedrawingZone ? "8, 6" : null,
                          }}
                        >
                          {!isDrawing && (
                            <Popup>
                              <strong>{z.name}</strong>
                            </Popup>
                          )}
                        </GeoJSON>
                      );
                    })}
                  </MapContainer>
                </div>

                <div className="zone-details-list">
                  <h3>Zones hiển thị: {activeZones.length} vùng</h3>
                  {activeZones.length > 0 ? (
                    <div className="zone-table-container territory-zone-scroll">
                      <table className="zone-table">
                        <thead>
                          <tr>
                            <th>Màu</th>
                            <th>Tên Zone</th>
                            <th>Khách hàng</th>
                            <th>Đơn hàng</th>
                            <th>Doanh thu</th>
                            <th>Hành động</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activeZones.map((z, idx) => (
                            <tr key={z.id}>
                              <td>
                                <div
                                  className="color-box"
                                  style={{ backgroundColor: getZoneColor(idx) }}
                                ></div>
                              </td>
                              <td>{z.name}</td>
                              <td>{(z.num_customers || 0).toLocaleString()}</td>
                              <td>{(z.num_orders || 0).toLocaleString()}</td>
                              <td>{(z.revenue || 0).toLocaleString()} đ</td>
                              <td>
                                <button
                                  className="btn-small"
                                  onClick={() => {
                                    setEditingZoneId(z.id);
                                    setNewZoneName(z.name);
                                    setIsDrawing(true);
                                    setTempPoints([]);
                                  }}
                                >
                                  Vẽ lại
                                </button>
                                <button
                                  className="btn-small"
                                  onClick={() => openZoneMetricsForm(z)}
                                >
                                  Sửa thông tin
                                </button>
                                <button
                                  className="btn-small"
                                  onClick={() => openZoneHistory(z)}
                                >
                                  Lịch sử
                                </button>
                                <button
                                  className="btn-small-del"
                                  onClick={() => deleteZone(z.id)}
                                >
                                  X
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="empty-msg">Chưa có vùng nào được liên kết.</p>
                  )}
                </div>
              </div>
            </div>
            <div
              className="assignment-section"
              style={{
                marginTop: "30px",
                borderTop: "2px solid #eee",
                paddingTop: "20px",
              }}
            >
              <div className="section-header">
                <h3>Chia vùng & Giao việc cho Sales</h3>
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  <button
                    className="btn-small"
                    onClick={handleRebuildAdjacency}
                    disabled={isUpdatingAdjacency || !selectedTerritoryId}
                  >
                    {isUpdatingAdjacency
                      ? "Đang cập nhật..."
                      : "Cập nhật ma trận kề"}
                  </button>
                  <button
                    className="btn-small"
                    onClick={handleFakeZoneMetrics}
                    disabled={isFakingMetrics || !selectedTerritoryId}
                  >
                    {isFakingMetrics ? "Đang fake..." : "Fake dữ liệu"}
                  </button>
                </div>
              </div>

              <div
                className="assignment-controls"
                style={{ display: "flex", gap: "20px", marginBottom: "20px" }}
              >
                <div className="control-item">
                  <label>Ngày làm việc:</label>
                  <input
                    type="date"
                    value={assignDate}
                    onChange={(e) => setAssignDate(e.target.value)}
                  />
                </div>

                <div className="control-item" style={{ flex: 1 }}>
                  <label>Chọn Sales (Ưu tiên sales rảnh):</label>
                  <div
                    className="sales-selector-grid"
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr 1fr",
                      gap: "10px",
                      maxHeight: "150px",
                      overflowY: "auto",
                      border: "1px solid #ddd",
                      padding: "10px",
                    }}
                  >
                    {assignableSales.length === 0 && (
                      <span className="hint-text">
                        Không có sales rảnh cùng khu vực với phân vùng này.
                      </span>
                    )}
                    {assignableSales.map((s) => (
                      <label
                        key={s.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "5px",
                          color: s.is_busy ? "#ccc" : "#000",
                        }}
                      >
                        <input
                          type="checkbox"
                          disabled={s.is_busy}
                          checked={selectedSalesIds.includes(s.id)}
                          onChange={(e) => {
                            if (e.target.checked)
                              setSelectedSalesIds([...selectedSalesIds, s.id]);
                            else
                              setSelectedSalesIds(
                                selectedSalesIds.filter((id) => id !== s.id),
                              );
                          }}
                        />
                        {s.full_name} {s.is_busy ? "(Bận)" : "(Rảnh)"}
                      </label>
                    ))}
                  </div>
                </div>

                <button
                  className="btn-primary"
                  onClick={handleRunAlgorithm}
                  disabled={isAssigning || !selectedTerritoryId}
                >
                  {isAssigning
                    ? "Đang tính toán..."
                    : "Chia vùng Tự động"}
                </button>
              </div>

              {assignmentResult && (
                <div
                  className="assignment-results-layout"
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "20px",
                  }}
                >
                  {/* Bản đồ kết quả chia vùng */}
                  <div className="result-map">
                    <h4>Bản đồ phân bổ (Tô màu theo Sales)</h4>
                    <MapContainer
                      center={[21.0285, 105.8542]}
                      zoom={13}
                      style={{ height: "400px", borderRadius: "8px" }}
                    >
                      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                      {activeZones.map((z) => {
                        const sId = getSalesIdOfZone(z.id);
                        return (
                          <GeoJSON
                            key={`assign-map-${z.id}-${sId}`}
                            data={z.geometry}
                            style={{
                              color: sId ? getSalesColor(sId) : "#999",
                              fillOpacity: sId ? 0.6 : 0.1,
                              weight: 2,
                            }}
                          >
                            <Popup>
                              <strong>{z.name}</strong>
                              <br />
                              Phụ trách:{" "}
                              {sId
                                ? availableSales.find((s) => Number(s.id) === Number(sId))
                                    ?.full_name
                                : "Chưa giao"}
                              <br />
                              <select
                                value={sId || ""}
                                onChange={(e) =>
                                  updateZoneAssignment(
                                    z.id,
                                    parseInt(e.target.value),
                                  )
                                }
                                style={{ marginTop: "8px", width: "100%" }}
                              >
                                <option value="">-- Chọn Sales --</option>
                                {selectedSalesIds.map((salesId) => {
                                  const sales = assignableSales.find(
                                    (item) => Number(item.id) === Number(salesId),
                                  );
                                  return (
                                    <option key={salesId} value={salesId}>
                                      {sales?.full_name || sales?.username}
                                    </option>
                                  );
                                })}
                              </select>
                            </Popup>
                          </GeoJSON>
                        );
                      })}
                    </MapContainer>
                  </div>

                  {/* Bảng chỉnh sửa thủ công */}
                  <div className="result-table">
                    <h4>Danh sách phân bổ & Chỉnh sửa</h4>
                    <div style={{ maxHeight: "220px", overflowY: "auto", marginBottom: "16px" }}>
                      <table className="zone-table">
                        <thead>
                          <tr>
                            <th>Sales</th>
                            <th>Zones</th>
                            <th>Khách hàng</th>
                            <th>Đơn hàng</th>
                            <th>Doanh thu</th>
                            <th>Workload</th>
                          </tr>
                        </thead>
                        <tbody>
                          {salesWorkloadRanking.map((item) => (
                            <tr key={`sales-workload-${item.salesId}`}>
                              <td>
                                <span
                                  className="color-box"
                                  style={{
                                    backgroundColor: getSalesColor(item.salesId),
                                    display: "inline-block",
                                    marginRight: "6px",
                                  }}
                                ></span>
                                {item.salesName}
                              </td>
                              <td>{item.zoneCount}</td>
                              <td>{item.totalCustomers.toLocaleString()}</td>
                              <td>{item.totalOrders.toLocaleString()}</td>
                              <td>{item.totalRevenue.toLocaleString()} đ</td>
                              <td>{item.workload.toFixed(1)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div style={{ maxHeight: "400px", overflowY: "auto" }}>
                      <table className="zone-table">
                        <thead>
                          <tr>
                            <th>Tên Zone</th>
                            <th>Sales phụ trách</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activeZones.map((z) => (
                            <tr key={`edit-assign-${z.id}`}>
                              <td>{z.name}</td>
                              <td>
                                <select
                                  value={getSalesIdOfZone(z.id) || ""}
                                  onChange={(e) =>
                                    updateZoneAssignment(
                                      z.id,
                                      parseInt(e.target.value),
                                    )
                                  }
                                  style={{
                                    borderLeft: `5px solid ${getSalesColor(getSalesIdOfZone(z.id))}`,
                                  }}
                                >
                                  <option value="">-- Chọn Sales --</option>
                                  {selectedSalesIds.map((sId) => (
                                    <option key={sId} value={sId}>
                                      {
                                        availableSales.find((s) => s.id === sId)
                                          ?.full_name
                                      }
                                    </option>
                                  ))}
                                </select>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <button
                      className="btn-success"
                      style={{ width: "100%", marginTop: "15px" }}
                      onClick={async () => {
                        if (handleFinalizeAssignment) {
                          await handleFinalizeAssignment();
                          return;
                        }
                        const res = await fetch(
                          `${API_BASE}/admin/finalize-assignment`,
                          {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                              territory_id: selectedTerritoryId,
                              date: assignDate,
                              data: assignmentResult,
                              algorithm: "manual_adjusted",
                            }),
                          },
                        );
                        if (res.ok)
            alert("Đã lưu kết quả giao việc thành công!");
                      }}
                    >
                    Lưu kết quả cuối cùng
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* --- TAB 2: QUẢN LÝ KHU VỰC --- */}
        {activeTab === "regions" && (
          <div className="tab-content">
            <div className="zone-mgr-header">
              <h2>Quản lý Khu vực</h2>
              <button
                className="btn-primary"
                onClick={() => setShowRegionForm(true)}
              >
              Tạo khu vực mới
              </button>
            </div>

            <div className="zone-mgr-layout">
              <div className="district-list">
                <h4>Danh sách khu vực</h4>
                {regions.length > 0 ? (
                  regions.map((r) => (
                    <div
                      key={r.id}
                      className={`dist-item-card ${selectedRegionId === r.id ? "selected-active" : ""}`}
                      onClick={() => handleSelectRegion(r.id)}
                    >
                      <div className="dist-info">
                        <span className="name">{r.name}</span>
                      </div>
                      <div className="dist-actions">
                        <button
                          className="btn-icon-del"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteRegion(r.id);
                          }}
                        >
                        X
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="empty-msg">Chưa có khu vực nào</p>
                )}
              </div>

              <div className="zone-display">
                {selectedRegionId && regionDetail ? (
                  <div className="region-detail-panel">
                    <div className="detail-header">
                    <h3>{regionDetail.name}</h3>
                      <div className="stats-row">
                        <div className="stat-item">
                          <span className="stat-label">Phân vùng:</span>
                          <span className="stat-value">
                            {regionDetail.territories?.length || 0}
                          </span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Sales:</span>
                          <span className="stat-value">
                            {regionDetail.sales_users?.length || 0}
                          </span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Zones:</span>
                          <span className="stat-value">
                            {regionDetail.total_zones || 0}
                          </span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Khách hàng:</span>
                          <span className="stat-value">
                            {regionDetail.total_customers || 0}
                          </span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Doanh thu:</span>
                          <span className="stat-value">
                            {(regionDetail.total_revenue || 0).toLocaleString()}{" "}
                            đ
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="tabs-detail">
                      <div className="detail-tab">
                        <h4>Phân vùng trong khu vực</h4>
                        {regionDetail.territories &&
                        regionDetail.territories.length > 0 ? (
                          <div className="zone-table-container">
                            <table className="zone-table">
                              <thead>
                                <tr>
                                  <th>Tên phân vùng</th>
                                  <th>Số zones</th>
                                </tr>
                              </thead>
                              <tbody>
                                {regionDetail.territories.map((t) => (
                                  <tr key={t.id}>
                                    <td>{t.name}</td>
                                    <td>{t.zone_ids?.length || 0}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <p className="empty-msg">Chưa có phân vùng nào</p>
                        )}
                      </div>

                      <div className="detail-tab">
                        <h4>Sales phụ trách khu vực</h4>
                        {regionDetail.sales_users &&
                        regionDetail.sales_users.length > 0 ? (
                          <div className="sales-grid">
                            {regionDetail.sales_users.map((s) => (
                              <div key={s.id} className="sales-card">
                                <div className="sales-info">
                                  <strong>{s.full_name || s.username}</strong>
                              <span>{s.email}</span>
                              <span>{s.phone || "N/A"}</span>
                                </div>
                                <button
                                  className="btn-small-del"
                                  onClick={() =>
                                    handleAssignRegionToSales(s.id, null)
                                  }
                                  title="Gỡ khu vực"
                                >
                                      Gỡ
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="empty-msg">Chưa có sales nào</p>
                        )}
                      </div>

                      <div className="detail-tab">
                        <h4>Gán thêm Sales cho khu vực</h4>
                        <div className="sales-selector">
                          <div
                            style={{
                              maxHeight: "200px",
                              overflowY: "auto",
                              border: "1px solid #ddd",
                              padding: "10px",
                              borderRadius: "4px",
                            }}
                          >
                            {salesList
                              .filter((s) => s.region_id !== selectedRegionId)
                              .map((s) => (
                                <div
                                  key={s.id}
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "center",
                                    padding: "8px",
                                    borderBottom: "1px solid #eee",
                                  }}
                                >
                                  <span>{s.full_name || s.username}</span>
                                  <button
                                    className="btn-small"
                                    onClick={() =>
                                      handleAssignRegionToSales(
                                        s.id,
                                        selectedRegionId,
                                      )
                                    }
                                  >
                                    Gán
                                  </button>
                                </div>
                              ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="empty-detail">
                    <p>Chọn một khu vực để xem chi tiết</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* --- TAB 3: QUẢN LÝ SALES --- */}
        {activeTab === "sales" && (
          <div className="tab-content">
            <div className="zone-mgr-header">
              <h2>Quản lý Đội ngũ Sales</h2>
              <button
                className="btn-primary"
                onClick={() => {
                  setEditingSales(null);
                  setSalesFormData({
                    username: "",
                    email: "",
                    password: "",
                    full_name: "",
                    phone: "",
                    region_id: null,
                  });
                  setShowSalesForm(true);
                }}
              >
                Thêm Sales mới
              </button>
            </div>

            {pendingSales.length > 0 && (
              <div className="sales-section pending-section">
                <h3 className="section-title">
                  Yêu cầu đăng ký đang chờ ({pendingSales.length})
                </h3>
                <div className="sales-grid">
                  {pendingSales.map((s) => (
                    <div key={s.id} className="sales-card pending">
                      <div className="sales-info">
                        <strong>{s.full_name || s.username}</strong>
                        <span>{s.email}</span>
                        <span>{s.phone || "N/A"}</span>
                      </div>
                      <div className="sales-btns">
                        <button
                          className="btn-approve"
                          onClick={() => handleSalesAction("approve", s.id)}
                        >
                          Duyệt
                        </button>
                        <button
                          className="btn-reject"
                          onClick={() => handleSalesAction("reject", s.id)}
                        >
                          Từ chối
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="sales-section">
              <h3 className="section-title">
                Danh sách Sales chính thức ({salesList.length})
              </h3>
              <div className="zone-table-container">
                <table className="zone-table">
                  <thead>
                    <tr>
                      <th>Username</th>
                      <th>Họ tên</th>
                      <th>Email</th>
                      <th>Khu vuc</th>
                      <th>Điện thoại</th>
                      <th>Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {salesList.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <strong>{s.username}</strong>
                        </td>
                        <td>{s.full_name}</td>
                        <td>{s.email}</td>
                        <td>{getSalesRegionName(s.region_id)}</td>
                        <td>{s.phone}</td>
                        <td>
                          <button
                            className="btn-small"
                            onClick={() => {
                              setEditingSales(s);
                              setSalesFormData({
                                username: s.username,
                                email: s.email,
                                password: "********",
                                full_name: s.full_name,
                                phone: s.phone,
                                region_id: s.region_id,
                              });
                              setShowSalesForm(true);
                            }}
                          >
                            Sửa
                          </button>
                          <button
                            className="btn-small-del"
                            onClick={() => handleSalesAction("delete", s.id)}
                          >
                            X
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* MODALS PHẢI NẰM NGOÀI MAIN CONTENT ĐỂ KHÔNG BỊ ẢNH HƯỞNG BỞI CSS LAYOUT */}
      {showZoneMetricsForm && editingZoneMetrics && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Sửa thông tin Zone</h3>
            <div className="form-group">
              <label>Zone</label>
              <input type="text" value={editingZoneMetrics.name} disabled />
            </div>
            <div className="form-group">
              <label>Số khách hàng</label>
              <input
                type="number"
                min="0"
                value={zoneMetricsForm.num_customers}
                onChange={(e) =>
                  setZoneMetricsForm({
                    ...zoneMetricsForm,
                    num_customers: e.target.value,
                  })
                }
              />
            </div>
            <div className="form-group">
              <label>Số đơn hàng</label>
              <input
                type="number"
                min="0"
                value={zoneMetricsForm.num_orders}
                onChange={(e) =>
                  setZoneMetricsForm({
                    ...zoneMetricsForm,
                    num_orders: e.target.value,
                  })
                }
              />
            </div>
            <div className="form-group">
              <label>Doanh thu</label>
              <input
                type="number"
                min="0"
                value={zoneMetricsForm.revenue}
                onChange={(e) =>
                  setZoneMetricsForm({
                    ...zoneMetricsForm,
                    revenue: e.target.value,
                  })
                }
              />
            </div>
            <div className="form-group">
              <label>Ghi chú</label>
              <input
                type="text"
                value={zoneMetricsForm.notes}
                onChange={(e) =>
                  setZoneMetricsForm({
                    ...zoneMetricsForm,
                    notes: e.target.value,
                  })
                }
              />
            </div>
            <div className="modal-btns">
              <button onClick={saveZoneMetrics} className="btn-success">
                Lưu
              </button>
              <button
                onClick={() => {
                  setShowZoneMetricsForm(false);
                  setEditingZoneMetrics(null);
                }}
              >
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}

      {showZoneHistory && (
        <div className="modal-overlay">
          <div className="modal-content zone-history-modal">
            <h3>Lịch sử bán hàng - {zoneHistoryTarget?.name}</h3>
            {zoneHistory.length > 0 ? (
              <div className="zone-table-container">
                <table className="zone-table">
                  <thead>
                    <tr>
                      <th>Ngày cập nhật</th>
                      <th>Khách hàng</th>
                      <th>Đơn hàng</th>
                      <th>Doanh thu</th>
                      <th>AOV</th>
                    </tr>
                  </thead>
                  <tbody>
                    {zoneHistory.map((item) => (
                      <tr key={item.id}>
                        <td>{formatDateTime(item.updated_at)}</td>
                        <td>{(item.num_customers || 0).toLocaleString()}</td>
                        <td>{(item.num_orders || 0).toLocaleString()}</td>
                        <td>{(item.total_revenue || 0).toLocaleString()} đ</td>
                        <td>{(item.avg_order_value || 0).toLocaleString()} đ</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-msg">Chưa có lịch sử bán hàng.</p>
            )}
            <div className="modal-btns">
              <button onClick={() => setShowZoneHistory(false)}>Đóng</button>
            </div>
          </div>
        </div>
      )}

      {showTerritoryForm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Tạo Phân vùng</h3>
            <div className="form-group" style={{ marginBottom: "15px" }}>
              <label>Tên phân vùng:</label>
              <input
                type="text"
                placeholder="Tên phân vùng..."
                value={newTerritoryName}
                onChange={(e) => setNewTerritoryName(e.target.value)}
              />
            </div>
            <div className="form-group" style={{ marginBottom: "15px" }}>
              <label>Chọn khu vực:</label>
              <select
                value={selectedRegionIdForTerritory || ""}
                onChange={(e) =>
                  setSelectedRegionIdForTerritory(
                    e.target.value ? parseInt(e.target.value) : null,
                  )
                }
              >
                <option value="">-- Chọn khu vực --</option>
                {regions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group" style={{ marginBottom: "15px" }}>
              <label>Gộp từ phân vùng đã có:</label>
              <div className="merge-territory-list">
                {mergeCandidateTerritories.length > 0 ? (
                  mergeCandidateTerritories.map((t) => (
                    <label
                      key={t.id}
                      className={`merge-territory-item ${t.parent_territory_id ? "is-version" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={mergeSourceTerritoryIds.includes(t.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setMergeSourceTerritoryIds([
                              ...mergeSourceTerritoryIds,
                              t.id,
                            ]);
                          } else {
                            setMergeSourceTerritoryIds(
                              mergeSourceTerritoryIds.filter(
                                (id) => Number(id) !== Number(t.id),
                              ),
                            );
                          }
                        }}
                      />
                      <span className="merge-territory-name">
                        {t.name}
                        {t.parent_territory_id && (
                          <small>v{t.version_no || 1}</small>
                        )}
                      </span>
                      <span className="merge-zone-count">
                        {t.zone_ids?.length || 0} zones
                      </span>
                    </label>
                  ))
                ) : (
                  <p className="empty-msg">Chưa có phân vùng để gộp.</p>
                )}
              </div>
            </div>
            <div className="modal-btns">
              <button onClick={handleCreateTerritory} className="btn-success">
                Lưu
              </button>
              <button
                onClick={() => {
                  setShowTerritoryForm(false);
                  setNewTerritoryName("");
                  setSelectedRegionIdForTerritory(null);
                  setMergeSourceTerritoryIds([]);
                }}
              >
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}

      {showRegionForm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Tạo Khu vực</h3>
            <div className="form-group" style={{ marginBottom: "15px" }}>
              <label>Tên khu vực:</label>
              <input
                type="text"
                placeholder="Tên khu vực (vd: Hà Nội, TP HCM)..."
                value={newRegionName}
                onChange={(e) => setNewRegionName(e.target.value)}
              />
            </div>
            <div className="modal-btns">
              <button onClick={handleCreateRegion} className="btn-success">
                Lưu
              </button>
              <button
                onClick={() => {
                  setShowRegionForm(false);
                  setNewRegionName("");
                }}
              >
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}

      {showSalesForm && (
        <div className="modal-overlay">
          <div className="modal-content sales-modal">
            <h3>
              {editingSales ? "Chỉnh sửa Sales" : "Tạo tài khoản Sales mới"}
            </h3>
            <div className="form-grid">
              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  disabled={!!editingSales}
                  value={salesFormData.username}
                  onChange={(e) =>
                    setSalesFormData({
                      ...salesFormData,
                      username: e.target.value,
                    })
                  }
                />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={salesFormData.email}
                  onChange={(e) =>
                    setSalesFormData({
                      ...salesFormData,
                      email: e.target.value,
                    })
                  }
                />
              </div>
              {!editingSales && (
                <div className="form-group">
                  <label>Mật khẩu</label>
                  <input
                    type="password"
                    value={salesFormData.password}
                    onChange={(e) =>
                      setSalesFormData({
                        ...salesFormData,
                        password: e.target.value,
                      })
                    }
                  />
                </div>
              )}
              <div className="form-group">
                <label>Họ và Tên</label>
                <input
                  type="text"
                  value={salesFormData.full_name}
                  onChange={(e) =>
                    setSalesFormData({
                      ...salesFormData,
                      full_name: e.target.value,
                    })
                  }
                />
              </div>
              <div className="form-group">
                <label>Số điện thoại</label>
                <input
                  type="text"
                  value={salesFormData.phone}
                  onChange={(e) =>
                    setSalesFormData({
                      ...salesFormData,
                      phone: e.target.value,
                    })
                  }
                />
              </div>
              <div className="form-group">
                <label>Chọn khu vực (tùy chọn)</label>
                <select
                  value={salesFormData.region_id || ""}
                  onChange={(e) =>
                    setSalesFormData({
                      ...salesFormData,
                      region_id: e.target.value
                        ? parseInt(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">-- Không chọn --</option>
                  {regions.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="modal-btns">
              <button
                onClick={() =>
                  handleSalesAction(
                    editingSales ? "update" : "create",
                    editingSales?.id,
                    salesFormData,
                  )
                }
                className="btn-success"
              >
                {editingSales ? "Cập nhật" : "Tạo tài khoản"}
              </button>
              <button onClick={() => setShowSalesForm(false)}>Hủy</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
