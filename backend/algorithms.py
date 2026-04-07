"""
Commercial Territory Design Algorithms
- K-means Clustering: Dựa trên vị trí địa lý
- Greedy Seed Growth: Cân bằng tải
- Local Search: Điều chỉnh tối ưu
"""

import math
import random
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict
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


class KMeansClustering(TerritoryAlgorithm):
    """K-means Clustering based on geographical location"""
    
    def solve(self, num_clusters: int, max_iterations: int = 100) -> Dict:
        """
        K-means clustering dựa trên vị trí địa lý
        
        Args:
            num_clusters: Số phân vùng cần tạo
            max_iterations: Số lần lặp tối đa
        """
        start_time = time.time()
        self.territories = defaultdict(list)
        
        if not self.zones or num_clusters <= 0:
            return {
                'territories': {},
                'algorithm': 'kmeans',
                'execution_time': 0,
                'quality_score': 0,
                'message': 'Invalid input'
            }
        
        # Khởi tạo centroids ngẫu nhiên
        centroids = {}
        initial_zones = random.sample(self.zones, min(num_clusters, len(self.zones)))
        for i, zone in enumerate(initial_zones):
            centroids[i] = (zone.lat, zone.lng)
        
        num_clusters = len(initial_zones)
        
        # K-means iterations
        for iteration in range(max_iterations):
            old_centroids = centroids.copy()
            new_territories = defaultdict(list)
            
            # Assign zones to nearest centroid
            for zone in self.zones:
                min_distance = float('inf')
                nearest_cluster = 0
                
                for cluster_id, (c_lat, c_lng) in centroids.items():
                    distance = self._haversine_distance(
                        zone.lat, zone.lng, c_lat, c_lng
                    )
                    if distance < min_distance:
                        min_distance = distance
                        nearest_cluster = cluster_id
                
                new_territories[nearest_cluster].append(zone.id)
            
            # Update centroids
            for cluster_id, zone_ids in new_territories.items():
                if zone_ids:
                    avg_lat = sum(self.zone_map[zid].lat for zid in zone_ids) / len(zone_ids)
                    avg_lng = sum(self.zone_map[zid].lng for zid in zone_ids) / len(zone_ids)
                    centroids[cluster_id] = (avg_lat, avg_lng)
            
            self.territories = new_territories
            
            # Check convergence
            converged = all(
                self._haversine_distance(old_centroids[i][0], old_centroids[i][1],
                                        centroids[i][0], centroids[i][1]) < 0.1
                for i in old_centroids if i in centroids
            )
            if converged:
                break
        
        self.execution_time = time.time() - start_time
        metrics = self._evaluate_solution()
        self.quality_score = metrics['overall_score']
        
        return {
            'territories': dict(self.territories),
            'algorithm': 'kmeans',
            'execution_time': self.execution_time,
            'quality_score': self.quality_score,
            'iterations': iteration + 1,
            'message': f'KMeans clustering completed in {iteration + 1} iterations'
        }


class GreedySeedGrowth(TerritoryAlgorithm):
    """Greedy Seed Growth - Load balancing approach"""
    
    def solve(self, num_territories: int, 
              max_zones_per_territory: int = 50) -> Dict:
        """
        Thuật toán Greedy Seed Growth cân bằng tải
        
        Args:
            num_territories: Số phân vùng cần tạo
            max_zones_per_territory: Số zones tối đa trong một phân vùng
        """
        start_time = time.time()
        self.territories = defaultdict(list)
        
        if not self.zones or num_territories <= 0:
            return {
                'territories': {},
                'algorithm': 'greedy',
                'execution_time': 0,
                'quality_score': 0,
                'message': 'Invalid input'
            }
        
        # Tính workload cho mỗi zone
        for zone in self.zones:
            zone.workload = self._calculate_workload(zone)
        
        # Sắp xếp zones theo workload (descending)
        sorted_zones = sorted(self.zones, key=lambda z: z.workload, reverse=True)
        
        # Chọn seed: zones có workload cao nhất
        seeds = sorted_zones[:num_territories]
        seed_ids = {i: seed.id for i, seed in enumerate(seeds)}
        
        # Khởi tạo territories với seed zones
        for territory_id, seed in enumerate(seeds):
            self.territories[territory_id] = [seed.id]
        
        # Bộ zones chưa được gán
        unassigned = set(z.id for z in sorted_zones[num_territories:])
        
        # Greedy growth: thêm zones liền kề với workload cân bằng
        while unassigned:
            # Tìm zone chưa gán có workload cao nhất
            best_zone = None
            best_workload = -1
            
            for zone_id in unassigned:
                zone = self.zone_map[zone_id]
                if zone.workload > best_workload:
                    best_workload = zone.workload
                    best_zone = zone_id
            
            if best_zone is None:
                break
            
            # Gán zone này cho phân vùng có tải thấp nhất
            min_workload_territory = min(
                self.territories.keys(),
                key=lambda tid: sum(
                    self._calculate_workload(self.zone_map[zid])
                    for zid in self.territories[tid]
                    if len(self.territories[tid]) < max_zones_per_territory
                )
            )
            
            self.territories[min_workload_territory].append(best_zone)
            unassigned.remove(best_zone)
        
        # Gán các zones còn lại
        for zone_id in unassigned:
            min_workload_territory = min(
                self.territories.keys(),
                key=lambda tid: sum(
                    self._calculate_workload(self.zone_map[zid])
                    for zid in self.territories[tid]
                )
            )
            self.territories[min_workload_territory].append(zone_id)
        
        self.execution_time = time.time() - start_time
        metrics = self._evaluate_solution()
        self.quality_score = metrics['overall_score']
        
        return {
            'territories': dict(self.territories),
            'algorithm': 'greedy',
            'execution_time': self.execution_time,
            'quality_score': self.quality_score,
            'message': 'Greedy Seed Growth completed'
        }


