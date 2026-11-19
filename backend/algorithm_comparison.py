"""
So sánh nhiều thuật toán chia vùng trên cùng một phân vùng (territory).

Thuật toán (khóa dùng trong API):
  grasp        Reactive GRASP sẵn có của app (algorithms.AdvancedTerritoryDesign) - giữ nguyên, không sửa.
  probvns      Prob-VNS, Aly et al. (2024) - research_algorithms/dtdp_probvns.py (bản bám paper).
  milp_center  MILP p-center (CTDP), Salazar-Aguilar et al. (2011), research_algorithms/paper_milp.py:
               GAMSPy/CPLEX, ICGP-TDP (Algorithm 1) với cắt liên thông (6) - cần license GAMSPy.
  milp_median  MILP p-median (MTDP), như trên.
  iqp_center   IQP p-center (QCTDP), GAMSPy/DICOPT - cần license GAMSPy.
  iqp_median   IQP p-median (QMTDP), GAMSPy/DICOPT.

Mỗi thuật toán chạy trong một tiến trình riêng (multiprocessing "spawn") với giới hạn thời gian cứng:
các thuật toán chạy song song, và một thuật toán bị treo không làm hỏng kết quả của các thuật toán khác.

Ánh xạ dữ liệu của app sang input của các thuật toán nghiên cứu:
  * khoảng cách: Haversine (km) giữa tâm zone; MILP/IQP dùng tọa độ chiếu phẳng (km) quanh tâm phân vùng;
  * cạnh: ma trận kề của app (ZoneAdjacency). MILP/IQP chỉ dùng ma trận kề thật (liên thông đúng như
    /admin/finalize-assignment kiểm tra). Prob-VNS cần đồ thị liên thông để tính đường đi ngắn nhất: nếu
    ma trận kề bị đứt, các cụm được nối bằng cạnh "cầu" giữa hai zone gần nhất (chỉ dùng để tính khoảng cách);
  * thuộc tính cân bằng: khách hàng (num_customers) và đơn hàng (num_orders); Prob-VNS cân bằng thêm
    workload = khách hàng + 0,2 x đơn hàng (công thức của app). Dung sai cân bằng tau dùng chung.
"""
from __future__ import annotations

import importlib.util
import math
import multiprocessing as mp
import random
import shutil
import tempfile
import time
import traceback
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional

# Thời gian dư cho tiến trình con (khởi động, import, xây mô hình) trước khi bị dừng cưỡng bức.
HARD_TIMEOUT_GRACE = 60

ALGORITHMS: Dict[str, Dict] = {
    "grasp": {
        "label": "Reactive GRASP (hiện có)",
        "family": "Heuristic của app",
        "modules": (),
        "contiguous": True,
        "uses_tolerance": False,
        "description": "Thuật toán mặc định của app: cân bằng workload (KH + 0,2·ĐH), phạt nặng khi CV > 15%, "
                       "giữ vùng liên thông. Không dùng tham số τ và giới hạn thời gian.",
    },
    "probvns": {
        "label": "Prob-VNS (Aly et al., 2024)",
        "family": "Metaheuristic",
        "modules": ("numpy", "scipy", "networkx"),
        "contiguous": False,
        "uses_tolerance": True,
        "description": "Bản bám paper: cực tiểu đường kính lớn nhất + vi phạm cân bằng (τ). "
                       "Không bắt buộc vùng liên thông (DTDP).",
    },
    "milp_center": {
        "label": "MILP p-center (CPLEX)",
        "family": "Chính xác – Salazar-Aguilar 2011",
        "modules": ("gamspy",),
        "contiguous": True,
        "uses_tolerance": True,
        "description": "CTDP giải bằng CPLEX qua GAMSPy (paper_milp.py, cần license): cực tiểu khoảng cách "
                       "lớn nhất từ zone tới tâm vùng, cân bằng KH/ĐH trong ±τ, liên thông bằng vòng lặp cắt.",
    },
    "milp_median": {
        "label": "MILP p-median (CPLEX)",
        "family": "Chính xác – Salazar-Aguilar 2011",
        "modules": ("gamspy",),
        "contiguous": True,
        "uses_tolerance": True,
        "description": "MTDP giải bằng CPLEX qua GAMSPy (paper_milp.py, cần license): cực tiểu tổng khoảng "
                       "cách zone tới tâm vùng, cân bằng KH/ĐH trong ±τ, liên thông.",
    },
    "iqp_center": {
        "label": "IQP p-center (GAMSPy/DICOPT)",
        "family": "Chính xác – Salazar-Aguilar 2011",
        "modules": ("gamspy",),
        "contiguous": True,
        "uses_tolerance": True,
        "description": "QCTDP giải bằng DICOPT qua GAMSPy (cần license). DICOPT cho nghiệm tối ưu cục bộ.",
    },
    "iqp_median": {
        "label": "IQP p-median (GAMSPy/DICOPT)",
        "family": "Chính xác – Salazar-Aguilar 2011",
        "modules": ("gamspy",),
        "contiguous": True,
        "uses_tolerance": True,
        "description": "QMTDP giải bằng DICOPT qua GAMSPy (cần license).",
    },
}


