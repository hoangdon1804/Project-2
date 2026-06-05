"""
Commercial Territory Design Algorithms
- Local Tabu Search: Tối ưu hóa địa phương với Tabu list
- Reactive GRASP: Thuật toán metaheuristic với filtering
"""

import math
import random
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict, deque
import time

@dataclass
class Zone:
    id: int
    code: str
    lat: float
    lng: float
    num_customers: int = 0
    num_orders: int = 0
    revenue: float = 0.0
    workload: float = 0.0  # Điểm tải trong thuật toán


class TerritoryAlgorithm:
    """Base class cho các thuật toán chia phân vùng"""
    
    def __init__(self, zones: List[Dict], distances: Dict[int, Dict[int, float]]):
        """
        Args:
            zones: List các zone với {id, code, lat, lng, num_customers, num_orders, revenue}
            distances: Dict {zone_id1: {zone_id2: distance}}
        """
        self.zones = [
            Zone(
                id=z['id'],
                code=z['code'],
                lat=z['lat'],
                lng=z['lng'],
                num_customers=z.get('num_customers', 0),
                num_orders=z.get('num_orders', 0),
                revenue=z.get('revenue', 0.0)
            )
            for z in zones
        ]
        self.distances = distances
        self.zone_map = {z.id: z for z in self.zones}
        self.territories = {}
        self.execution_time = 0
        self.quality_score = 0
        
    def _calculate_workload(self, zone: Zone) -> float:
        """Tính điểm tải cho một zone (kết hợp số lượng và vị trí)"""
        # Công thức: workload = customers * 0.4 + orders * 0.3 + revenue/100000 * 0.3
        return (zone.num_customers * 0.4 + 
                zone.num_orders * 0.3 + 
                (zone.revenue / 100000) * 0.3)
    
    def _calculate_distance(self, zone1: Zone, zone2: Zone) -> float:
        """Tính khoảng cách giữa 2 zones"""
        if zone1.id in self.distances and zone2.id in self.distances[zone1.id]:
            return self.distances[zone1.id][zone2.id]
        # Fallback: tính Haversine distance
        return self._haversine_distance(
            zone1.lat, zone1.lng, zone2.lat, zone2.lng
        )
    
    @staticmethod
    def _haversine_distance(lat1: float, lng1: float, 
                           lat2: float, lng2: float) -> float:
        """Tính khoảng cách Haversine (km)"""
        R = 6371  # Bán kính Trái Đất (km)
        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    
    def _evaluate_solution(self) -> Dict:
        """Đánh giá chất lượng của giải pháp"""
        metrics = {
            'balance_score': 0,
            'contiguity_score': 0,
            'compactness_score': 0,
            'overall_score': 0
        }
        
        # 1. Balance score: Cân bằng tải giữa các phân vùng
        workloads = []
        for territory_zones in self.territories.values():
            total_workload = sum(self._calculate_workload(self.zone_map[zid]) 
                               for zid in territory_zones)
            workloads.append(total_workload)
        
        if workloads:
            avg_workload = sum(workloads) / len(workloads)
            variance = sum((w - avg_workload)**2 for w in workloads) / len(workloads)
            balance_score = 100 / (1 + math.sqrt(variance))
            metrics['balance_score'] = min(100, balance_score)
        
        # 2. Overall score (trung bình các điểm)
        metrics['overall_score'] = metrics['balance_score']
        
        return metrics
    
    def solve(self) -> Dict:
        """Solve the territory design problem"""
        raise NotImplementedError


