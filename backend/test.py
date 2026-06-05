import math
import random
from collections import defaultdict, deque

# ==========================================
# 1. CÁC HÀM TÍNH TOÁN CƠ BẢN & WORKLOAD
# ==========================================

def calculate_distance(node1, node2):
    return math.sqrt((node1['x'] - node2['x'])**2 + (node1['y'] - node2['y'])**2)

def calculate_centroid(nodes, cluster_node_ids): 
    if not cluster_node_ids:
        return {'x': 0, 'y': 0}
    sum_x = sum(nodes[n]['x'] for n in cluster_node_ids)
    sum_y = sum(nodes[n]['y'] for n in cluster_node_ids)
    count = len(cluster_node_ids)
    return {'x': sum_x / count, 'y': sum_y / count}

def get_node_w1(node):
    return node['customers'] * 1.0 + node['orders'] * 0.2

def calculate_score(cv, dist):
    """Hàm đánh giá chung: Phạt nặng nếu CV vượt 15% để ép cân bằng"""
    penalty = 1000000 if cv > 15.0 else 0 
    return (cv * 10000) + dist + penalty

def evaluate_workloads(nodes, assignment, num_sales):
    clusters = defaultdict(list)
    for node_id, sales_id in assignment.items():
        if sales_id != -1:  # Bỏ qua các node chưa gán
            clusters[sales_id].append(node_id)
        
    metrics = {}
    total_distance_all = 0
    
    for sales_id in range(num_sales):
        cluster_nodes = clusters[sales_id]
        if not cluster_nodes:
            metrics[sales_id] = {'nodes': [], 'customers': 0, 'orders': 0, 'distance': 0, 'w1': 0}
            continue
            
        sum_cust = sum(nodes[n]['customers'] for n in cluster_nodes)
        sum_ord = sum(nodes[n]['orders'] for n in cluster_nodes)
        
        centroid = calculate_centroid(nodes, cluster_nodes)
        distance = sum(calculate_distance(centroid, nodes[n]) for n in cluster_nodes)
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
    variance = sum((x - mean_w1)**2 for x in w1_values) / num_sales
    cv_pct = (math.sqrt(variance) / mean_w1 * 100) if mean_w1 > 0 else 0
    hoover_index = (0.5 * sum(abs(x - mean_w1) for x in w1_values) / total_w1 * 100) if total_w1 > 0 else 0
        
    return metrics, total_distance_all, cv_pct, hoover_index

def is_connected_without_node(nodes_in_region, node_to_remove, adj_list):
    """Kiểm tra liên thông bằng BFS với deque để tối ưu tốc độ"""
    remaining_nodes = set(nodes_in_region)
    remaining_nodes.discard(node_to_remove)
        
    if not remaining_nodes:
        return True 
        
    start_node = next(iter(remaining_nodes))
    visited = {start_node}
    queue = deque([start_node])
    
    while queue:
        curr = queue.popleft()
        for neighbor in adj_list[curr]:
            if neighbor in remaining_nodes and neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
                
    return len(visited) == len(remaining_nodes)

# ==========================================
# 2. CÁC THUẬT TOÁN PHÂN VÙNG CƠ BẢN
# ==========================================

def algo_smart_region_growing(nodes, adj_list, num_sales):
    node_ids = list(nodes.keys())
    assignment = {nid: -1 for nid in node_ids}
    
    seeds = [node_ids[0]] 
    while len(seeds) < num_sales:
        candidates = [n for n in node_ids if n not in seeds]
        dists = {n: min(calculate_distance(nodes[n], nodes[s]) for s in seeds) for n in candidates}
        seeds.append(max(dists, key=dists.get))

    workloads = {i: 0 for i in range(num_sales)} 
    frontiers = {i: set(adj_list[s]) for i, s in enumerate(seeds)}
    
    for i, seed in enumerate(seeds):
        assignment[seed] = i
        workloads[i] += get_node_w1(nodes[seed])
        
    unassigned = set(node_ids) - set(seeds)
    
    while unassigned:
        sorted_sales = sorted(range(num_sales), key=lambda x: workloads[x])
        assigned_in_this_turn = False
        
        for sales_id in sorted_sales:
            valid_frontiers = [n for n in frontiers[sales_id] if assignment[n] == -1]
            if valid_frontiers:
                centroid = calculate_centroid(nodes, [n for n, s in assignment.items() if s == sales_id])
                chosen = min(valid_frontiers, key=lambda n: calculate_distance(nodes[n], centroid))
                
                assignment[chosen] = sales_id
                workloads[sales_id] += get_node_w1(nodes[chosen])
                unassigned.remove(chosen)
                frontiers[sales_id].update(adj_list[chosen])
                assigned_in_this_turn = True
                break
                
        if not assigned_in_this_turn and unassigned:
            forced_node = unassigned.pop()
            assignment[forced_node] = sorted_sales[0]
            workloads[sorted_sales[0]] += get_node_w1(nodes[forced_node])
            frontiers[sorted_sales[0]].update(adj_list[forced_node])
            
    return assignment