# ----------------------------------------------------------------------------- availability
def availability(name: str) -> Dict:
    info = ALGORITHMS.get(name)
    if info is None:
        return {"available": False, "reason": f"Thuật toán không tồn tại: {name}"}
    missing = [m for m in info["modules"] if importlib.util.find_spec(m) is None]
    if missing:
        return {"available": False,
                "reason": f"Thiếu thư viện Python: {', '.join(missing)} (pip install {' '.join(missing)})"}
    return {"available": True, "reason": ""}


def list_algorithms() -> List[Dict]:
    out = []
    for key, info in ALGORITHMS.items():
        item = {k: v for k, v in info.items() if k != "modules"}
        item.update({"key": key, **availability(key)})
        out.append(item)
    return out


# ----------------------------------------------------------------------------- data helpers
def zone_workload(zone: Dict) -> float:
    return float(zone.get("num_customers") or 0) + 0.2 * float(zone.get("num_orders") or 0)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(min(1.0, math.sqrt(a)))


def build_problem(zones: List[Dict], adj_list: Dict, num_sales: int, tolerance: float,
                  time_limit: int, seed: int) -> Dict:
    """Plain, picklable problem description shared by every solver process."""
    zone_ids = [int(z["id"]) for z in zones]
    id_set = set(zone_ids)
    adjacency = {zid: sorted({int(n) for n in adj_list.get(zid, []) if int(n) in id_set and int(n) != zid})
                 for zid in zone_ids}
    for zid, neighbors in list(adjacency.items()):  # make symmetric
        for n in neighbors:
            if zid not in adjacency[n]:
                adjacency[n] = sorted(set(adjacency[n]) | {zid})
    clean = [{
        "id": int(z["id"]),
        "code": z.get("code"),
        "lat": float(z.get("lat")),
        "lng": float(z.get("lng")),
        "num_customers": int(z.get("num_customers") or 0),
        "num_orders": int(z.get("num_orders") or 0),
        "revenue": float(z.get("revenue") or 0),
    } for z in zones]
    return {"zones": clean, "adjacency": adjacency, "num_sales": int(num_sales),
            "tolerance": float(tolerance), "time_limit": int(time_limit), "seed": int(seed)}


def _components(node_ids, adjacency) -> List[List[int]]:
    remaining = set(node_ids)
    comps = []
    while remaining:
        start = min(remaining)
        seen = {start}
        queue = deque([start])
        while queue:
            for n in adjacency.get(queue.popleft(), []):
                if n in remaining and n not in seen:
                    seen.add(n)
                    queue.append(n)
        comps.append(sorted(seen))
        remaining -= seen
    return comps


def bridged_edges(problem: Dict):
    """Adjacency edges plus 'bridge' edges joining disconnected components (closest pair of zones)."""
    zones = {z["id"]: z for z in problem["zones"]}
    edges = {(min(u, v), max(u, v)) for u, ns in problem["adjacency"].items() for v in ns}
    comps = _components(list(zones), problem["adjacency"])
    bridges = []
    while len(comps) > 1:
        base, best = comps[0], None
        for ci in range(1, len(comps)):
            for u in base:
                for v in comps[ci]:
                    d = haversine_km(zones[u]["lat"], zones[u]["lng"], zones[v]["lat"], zones[v]["lng"])
                    if best is None or d < best[0]:
                        best = (d, u, v, ci)
        _, u, v, ci = best
        bridges.append((min(u, v), max(u, v)))
        edges.add((min(u, v), max(u, v)))
        comps[0] = sorted(base + comps[ci])
        comps.pop(ci)
    return sorted(edges), bridges