class AdvancedTerritoryDesign(TerritoryAlgorithm):
    """Advanced Territory Design với Local Tabu Search và Reactive GRASP"""
    
    def __init__(self, zones: List[Dict], adj_list: Dict):
        """
        Args:
            zones: List các zone với {id, code, lat, lng, num_customers, num_orders, revenue}
            adj_list: Dict {zone_id: [neighbor_zone_ids]}
        """
        # Chuyển đổi dữ liệu từ DB sang format của test.py
        self.nodes = {
            z['id']: {
                'x': z['lng'], # lng tương ứng x
                'y': z['lat'], # lat tương ứng y
                'customers': z.get('num_customers', 0),
                'orders': z.get('num_orders', 0)
            } for z in zones
        }
        self.adj_list = {z['id']: set(adj_list.get(z['id'], [])) for z in zones}
        self.zone_data = {z['id']: z for z in zones}
    
    # ==========================================
    # HÀM HỖ TRỢ TÍNH TOÁN CƠ BẢN & WORKLOAD
    # ==========================================
    
    @staticmethod
    def _calculate_distance(node1: Dict, node2: Dict) -> float:
        """Tính khoảng cách Euclid giữa 2 node"""
        return math.sqrt((node1['x'] - node2['x'])**2 + (node1['y'] - node2['y'])**2)
    
    @staticmethod
    def _calculate_centroid(nodes: Dict, cluster_node_ids: List[int]) -> Dict:
        """Tính tâm của một cluster"""
        if not cluster_node_ids:
            return {'x': 0, 'y': 0}
        sum_x = sum(nodes[n]['x'] for n in cluster_node_ids)
        sum_y = sum(nodes[n]['y'] for n in cluster_node_ids)
        count = len(cluster_node_ids)
        return {'x': sum_x / count, 'y': sum_y / count}
    
    @staticmethod
    def _get_node_w1(node: Dict) -> float:
        """Tính workload của một node: customers * 1.0 + orders * 0.2"""
        return node['customers'] * 1.0 + node['orders'] * 0.2
    
    @staticmethod
    def _calculate_score(cv: float, dist: float) -> float:
        """Hàm đánh giá chung: Phạt nặng nếu CV vượt 15% để ép cân bằng"""
        penalty = 1000000 if cv > 15.0 else 0 
        return (cv * 10000) + dist + penalty
    
    def _evaluate_workloads(self, assignment: Dict, num_sales: int) -> Tuple[Dict, float, float, float]:
        """
        Đánh giá workloads của phân vùng
        Returns: (metrics, total_distance, cv_pct, hoover_index)
        """
        clusters = defaultdict(list)
        for node_id, sales_id in assignment.items():
            if sales_id != -1:  # Bỏ qua node chưa gán
                clusters[sales_id].append(node_id)
        
        metrics = {}
        total_distance_all = 0
        
        for sales_id in range(num_sales):
            cluster_nodes = clusters[sales_id]
            if not cluster_nodes:
                metrics[sales_id] = {
                    'nodes': [], 'customers': 0, 'orders': 0,
                    'distance': 0, 'w1': 0
                }
                continue
            
            sum_cust = sum(self.nodes[n]['customers'] for n in cluster_nodes)
            sum_ord = sum(self.nodes[n]['orders'] for n in cluster_nodes)
            
            centroid = self._calculate_centroid(self.nodes, cluster_nodes)
            distance = sum(self._calculate_distance(centroid, self.nodes[n]) 
                          for n in cluster_nodes)
            total_distance_all += distance
            
            w1 = sum_cust * 1.0 + sum_ord * 0.2
            
            metrics[sales_id] = {
                'nodes': sorted(cluster_nodes),
                'customers': sum_cust,
                'orders': sum_ord,
                'distance': round(distance, 2),
                'w1': round(w1, 2)
            }
        
        w1_values = [m['w1'] for m in metrics.values()]
        mean_w1 = sum(w1_values) / num_sales if num_sales > 0 else 1
        total_w1 = sum(w1_values)
        
        # Tính Hệ số biến thiên (CV) và Chỉ số Hoover
        variance = sum((x - mean_w1)**2 for x in w1_values) / num_sales if num_sales > 0 else 0
        cv_pct = (math.sqrt(variance) / mean_w1 * 100) if mean_w1 > 0 else 0
        hoover_index = (0.5 * sum(abs(x - mean_w1) for x in w1_values) / total_w1 * 100) if total_w1 > 0 else 0
        
        return metrics, total_distance_all, cv_pct, hoover_index
    
    def _is_connected_without_node(self, nodes_in_region: List[int], node_to_remove: int) -> bool:
        """Kiểm tra liên thông của vùng khi xóa một node"""
        remaining_nodes = set(nodes_in_region)
        remaining_nodes.discard(node_to_remove)
        
        if not remaining_nodes:
            return True 
        
        start_node = next(iter(remaining_nodes))
        visited = {start_node}
        queue = deque([start_node])
        
        while queue:
            curr = queue.popleft()
            for neighbor in self.adj_list.get(curr, []):
                if neighbor in remaining_nodes and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return len(visited) == len(remaining_nodes)
    
    # ==========================================
    # THUẬT TOÁN TABU SEARCH
    # ==========================================
    
    def _tabu_search(self, assignment: Dict, num_sales: int, max_iter: int = 100) -> Dict:
        """
        Tabu Search - Sử dụng tabu list để tránh lặp lại các move cũ
        """
        assignment = assignment.copy()
        best_assignment = assignment.copy()
        
        _, best_dist, best_cv, _ = self._evaluate_workloads(best_assignment, num_sales)
        best_overall_score = self._calculate_score(best_cv, best_dist)
        tabu_list = {}
        
        for iteration in range(max_iter):
            best_move = None
            best_move_score = float('inf')
            
            for node_id, current_sales in assignment.items():
                neighbor_sales_set = {
                    assignment[neighbor] 
                    for neighbor in self.adj_list.get(node_id, [])
                    if assignment[neighbor] != current_sales
                }
                if not neighbor_sales_set:
                    continue
                
                nodes_in_current = [n for n, s in assignment.items() if s == current_sales]
                if not self._is_connected_without_node(nodes_in_current, node_id):
                    continue
                
                for target_sales in neighbor_sales_set:
                    move = (node_id, current_sales, target_sales)
                    
                    assignment[node_id] = target_sales
                    _, new_dist, new_cv, _ = self._evaluate_workloads(assignment, num_sales)
                    assignment[node_id] = current_sales
                    
                    new_score = self._calculate_score(new_cv, new_dist)
                    is_tabu = move in tabu_list and tabu_list[move] > iteration
                    
                    if not is_tabu or new_score < best_overall_score:
                        if new_score < best_move_score:
                            best_move_score = new_score
                            best_move = move
            
            if best_move is None:
                break
            
            node_id, old_s, new_s = best_move
            assignment[node_id] = new_s
            
            dynamic_tenure = random.randint(5, 10)
            tabu_list[(node_id, new_s, old_s)] = iteration + dynamic_tenure
            
            if best_move_score < best_overall_score:
                best_overall_score = best_move_score
                best_assignment = assignment.copy()
        
        return best_assignment
    
    # ==========================================
    # THUẬT TOÁN REACTIVE GRASP VỚI FILTERING
    # ==========================================
    
    @staticmethod
    def _get_max_distance(nodes: Dict) -> float:
        """Tính khoảng cách lớn nhất giữa 2 nodes"""
        d_max = 0
        node_ids = list(nodes.keys())
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                d = AdvancedTerritoryDesign._calculate_distance(
                    nodes[node_ids[i]], nodes[node_ids[j]]
                )
                if d > d_max:
                    d_max = d
        return d_max if d_max > 0 else 1
    
    def _eval_merit_function(self, assignment: Dict, num_sales: int, tau: float, 
                            d_max: float, lambd: float = 0.5) -> Tuple[float, float, float]:
        """Đánh giá hàm merit cho GRASP"""
        clusters = defaultdict(list)
        for nid, sid in assignment.items():
            if sid != -1:
                clusters[sid].append(nid)
        
        total_w1 = sum(self._get_node_w1(self.nodes[n]) for n in self.nodes)
        mu = total_w1 / num_sales if num_sales > 0 else 1
        
        max_dispersion = 0
        for sid, cluster in clusters.items():
            if not cluster:
                continue
            centroid = self._calculate_centroid(self.nodes, cluster)
            max_dist_in_cluster = max(
                [self._calculate_distance(centroid, self.nodes[n]) for n in cluster] + [0]
            )
            if max_dist_in_cluster > max_dispersion:
                max_dispersion = max_dist_in_cluster
        
        F_S = max_dispersion / d_max
        
        G_S = 0
        for sid in range(num_sales):
            cluster = clusters.get(sid, [])
            w_cluster = sum(self._get_node_w1(self.nodes[n]) for n in cluster)
            violation = max(w_cluster - (1 + tau)*mu, (1 - tau)*mu - w_cluster, 0)
            G_S += violation / mu
        
        psi_S = lambd * F_S + (1 - lambd) * G_S
        return psi_S, F_S, G_S
    
    def _construct_greedy_randomized(self, num_sales: int, alpha: float, rho: float, 
                                    tau: float, d_max: float, lambd: float = 0.5) -> Tuple[Dict, int]:
        """Xây dựng giải pháp bằng greedy randomized"""
        node_ids = list(self.nodes.keys())
        unassigned = set(node_ids)
        assignment = {nid: -1 for nid in node_ids}
        
        degrees = {n: len(self.adj_list.get(n, [])) for n in node_ids}
        start_node = min(degrees, key=degrees.get)
        
        q = 0
        territories = defaultdict(list)
        territories[q].append(start_node)
        assignment[start_node] = q
        unassigned.remove(start_node)
        
        total_w1 = sum(self._get_node_w1(self.nodes[n]) for n in self.nodes)
        mu = total_w1 / num_sales
        
        while unassigned:
            neighbors = set()
            for n in territories[q]:
                neighbors.update(self.adj_list.get(n, []))
            valid_neighbors = list(neighbors.intersection(unassigned))
            
            current_w1 = sum(self._get_node_w1(self.nodes[n]) for n in territories[q])
            if not valid_neighbors or current_w1 > rho * (1 + tau) * mu:
                q += 1
                next_start = min((n for n in unassigned), key=lambda x: degrees[x])
                territories[q].append(next_start)
                assignment[next_start] = q
                unassigned.remove(next_start)
                continue
            
            phi_values = {}
            centroid = self._calculate_centroid(self.nodes, territories[q])
            f_Vk = max(
                [self._calculate_distance(centroid, self.nodes[n]) for n in territories[q]] + [0]
            )
            
            for v in valid_neighbors:
                d_v = self._calculate_distance(centroid, self.nodes[v])
                F_k_v = max(f_Vk, d_v) / d_max
                w_new = current_w1 + self._get_node_w1(self.nodes[v])
                G_k_v = max(w_new - (1 + tau) * mu, 0) / mu
                phi_values[v] = lambd * F_k_v + (1 - lambd) * G_k_v
            
            phi_min = min(phi_values.values())
            phi_max = max(phi_values.values())
            threshold = phi_min + alpha * (phi_max - phi_min)
            rcl = [v for v, phi in phi_values.items() if phi <= threshold]
            
            chosen_v = random.choice(rcl)
            territories[q].append(chosen_v)
            assignment[chosen_v] = q
            unassigned.remove(chosen_v)
        
        return assignment, q + 1
    
    def _adjustment_phase(self, assignment: Dict, q: int, num_sales: int) -> Dict:
        """Điều chỉnh nếu số vùng > num_sales"""
        if q <= num_sales:
            return assignment
        
        current_q = q
        while current_q > num_sales:
            w_sizes = {
                sid: sum(self._get_node_w1(self.nodes[n]) 
                        for n, s in assignment.items() if s == sid)
                for sid in range(current_q)
            }
            smallest_sid = min(w_sizes, key=w_sizes.get)
            
            neighbor_sids = set()
            for nid, sid in assignment.items():
                if sid == smallest_sid:
                    for neighbor in self.adj_list.get(nid, []):
                        n_sid = assignment[neighbor]
                        if n_sid != smallest_sid:
                            neighbor_sids.add(n_sid)
            
            if not neighbor_sids:
                break
            
            target_sid = min(neighbor_sids, key=lambda s: w_sizes[s])
            for nid in [k for k, v in assignment.items() if v == smallest_sid]:
                assignment[nid] = target_sid
            
            current_q -= 1
            
            unique_sids = list(set(assignment.values()))
            mapping = {old: new for new, old in enumerate(unique_sids)}
            for nid in assignment:
                assignment[nid] = mapping[assignment[nid]]
        
        return assignment
    
    def _post_processing_local_search(self, num_sales: int, assignment: Dict, 
                                     tau: float, d_max: float, limit_moves: int = 100) -> Tuple[Dict, float]:
        """Post-processing local search cho GRASP"""
        assignment = assignment.copy()
        current_psi, _, _ = self._eval_merit_function(assignment, num_sales, tau, d_max)
        
        moves = 0
        while moves < limit_moves:
            moved = False
            node_ids = list(assignment.keys())
            random.shuffle(node_ids)
            
            for i in node_ids:
                current_s = assignment[i]
                neighbor_sids = {
                    assignment[j] 
                    for j in self.adj_list.get(i, [])
                    if assignment[j] != current_s
                }
                if not neighbor_sids:
                    continue
                
                nodes_in_current = [n for n, s in assignment.items() if s == current_s]
                if not self._is_connected_without_node(nodes_in_current, i):
                    continue
                
                for j_s in neighbor_sids:
                    assignment[i] = j_s
                    new_psi, _, _ = self._eval_merit_function(assignment, num_sales, tau, d_max)
                    
                    if new_psi < current_psi:
                        current_psi = new_psi
                        moved = True
                        break
                    else:
                        assignment[i] = current_s
                
                if moved:
                    break
            
            if not moved:
                break
            moves += 1
        
        return assignment, current_psi
    
    def _reactive_grasp_filter(self, num_sales: int, limit_iterations: int = 100,
                              update_period: int = 20) -> Dict:
        """
        Reactive GRASP với Filtering
        """
        d_max = self._get_max_distance(self.nodes)
        tau = 0.1
        rho = 0.8
        beta = 0.6
        delta = 8
        
        A_set = [0.1, 0.2, 0.3, 0.4, 0.5]
        m = len(A_set)
        p_probs = [1/m] * m
        
        best_assignment = None
        best_psi = float('inf')
        
        sum_beta_reduction = 0
        times_ls_called = 0
        avg_beta = 0.0
        
        sum_A = [0] * m
        count_A = [0] * m
        
        for iteration in range(limit_iterations):
            alpha_idx = random.choices(range(m), weights=p_probs, k=1)[0]
            alpha = A_set[alpha_idx]
            
            S_constructed, q = self._construct_greedy_randomized(
                num_sales, alpha, rho, tau, d_max
            )
            
            if q != num_sales:
                S_constructed = self._adjustment_phase(S_constructed, q, num_sales)
            
            psi_S, _, _ = self._eval_merit_function(S_constructed, num_sales, tau, d_max)
            
            do_local_search = False
            if iteration < 20:
                do_local_search = True
            else:
                threshold = beta * (1 - avg_beta) * psi_S
                if threshold < best_psi:
                    do_local_search = True
            
            if do_local_search:
                S_refined, psi_S_prime = self._post_processing_local_search(
                    num_sales, S_constructed, tau, d_max
                )
                
                if psi_S_prime < best_psi:
                    best_psi = psi_S_prime
                    best_assignment = S_refined.copy()
                
                if psi_S > 0:
                    reduction = max(0, (psi_S - psi_S_prime) / psi_S)
                    sum_beta_reduction += reduction
                    times_ls_called += 1
                    avg_beta = sum_beta_reduction / times_ls_called
                
                sum_A[alpha_idx] += psi_S_prime
                count_A[alpha_idx] += 1
            
            if (iteration + 1) % update_period == 0:
                q_vals = []
                for i in range(m):
                    if count_A[i] > 0:
                        avg_score = sum_A[i] / count_A[i]
                        q_vals.append((1.0 / avg_score) ** delta)
                    else:
                        q_vals.append(0)
                
                total_q = sum(q_vals)
                if total_q > 0:
                    p_probs = [q_val / total_q for q_val in q_vals]
                else:
                    p_probs = [1/m] * m
        
        return best_assignment
    
    # ==========================================
    # PUBLIC METHODS
    # ==========================================
    
    def run_tabu_search(self, initial_assignment: Dict, num_sales: int, 
                       max_iter: int = 100) -> Dict:
        """Chạy thuật toán Tabu Search"""
        return self._tabu_search(initial_assignment, num_sales, max_iter)
    
    def run_grasp(self, num_sales: int, limit_iterations: int = 100) -> Dict:
        """Chạy thuật toán Reactive GRASP"""
        return self._reactive_grasp_filter(num_sales, limit_iterations)

    def _connected_components(self, node_ids: List[int]) -> List[List[int]]:
        remaining = set(node_ids)
        components = []
        while remaining:
            start = next(iter(remaining))
            visited = {start}
            queue = deque([start])
            while queue:
                current = queue.popleft()
                for neighbor in self.adj_list.get(current, []):
                    if neighbor in remaining and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(sorted(visited))
            remaining -= visited
        return components

    def _find_detachable_node(self, cluster_nodes: List[int]) -> int:
        if len(cluster_nodes) <= 1:
            return None
        candidates = sorted(
            cluster_nodes,
            key=lambda node_id: self._get_node_w1(self.nodes[node_id]),
        )
        for node_id in candidates:
            if self._is_connected_without_node(cluster_nodes, node_id):
                return node_id
        return None
    
    def _ensure_complete_assignment(self, assignment: Dict, num_sales: int) -> Dict:
        """Ensure every node is assigned and every sales bucket has at least one node."""
        node_ids = list(self.nodes.keys())
        assignment = {node_id: assignment.get(node_id, -1) for node_id in node_ids}

        for node_id, sales_id in list(assignment.items()):
            if sales_id is None or sales_id < 0 or sales_id >= num_sales:
                assignment[node_id] = 0

        clusters = defaultdict(list)
        for node_id, sales_id in assignment.items():
            clusters[sales_id].append(node_id)

        for sales_id in range(num_sales):
            if clusters.get(sales_id):
                continue
            donor_options = sorted(
                range(num_sales),
                key=lambda sid: len(clusters.get(sid, [])),
                reverse=True,
            )
            moved_node = None
            donor_sales = None
            for candidate_sales in donor_options:
                candidate_node = self._find_detachable_node(clusters.get(candidate_sales, []))
                if candidate_node is not None:
                    moved_node = candidate_node
                    donor_sales = candidate_sales
                    break
            if moved_node is None:
                continue
            clusters[donor_sales].remove(moved_node)
            assignment[moved_node] = sales_id
            clusters[sales_id].append(moved_node)

        for sales_id in range(num_sales):
            components = self._connected_components(clusters.get(sales_id, []))
            if len(components) <= 1:
                continue
            components.sort(key=len, reverse=True)
            keep = set(components[0])
            for component in components[1:]:
                neighbor_sales = {
                    assignment[neighbor]
                    for node_id in component
                    for neighbor in self.adj_list.get(node_id, [])
                    if assignment.get(neighbor) != sales_id
                }
                if not neighbor_sales:
                    continue
                target_sales = min(
                    neighbor_sales,
                    key=lambda sid: sum(
                        self._get_node_w1(self.nodes[n])
                        for n, assigned_sid in assignment.items()
                        if assigned_sid == sid
                    ),
                )
                for node_id in component:
                    assignment[node_id] = target_sales
                    if node_id in clusters[sales_id]:
                        clusters[sales_id].remove(node_id)
                    clusters[target_sales].append(node_id)
            clusters[sales_id] = [node_id for node_id in clusters[sales_id] if node_id in keep]

        return assignment
    
    def solve(self, num_sales: int, algorithm: str = 'grasp', 
             initial_assignment: Dict = None) -> Dict:
        """
        Solve territory design problem using specified algorithm
        
        Args:
            num_sales: Số salesperson
            algorithm: 'tabu_search' hoặc 'grasp'
            initial_assignment: Phân vùng ban đầu (cho tabu_search)
        """
        if algorithm == 'tabu_search':
            if initial_assignment is None:
                raise ValueError("initial_assignment required for tabu_search")
            result = self._tabu_search(initial_assignment, num_sales)
            result = self._ensure_complete_assignment(result, num_sales)
            metrics, total_dist, cv_pct, hoover_idx = self._evaluate_workloads(result, num_sales)
            return {
                'territories': {i: m['nodes'] for i, m in metrics.items()},
                'algorithm': 'tabu_search',
                'metrics': metrics,
                'total_distance': total_dist,
                'cv_pct': cv_pct,
                'hoover_index': hoover_idx
            }
        
        elif algorithm == 'grasp':
            result = self._reactive_grasp_filter(num_sales)
            if result is None:
                return {'error': 'GRASP failed to find solution'}
            result = self._ensure_complete_assignment(result, num_sales)
            metrics, total_dist, cv_pct, hoover_idx = self._evaluate_workloads(result, num_sales)
            return {
                'territories': {i: m['nodes'] for i, m in metrics.items()},
                'algorithm': 'grasp',
                'metrics': metrics,
                'total_distance': total_dist,
                'cv_pct': cv_pct,
                'hoover_index': hoover_idx
            }
        
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