def algo_local_search(nodes, adj_list, num_sales, initial_assignment, target_cv=15.0):
    assignment = initial_assignment.copy()
    
    for iteration in range(200): 
        metrics, _, current_cv, _ = evaluate_workloads(nodes, assignment, num_sales)
        if current_cv <= target_cv: break
            
        w1_values = {s: m['w1'] for s, m in metrics.items()}
        mean_w1 = sum(w1_values.values()) / num_sales
        sorted_sales = sorted(w1_values.keys(), key=lambda s: w1_values[s], reverse=True)
        moved = False
        
        for heavy_sales in sorted_sales:
            if w1_values[heavy_sales] <= mean_w1: continue 
                
            nodes_in_heavy = [n for n, s in assignment.items() if s == heavy_sales]
                
            for node_id in nodes_in_heavy:
                for neighbor in adj_list[node_id]:
                    light_sales = assignment[neighbor]
                    
                    if light_sales != heavy_sales and w1_values[light_sales] < mean_w1:
                        if not is_connected_without_node(nodes_in_heavy, node_id, adj_list):
                            continue 
                            
                        node_w1 = get_node_w1(nodes[node_id])
                        old_diff = abs(w1_values[heavy_sales] - mean_w1) + abs(w1_values[light_sales] - mean_w1)
                        new_diff = abs((w1_values[heavy_sales] - node_w1) - mean_w1) + abs((w1_values[light_sales] + node_w1) - mean_w1)
                        
                        if new_diff < old_diff:
                            assignment[node_id] = light_sales
                            moved = True
                            break 
                if moved: break
            if moved: break
            
        if not moved: break 
            
    return assignment

def algo_tabu_search(nodes, adj_list, num_sales, initial_assignment, max_iter=100):
    assignment = initial_assignment.copy()
    best_assignment = assignment.copy()
    
    _, best_dist, best_cv, _ = evaluate_workloads(nodes, best_assignment, num_sales)
    best_overall_score = calculate_score(best_cv, best_dist)
    tabu_list = {}
    
    for iteration in range(max_iter):
        best_move = None
        best_move_score = float('inf')
        
        for node_id, current_sales in assignment.items():
            neighbor_sales_set = {assignment[neighbor] for neighbor in adj_list[node_id] if assignment[neighbor] != current_sales}
            if not neighbor_sales_set: continue
                
            nodes_in_current = [n for n, s in assignment.items() if s == current_sales]
            if not is_connected_without_node(nodes_in_current, node_id, adj_list):
                continue
                
            for target_sales in neighbor_sales_set:
                move = (node_id, current_sales, target_sales)
                
                assignment[node_id] = target_sales
                _, new_dist, new_cv, _ = evaluate_workloads(nodes, assignment, num_sales)
                assignment[node_id] = current_sales 
                
                new_score = calculate_score(new_cv, new_dist)
                is_tabu = move in tabu_list and tabu_list[move] > iteration
                
                if not is_tabu or new_score < best_overall_score:
                    if new_score < best_move_score:
                        best_move_score = new_score
                        best_move = move
                        
        if best_move is None: break 
            
        node_id, old_s, new_s = best_move
        assignment[node_id] = new_s
        
        dynamic_tenure = random.randint(5, 10)
        tabu_list[(node_id, new_s, old_s)] = iteration + dynamic_tenure
        
        if best_move_score < best_overall_score:
            best_overall_score = best_move_score
            best_assignment = assignment.copy()
            
    return best_assignment

# ==========================================
# 3. THUẬT TOÁN REACTIVE GRASP VỚI FILTERING
# ==========================================

def get_max_distance(nodes):
    d_max = 0
    node_ids = list(nodes.keys())
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            d = calculate_distance(nodes[node_ids[i]], nodes[node_ids[j]])
            if d > d_max: d_max = d
    return d_max if d_max > 0 else 1