def _projected_km(zones: List[Dict]) -> Dict[int, tuple]:
    lat0 = sum(z["lat"] for z in zones) / len(zones)
    lng0 = sum(z["lng"] for z in zones) / len(zones)
    kx = 6371.0088 * math.pi / 180 * math.cos(math.radians(lat0))
    ky = 6371.0088 * math.pi / 180
    return {z["id"]: ((z["lng"] - lng0) * kx, (z["lat"] - lat0) * ky) for z in zones}


# ----------------------------------------------------------------------------- solvers (run in child)
def _solve_grasp(problem: Dict) -> Dict:
    from algorithms import AdvancedTerritoryDesign

    random.seed(problem["seed"])
    designer = AdvancedTerritoryDesign(problem["zones"], problem["adjacency"])
    result = designer.solve(problem["num_sales"], "grasp")
    if result.get("error"):
        return {"status": "FAILED", "message": result["error"], "territories": None}
    terr = result.get("territories", {})
    territories = [list(terr.get(i, terr.get(str(i), []))) for i in range(problem["num_sales"])]
    return {"status": "OK", "message": "", "territories": territories, "details": {}}


def _solve_probvns(problem: Dict) -> Dict:
    import networkx as nx
    import numpy as np
    from research_algorithms import dtdp_probvns as dtdp

    start = time.time()
    random.seed(problem["seed"])
    np.random.seed(problem["seed"] % (2 ** 32))
    zones, p = problem["zones"], problem["num_sales"]
    if p == 1:
        return {"status": "OK", "message": "", "territories": [[z["id"] for z in zones]], "details": {}}

    G = nx.Graph()
    for z in zones:
        G.add_node(str(z["id"]), workload=zone_workload(z), n_customers=z["num_customers"],
                   demand=z["num_orders"])
    by_id = {z["id"]: z for z in zones}
    edges, bridges = bridged_edges(problem)
    for u, v in edges:
        d = haversine_km(by_id[u]["lat"], by_id[u]["lng"], by_id[v]["lat"], by_id[v]["lng"])
        G.add_edge(str(u), str(v), distance=max(d, 1e-3))

    # The DTDP code hard-codes the attribute names workload / n_customers / demand. Attributes whose total is 0
    # are not balanced; if all are 0, the number of zones is balanced instead (stored under "workload").
    acts = [a for a in ("workload", "n_customers", "demand") if sum(G.nodes[v][a] for v in G) > 0]
    if not acts:
        for v in G:
            G.nodes[v]["workload"] = 1
        acts = ["workload"]
    dtdp.activities[:] = acts  # this process only
    tdp = dtdp.TerritoryDesignProblem(G, delta=problem["tolerance"], llambda=0.7, rcl_parameter=0.5,
                                      nr_districts=p)
    vns = dtdp.BVNS(tdp, k_max=5, l_max=4, r_max=4, nrInitSolutions=100, lambdaRange=[0.1, 0.4, 0.7, 1],
                    max_moves=1000, deadline=start + problem["time_limit"])
    obj_hist, inf_hist, best, _ = vns.performBVNS()
    territories = [[int(v) for v in best.get(k, [])] for k in sorted(best)]
    return {
        "status": "TIME_LIMIT" if vns.timed_out else "OK",
        "message": "Hết thời gian: trả về nghiệm tốt nhất đã tìm được." if vns.timed_out else "",
        "territories": territories,
        "details": {"diameter_graph_km": round(float(obj_hist[-1]), 3),
                    "paper_infeasibility": round(float(inf_hist[-1]), 6),
                    "improvements": len(obj_hist) - 1,
                    "balanced_attributes": (list(dtdp.activities) if any(G.nodes[v]["n_customers"] or
                                                                          G.nodes[v]["demand"] for v in G)
                                            else ["zone_count"]),
                    "bridged_edges": len(bridges)},
    }


def _exact_instance(problem: Dict):
    """Exact models enforce contiguity, so they use the app's real adjacency only (no bridge edges):
    a territory is then connected exactly in the sense checked by /admin/finalize-assignment."""
    from research_algorithms.tdp_common import Instance

    zones = sorted(problem["zones"], key=lambda z: z["id"])
    ids = [z["id"] for z in zones]
    index = {zid: i for i, zid in enumerate(ids)}
    xy = _projected_km(zones)
    edges = sorted({(min(u, v), max(u, v)) for u, ns in problem["adjacency"].items() for v in ns})
    instance = Instance(
        path=Path(f"territory_{len(ids)}_zones"),
        coordinates=tuple(xy[zid] for zid in ids),
        activities=tuple((int(z["num_customers"]), int(z["num_orders"])) for z in zones),
        edges=tuple(sorted((index[u], index[v]) for u, v in edges)),
        territories=problem["num_sales"],
        tolerances=(problem["tolerance"], problem["tolerance"]),
    )
    return instance, ids, len(_components(ids, problem["adjacency"]))