class LocalSearch(TerritoryAlgorithm):
    """Local Search - Optimize existing territories"""
    
    def solve(self, initial_territories: Dict[int, List[int]], 
              swap_iterations: int = 10) -> Dict:
        """
        Local Search - Điều chỉnh tối ưu các phân vùng hiện tại
        
        Args:
            initial_territories: Các phân vùng hiện tại {territory_id: [zone_ids]}
            swap_iterations: Số lần thử swap
        """
        start_time = time.time()
        self.territories = {k: list(v) for k, v in initial_territories.items()}
        
        # Tính workload
        for zone in self.zones:
            zone.workload = self._calculate_workload(zone)
        
        improved = True
        iteration = 0
        
        while improved and iteration < swap_iterations:
            improved = False
            iteration += 1
            
            # Thử swap zones giữa các territories
            territory_ids = list(self.territories.keys())
            
            for i in range(len(territory_ids)):
                for j in range(i + 1, len(territory_ids)):
                    tid1, tid2 = territory_ids[i], territory_ids[j]
                    
                    if not self.territories[tid1] or not self.territories[tid2]:
                        continue
                    
                    # Tính hiện tại workload
                    current_score = self._quality_of_partition(tid1, tid2)
                    
                    # Thử swap từng zone từ tid1 sang tid2
                    for zone_id in self.territories[tid1][:]:
                        self.territories[tid1].remove(zone_id)
                        self.territories[tid2].append(zone_id)
                        
                        new_score = self._quality_of_partition(tid1, tid2)
                        
                        if new_score > current_score:
                            # Swap tốt hơn, giữ lại
                            improved = True
                            break
                        else:
                            # Swap không tốt, hoàn tác
                            self.territories[tid2].remove(zone_id)
                            self.territories[tid1].append(zone_id)
                    
                    if improved:
                        break
                
                if improved:
                    break
        
        self.execution_time = time.time() - start_time
        metrics = self._evaluate_solution()
        self.quality_score = metrics['overall_score']
        
        return {
            'territories': dict(self.territories),
            'algorithm': 'localsearch',
            'execution_time': self.execution_time,
            'quality_score': self.quality_score,
            'iterations': iteration,
            'message': f'Local Search completed in {iteration} iterations'
        }
    
    def _quality_of_partition(self, tid1: int, tid2: int) -> float:
        """Tính chất lượng của một cặp phân vùng"""
        workload1 = sum(
            self._calculate_workload(self.zone_map[zid])
            for zid in self.territories[tid1]
        )
        workload2 = sum(
            self._calculate_workload(self.zone_map[zid])
            for zid in self.territories[tid2]
        )
        
        # Chất lượng = 100 / (1 + |workload1 - workload2|)
        return 100 / (1 + abs(workload1 - workload2))

class AdvancedTerritoryDesign(TerritoryAlgorithm):
    def __init__(self, zones, adj_list, num_sales):
        # Chuyển đổi dữ liệu từ DB sang format của test.py
        self.nodes = {
            z['id']: {
                'x': z['lng'], # lng tương ứng x
                'y': z['lat'], # lat tương ứng y
                'customers': z['num_customers'],
                'orders': z['num_orders']
            } for z in zones
        }
        self.adj_list = adj_list # Dict {id: [neighbor_ids]}
        self.num_sales = num_sales

    # Copy các hàm hỗ trợ từ test.py vào đây: 
    # is_connected_without_node, evaluate_workloads, calculate_centroid, v.v.
    
    def run_local_search(self, initial_assignment):
        # Logic algo_local_search từ test.py
        pass

    def run_tabu_search(self, initial_assignment):
        # Logic algo_tabu_search từ test.py
        pass

    def run_grasp(self):
        # Logic algo_reactive_grasp_filter từ test.py
        pass