def eval_merit_function(nodes, assignment, num_sales, tau, d_max, lambd=0.5):
    clusters = defaultdict(list)
    for nid, sid in assignment.items():
        if sid != -1: clusters[sid].append(nid)
        
    total_w1 = sum(get_node_w1(nodes[n]) for n in nodes)
    mu = total_w1 / num_sales if num_sales > 0 else 1
    
    max_dispersion = 0
    for sid, cluster in clusters.items():
        if not cluster: continue
        centroid = calculate_centroid(nodes, cluster)
        max_dist_in_cluster = max([calculate_distance(centroid, nodes[n]) for n in cluster] + [0])
        if max_dist_in_cluster > max_dispersion:
            max_dispersion = max_dist_in_cluster
    F_S = max_dispersion / d_max
    
    G_S = 0
    for sid in range(num_sales):
        cluster = clusters.get(sid, [])
        w_cluster = sum(get_node_w1(nodes[n]) for n in cluster)
        violation = max(w_cluster - (1 + tau)*mu, (1 - tau)*mu - w_cluster, 0)
        G_S += violation / mu
        
    psi_S = lambd * F_S + (1 - lambd) * G_S
    return psi_S, F_S, G_S

def construct_greedy_randomized(nodes, adj_list, num_sales, alpha, rho, tau, d_max, lambd=0.5):
    node_ids = list(nodes.keys())
    unassigned = set(node_ids)
    assignment = {nid: -1 for nid in node_ids}
    
    degrees = {n: len(adj_list[n]) for n in node_ids}
    start_node = min(degrees, key=degrees.get)
    
    q = 0 
    territories = defaultdict(list)
    territories[q].append(start_node)
    assignment[start_node] = q
    unassigned.remove(start_node)
    
    total_w1 = sum(get_node_w1(nodes[n]) for n in nodes)
    mu = total_w1 / num_sales
    
    while unassigned:
        neighbors = set()
        for n in territories[q]:
            neighbors.update(adj_list[n])
        valid_neighbors = list(neighbors.intersection(unassigned))
        
        current_w1 = sum(get_node_w1(nodes[n]) for n in territories[q])
        if not valid_neighbors or current_w1 > rho * (1 + tau) * mu:
            q += 1
            next_start = min((n for n in unassigned), key=lambda x: degrees[x])
            territories[q].append(next_start)
            assignment[next_start] = q
            unassigned.remove(next_start)
            continue
            
        phi_values = {}
        centroid = calculate_centroid(nodes, territories[q])
        f_Vk = max([calculate_distance(centroid, nodes[n]) for n in territories[q]] + [0])
        
        for v in valid_neighbors:
            d_v = calculate_distance(centroid, nodes[v])
            F_k_v = max(f_Vk, d_v) / d_max
            w_new = current_w1 + get_node_w1(nodes[v])
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

def adjustment_phase(nodes, adj_list, assignment, q, num_sales):
    if q <= num_sales: return assignment
    
    current_q = q
    while current_q > num_sales:
        w_sizes = {sid: sum(get_node_w1(nodes[n]) for n, s in assignment.items() if s == sid) for sid in range(current_q)}
        smallest_sid = min(w_sizes, key=w_sizes.get)
        
        neighbor_sids = set()
        for nid, sid in assignment.items():
            if sid == smallest_sid:
                for neighbor in adj_list[nid]:
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

def post_processing_local_search(nodes, adj_list, num_sales, initial_assignment, tau, d_max, limit_moves=100):
    assignment = initial_assignment.copy()
    current_psi, _, _ = eval_merit_function(nodes, assignment, num_sales, tau, d_max)
    
    moves = 0
    while moves < limit_moves:
        moved = False
        node_ids = list(assignment.keys())
        random.shuffle(node_ids) 
        
        for i in node_ids:
            current_s = assignment[i]
            neighbor_sids = {assignment[j] for j in adj_list[i] if assignment[j] != current_s}
            if not neighbor_sids: continue
                
            nodes_in_current = [n for n, s in assignment.items() if s == current_s]
            if not is_connected_without_node(nodes_in_current, i, adj_list):
                continue
                
            for j_s in neighbor_sids:
                assignment[i] = j_s
                new_psi, _, _ = eval_merit_function(nodes, assignment, num_sales, tau, d_max)
                
                if new_psi < current_psi:
                    current_psi = new_psi
                    moved = True
                    break 
                else:
                    assignment[i] = current_s 
            if moved: break
            
        if not moved: break
        moves += 1
        
    return assignment, current_psi