def _too_many_components(problem: Dict, components: int) -> Optional[Dict]:
    if components > problem["num_sales"]:
        return {"status": "INFEASIBLE", "territories": None,
                "message": f"Ma trận kề có {components} cụm zone rời nhau > {problem['num_sales']} sales: "
                           "không thể chia thành các vùng liên thông."}
    return None


def _clean_bound(value):
    return None if value is None or abs(value) >= 1e19 else value


def _territories_from(result: Dict, ids: List[int]) -> Optional[List[List[int]]]:
    if "assignment" not in result:
        return None
    centers = list(result["centers"])
    groups = {c: [] for c in centers}
    for node, center in enumerate(result["assignment"]):
        groups[center].append(ids[node])
    return [groups[c] for c in centers]


EXACT_MESSAGES = {
    "OPTIMAL": "Tối ưu (đã chứng minh).",
    "FEASIBLE_TIME_LIMIT": "Có nghiệm liên thông nhưng chưa chứng minh tối ưu (hết thời gian).",
    "TIME_LIMIT": "Hết thời gian trước khi có nghiệm liên thông.",
    "INFEASIBLE": "Vô nghiệm với dung sai τ hiện tại – thử tăng τ.",
    "NO_PROOF": "Solver dừng mà không có nghiệm.",
    "CONNECTED": "Có nghiệm liên thông (DICOPT – tối ưu cục bộ).",
}


def _solve_milp(problem: Dict, objective: str) -> Dict:
    # Không giới hạn số zone: CPLEX (license GAMSPy academic) giải được phân vùng vài trăm zone;
    # mô hình lớn chỉ tốn thời gian hơn và dừng theo time_limit.
    from research_algorithms import paper_milp

    instance, ids, components = _exact_instance(problem)
    blocked = _too_many_components(problem, components)
    if blocked:
        return blocked
    # R1 adds inequality (21); it holds for every connected territory, so it only tightens the model.
    workdir = Path(tempfile.mkdtemp(prefix="milp_logs_"))
    try:
        res = paper_milp.solve(instance, objective, "R1", float(problem["time_limit"]), workdir,
                               optcr=5e-6, threads=1)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    territories = _territories_from(res, ids)
    status = res["status"]
    message = EXACT_MESSAGES.get(status)
    if message is None:
        message = ("Solver dừng mà không có nghiệm – thử tăng τ hoặc thời gian."
                   if status.startswith("NO_SOLUTION") else status)
    return {
        "status": "OK" if status == "OPTIMAL" else status,
        "message": message,
        "territories": territories,
        "details": {"model": res.get("model"), "solver": res.get("solver"), "relaxation": res.get("relaxation"),
                    "objective_km": res.get("objective_value"),
                    "best_lower_bound": _clean_bound(res.get("best_lower_bound")),
                    "proven_optimal": status == "OPTIMAL", "iterations": res.get("iterations"),
                    "connectivity_cuts": res.get("connectivity_cuts"), "adjacency_components": components},
    }


def _solve_iqp(problem: Dict, objective: str) -> Dict:
    from research_algorithms import gams_iqp

    instance, ids, components = _exact_instance(problem)
    blocked = _too_many_components(problem, components)
    if blocked:
        return blocked
    p, tau = instance.territories, problem["tolerance"]
    totals = [sum(w[a] for w in instance.activities) for a in range(2)]
    # Inequality (20) (relaxation R1, used in the paper) is valid only if w_j^a < (1 - tau) mu^a for all j, a.
    r1_valid = all(w[a] < (1 - tau) * totals[a] / p for w in instance.activities for a in range(2))
    workdir = Path(tempfile.mkdtemp(prefix="iqp_"))
    try:
        res = gams_iqp.solve(instance, objective, "R1" if r1_valid else "R", float(problem["time_limit"]),
                             gams=None, workdir=workdir, optcr=None, nlp=None, threads=1, backend="gamspy")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    territories = _territories_from(res, ids)
    status = res["status"]
    message = EXACT_MESSAGES.get(status)
    if message is None:
        message = ("Vô nghiệm/không tìm được nghiệm (DICOPT) – thử tăng τ hoặc thời gian."
                   if status.startswith("NO_SOLUTION") or status == "INFEASIBLE" else status)
    last_error = next((h.get("error") for h in reversed(res.get("history", [])) if h.get("error")), None)
    if last_error:
        message = f"{message} ({last_error})"
    return {
        "status": "OK" if status == "CONNECTED" else status,
        "message": message,
        "territories": territories,
        "details": {"model": res.get("model"), "relaxation": res.get("relaxation"),
                    "objective_km": res.get("objective_value"), "last_modelstat": res.get("last_modelstat"),
                    "iterations": res.get("iterations"), "connectivity_cuts": res.get("connectivity_cuts"),
                    "adjacency_components": components},
    }