def algo_reactive_grasp_filter(nodes, adj_list, num_sales, limit_iterations=100, update_period=20):
    d_max = get_max_distance(nodes)
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
        
        S_constructed, q = construct_greedy_randomized(nodes, adj_list, num_sales, alpha, rho, tau, d_max)
        
        if q != num_sales:
            S_constructed = adjustment_phase(nodes, adj_list, S_constructed, q, num_sales)
            
        psi_S, _, _ = eval_merit_function(nodes, S_constructed, num_sales, tau, d_max)
        
        do_local_search = False
        if iteration < 20: 
            do_local_search = True
        else:
            threshold = beta * (1 - avg_beta) * psi_S
            if threshold < best_psi:
                do_local_search = True
                
        if do_local_search:
            S_refined, psi_S_prime = post_processing_local_search(nodes, adj_list, num_sales, S_constructed, tau, d_max)
            
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
# 4. HỆ THỐNG PARSER VÀ IN BÁO CÁO
# ==========================================

def parse_input_and_run(input_text):
    lines = [line.strip() for line in input_text.strip().split('\n') if line.strip()]
    n = int(lines[0])
    nodes = {}
    idx = 1
    for _ in range(n):
        parts = list(map(float, lines[idx].split()))
        nodes[int(parts[0])] = {'x': parts[1], 'y': parts[2], 'customers': parts[3], 'orders': parts[4]}
        idx += 1
        
    m = int(lines[idx])
    idx += 1
    adj_list = defaultdict(set)
    for _ in range(m):
        u, v = map(int, lines[idx].split())
        adj_list[u].add(v)
        adj_list[v].add(u)
        idx += 1
        
    num_sales = int(lines[idx])
    
    print("="*85)
    print(f"KẾT QUẢ PHÂN VÙNG (SỐ LƯỢNG SALES: {num_sales} | TỔNG SỐ NÚT: {n})")
    print("="*85)
    
    assignment_rg = algo_smart_region_growing(nodes, adj_list, num_sales)
    assignment_ls = algo_local_search(nodes, adj_list, num_sales, assignment_rg, target_cv=15.0)
    
    print("Đang chạy thuật toán REACTIVE GRASP VỚI FILTERING (100 vòng lặp)... Vui lòng đợi...\n")
    assignment_rgrasp = algo_reactive_grasp_filter(nodes, adj_list, num_sales, limit_iterations=100, update_period=20)
    
    print("Đang chạy thuật toán TABU SEARCH... Vui lòng đợi...\n")
    assignment_tabu = algo_tabu_search(nodes, adj_list, num_sales, assignment_ls, max_iter=100)
    
    algorithms = [
        ("SMART REGION GROWING", assignment_rg),
        ("LOCAL SEARCH", assignment_ls),
        ("TABU SEARCH", assignment_tabu),
        ("REACTIVE GRASP VỚI FILTERING", assignment_rgrasp)
    ]
    
    best_algo_w1 = ("", float('inf'))
    
    for algo_name, assignment in algorithms:
        if assignment is None: continue
        metrics, total_dist, cv_pct, hoover_idx = evaluate_workloads(nodes, assignment, num_sales)
        
        print(f"--- THUẬT TOÁN: {algo_name} ---")
        print(f"* TỔNG QUÃNG ĐƯỜNG: {round(total_dist, 2)} đơn vị")
        status = "CÂN BẰNG TỐT" if cv_pct <= 15 else "CHƯA CÂN BẰNG"
        print(f"* HỆ SỐ BIẾN THIÊN (CV): {round(cv_pct, 2)}% ({status})")
        print(f"* CHỈ SỐ HOOVER: {round(hoover_idx, 2)}%")
        
        for sid, m_data in metrics.items():
            print(f"   [Sales {sid+1}] Distance: {m_data['distance']:>7.2f} | Workload: {m_data['w1']:>6.2f}")
            
        if cv_pct < best_algo_w1[1]: 
            best_algo_w1 = (algo_name, cv_pct)
        print()

    print("="*85)
    if best_algo_w1[0]:
        print(f"🏆 Cân bằng tốt nhất: {best_algo_w1[0]} ({round(best_algo_w1[1], 2)}%)")

if __name__ == "__main__":
    file_path = "D:\\project 2\\backend\\input\\input3.dat" 
    try:
        with open(file_path, "r") as file:
            parse_input_and_run(file.read())
    except Exception as e:
        print(f"LỖI: {e}")