def _dispatch(name: str, problem: Dict) -> Dict:
    if name == "grasp":
        return _solve_grasp(problem)
    if name == "probvns":
        return _solve_probvns(problem)
    if name in ("milp_center", "milp_median"):
        return _solve_milp(problem, name.split("_")[1])
    if name in ("iqp_center", "iqp_median"):
        return _solve_iqp(problem, name.split("_")[1])
    raise ValueError(f"Unknown algorithm: {name}")


def _child(conn, name: str, problem: Dict) -> None:
    start = time.perf_counter()
    try:
        out = _dispatch(name, problem)
    except Exception as exc:  # report, never crash silently
        out = {"status": "ERROR", "message": f"{type(exc).__name__}: {exc}", "territories": None,
               "traceback": traceback.format_exc(limit=8)}
    out["solve_seconds"] = round(time.perf_counter() - start, 3)
    try:
        conn.send(out)
    finally:
        conn.close()


def run_algorithms(problem: Dict, names: List[str]) -> Dict[str, Dict]:
    """Run every algorithm in its own process (in parallel) with a hard wall-clock cap."""
    ctx = mp.get_context("spawn")
    results: Dict[str, Dict] = {}
    jobs = {}
    for name in names:
        avail = availability(name)
        if not avail["available"]:
            results[name] = {"status": "UNAVAILABLE", "message": avail["reason"], "territories": None}
            continue
        receiver, sender = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_child, args=(sender, name, problem), daemon=True)
        proc.start()
        sender.close()
        jobs[name] = (proc, receiver, time.monotonic())

    cap = problem["time_limit"] + HARD_TIMEOUT_GRACE
    while jobs:
        for name, (proc, receiver, started) in list(jobs.items()):
            elapsed = time.monotonic() - started
            if receiver.poll():
                try:
                    results[name] = receiver.recv()
                except EOFError:
                    results[name] = {"status": "ERROR", "message": "Tiến trình kết thúc bất thường.",
                                     "territories": None}
                proc.join(5)
            elif not proc.is_alive():
                results[name] = {"status": "ERROR", "territories": None,
                                 "message": f"Tiến trình dừng với mã {proc.exitcode}."}
            elif elapsed > cap:
                proc.terminate()
                proc.join(5)
                results[name] = {"status": "TIMEOUT", "territories": None,
                                 "message": f"Bị dừng sau {cap} s (giới hạn thời gian + {HARD_TIMEOUT_GRACE} s)."}
            else:
                continue
            results[name]["wall_seconds"] = round(elapsed, 3)
            receiver.close()
            jobs.pop(name)
        if jobs:
            time.sleep(0.1)
    return results


# ----------------------------------------------------------------------------- post-processing & metrics
def complete_territories(problem: Dict, territories: List[List[int]]):
    """Exactly p lists; unknown/duplicate ids dropped; missing zones go to the lightest adjacent territory."""
    p = problem["num_sales"]
    zones = {z["id"]: z for z in problem["zones"]}
    out = [[] for _ in range(p)]
    owner = {}
    for i, terr in enumerate(list(territories)[:p]):
        for zid in terr:
            zid = int(zid)
            if zid in zones and zid not in owner:
                owner[zid] = i
                out[i].append(zid)
    missing = [zid for zid in zones if zid not in owner]
    for zid in missing:
        loads = [sum(zone_workload(zones[z]) for z in terr) for terr in out]
        neighbors = {owner[n] for n in problem["adjacency"].get(zid, []) if n in owner}
        target = min(neighbors or range(p), key=lambda i: loads[i])
        owner[zid] = target
        out[target].append(zid)
    return out, len(missing)


def align_territories(reference: List[List[int]], territories: List[List[int]]) -> List[List[int]]:
    """Reorder territories so that territory i overlaps most with reference territory i (same colour on maps)."""
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
    except ImportError:
        return territories
    ref = [set(t) for t in reference]
    cost = np.array([[-len(ref[i] & set(t)) for t in territories] for i in range(len(ref))])
    rows, cols = linear_sum_assignment(cost)
    order = [None] * len(territories)
    for r, c in zip(rows, cols):
        order[r] = territories[c]
    return [t if t is not None else [] for t in order]


def evaluate(problem: Dict, territories: List[List[int]]) -> Dict:
    from algorithms import AdvancedTerritoryDesign

    p, tau = problem["num_sales"], problem["tolerance"]
    zones = {z["id"]: z for z in problem["zones"]}
    adjacency = problem["adjacency"]
    designer = AdvancedTerritoryDesign(problem["zones"], adjacency)
    assignment = {zid: i for i, terr in enumerate(territories) for zid in terr}
    _, total_distance, cv_pct, hoover = designer._evaluate_workloads(assignment, p)

    def dist(a, b):
        return haversine_km(zones[a]["lat"], zones[a]["lng"], zones[b]["lat"], zones[b]["lng"])

    activities = {"customers": "num_customers", "orders": "num_orders"}
    totals = {a: sum(z[f] for z in zones.values()) for a, f in activities.items()}
    per_territory, g_total = [], 0.0
    max_dev = {a: 0.0 for a in activities}
    for terr in territories:
        loads = {a: sum(zones[z][f] for z in terr) for a, f in activities.items()}
        for a in activities:
            mu = totals[a] / p
            if mu > 0:
                max_dev[a] = max(max_dev[a], abs(loads[a] - mu) / mu * 100)
                g_total += max(loads[a] - (1 + tau) * mu, (1 - tau) * mu - loads[a], 0) / mu
        if terr:
            diameter = max((dist(a, b) for i, a in enumerate(terr) for b in terr[i + 1:]), default=0.0)
            radius = min(max(dist(c, z) for z in terr) for c in terr)
            median = min(sum(dist(c, z) for z in terr) for c in terr)
            connected = len(_components(terr, adjacency)) == 1
        else:
            diameter = radius = median = 0.0
            connected = True
        per_territory.append({
            "zones": len(terr), "customers": loads["customers"], "orders": loads["orders"],
            "workload": round(sum(zone_workload(zones[z]) for z in terr), 2),
            "diameter_km": round(diameter, 3), "radius_km": round(radius, 3), "connected": connected,
        })
        if terr:
            per_territory[-1]["median_km"] = round(median, 3)
    return {
        "cv_pct": round(cv_pct, 3),
        "hoover_index": round(hoover, 3),
        "total_distance": round(total_distance, 6),
        "max_diameter_km": round(max(t["diameter_km"] for t in per_territory), 3),
        "max_radius_km": round(max(t["radius_km"] for t in per_territory), 3),
        "sum_median_km": round(sum(t.get("median_km", 0) for t in per_territory), 3),
        "max_dev_customers_pct": round(max_dev["customers"], 2),
        "max_dev_orders_pct": round(max_dev["orders"], 2),
        "balance_violation": round(g_total, 6),
        "balanced": g_total <= 1e-9,
        "disconnected_territories": sum(not t["connected"] for t in per_territory),
        "empty_territories": sum(t["zones"] == 0 for t in per_territory),
        "per_territory": per_territory,
    }


def compare(problem: Dict, names: List[str]) -> List[Dict]:
    """Run the algorithms and return one report per algorithm, in the requested order."""
    raw = run_algorithms(problem, names)
    reports, reference = [], None
    for name in names:
        res = raw[name]
        report = {
            "algorithm": name,
            "label": ALGORITHMS[name]["label"],
            "contiguous_model": ALGORITHMS[name]["contiguous"],
            "status": res.get("status"),
            "message": res.get("message", ""),
            "solve_seconds": res.get("solve_seconds"),
            "wall_seconds": res.get("wall_seconds"),
            "details": res.get("details", {}),
            "ok": bool(res.get("territories")),
            "territories": None,
            "metrics": None,
        }
        if res.get("traceback"):
            report["traceback"] = res["traceback"]
        if report["ok"]:
            territories, repaired = complete_territories(problem, res["territories"])
            if reference is None:
                reference = territories
            else:
                territories = align_territories(reference, territories)
            report["territories"] = territories
            report["details"]["completed_zones"] = repaired
            report["metrics"] = evaluate(problem, territories)
        reports.append(report)
    return reports
