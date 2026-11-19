"""Instance format and helpers shared by paper_milp.py and gams_iqp.py.

Taken from "D:/territory problem/Code/NASE-Code/exact_milp.py" (instance reader, paper settings,
adjacency, connectivity separation by BFS = Algorithm 2, solution validation) without its OR-Tools
model, which project 2 no longer uses (the MILP is solved by paper_milp.py with CPLEX).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Instance:
    path: Path
    coordinates: tuple[tuple[float, float], ...]
    activities: tuple[tuple[int, int], ...]
    edges: tuple[tuple[int, int], ...]
    territories: int
    tolerances: tuple[float, float]

    @property
    def n(self) -> int:
        return len(self.coordinates)



def read_instance(path: Path) -> Instance:
    """Read the NASE-Code .dat layout (zero-based node IDs)."""
    with path.open(encoding="utf-8-sig") as stream:
        lines = [line.strip() for line in stream if line.strip()]
    position = 0

    def next_fields(expected: int, label: str) -> list[str]:
        nonlocal position
        if position >= len(lines):
            raise ValueError(f"Missing {label}")
        fields = lines[position].split()
        position += 1
        if len(fields) != expected:
            raise ValueError(f"{label}: expected {expected} fields, got {len(fields)}")
        return fields

    n = int(next_fields(1, "node count")[0])
    if n < 1:
        raise ValueError("Node count must be positive")
    coordinates: list[tuple[float, float]] = []
    activities: list[tuple[int, int]] = []
    for j in range(n):
        fields = next_fields(6, f"node {j}")
        node_id = int(fields[0])
        if node_id != j:
            raise ValueError(f"Expected node ID {j}, got {node_id}")
        xy = (float(fields[1]), float(fields[2]))
        if not all(math.isfinite(value) for value in xy):
            raise ValueError(f"Node {j} has a nonfinite coordinate")
        weights = (int(fields[3]), int(fields[4]))
        if any(weight < 0 for weight in weights):
            raise ValueError(f"Node {j} has a negative activity")
        # The third activity is in the input format but not in the 2011 model.
        int(fields[5])
        coordinates.append(xy)
        activities.append(weights)

    edge_count = int(next_fields(1, "edge count")[0])
    if edge_count < 0:
        raise ValueError("Edge count cannot be negative")
    edges: set[tuple[int, int]] = set()
    for e in range(edge_count):
        u, v = (int(value) for value in next_fields(2, f"edge {e}"))
        if not (0 <= u < n and 0 <= v < n) or u == v:
            raise ValueError(f"Invalid edge ({u}, {v})")
        edges.add((min(u, v), max(u, v)))

    fields = next_fields(5, "territory settings")
    territories = int(fields[0])
    int(fields[1])  # Legacy input field, also ignored by the original C++.
    tolerances = (float(fields[2]), float(fields[3]))
    float(fields[4])  # Tolerance for the unused third activity.
    if not 1 <= territories <= n:
        raise ValueError("Territory count must be between 1 and node count")
    if any(not math.isfinite(t) or not 0 <= t <= 1 for t in tolerances):
        raise ValueError("Activity tolerances must be finite and in [0, 1]")
    if position < len(lines) and not lines[position].lower().startswith("semilla:"):
        raise ValueError(f"Unexpected content after territory settings: {lines[position]}")
    return Instance(path, tuple(coordinates), tuple(activities),
                    tuple(sorted(edges)), territories, tolerances)


def paper_settings(instance: Instance) -> Instance:
    """Use the experimental p and tau reported in the paper on project data.

    The (120,7) family is not tabulated in the paper, so its file p is kept.
    """
    p_by_size = {60: 4, 80: 5, 100: 6, 150: 8, 200: 11, 280: 9, 500: 12}
    return replace(instance, territories=p_by_size.get(instance.n, instance.territories),
                   tolerances=(0.05, 0.05))


def adjacency(instance: Instance) -> list[set[int]]:
    neighbors = [set() for _ in range(instance.n)]
    for u, v in instance.edges:
        neighbors[u].add(v)
        neighbors[v].add(u)
    return neighbors


def disconnected_components(assignment: list[int], centers: list[int],
                            neighbors: list[set[int]]) -> list[tuple[int, frozenset[int], frozenset[int]]]:
    """Return (center, disconnected component S, external boundary N(S))."""
    cuts = []
    for center in centers:
        remaining = {j for j, assigned_center in enumerate(assignment)
                     if assigned_center == center}
        while remaining:
            start = next(iter(remaining))
            component = {start}
            remaining.remove(start)
            queue = deque([start])
            while queue:
                for v in neighbors[queue.popleft()]:
                    if v in remaining:
                        remaining.remove(v)
                        component.add(v)
                        queue.append(v)
            if center not in component:
                boundary = set().union(*(neighbors[v] for v in component)) - component
                cuts.append((center, frozenset(component), frozenset(boundary)))
    return cuts


def validate_solution(instance: Instance, assignment: list[int], centers: list[int],
                      objective: str, reported_value: float) -> dict:
    if len(assignment) != instance.n or len(centers) != instance.territories:
        raise RuntimeError("Invalid solution cardinality")
    if len(set(centers)) != len(centers) or any(assignment[i] != i for i in centers):
        raise RuntimeError("Invalid centers")
    if any(i not in centers for i in assignment):
        raise RuntimeError("Assignment references a closed center")
    if disconnected_components(assignment, centers, adjacency(instance)):
        raise RuntimeError("Returned solution contains a disconnected territory")
    mean = [sum(row[a] for row in instance.activities) / instance.territories
            for a in range(2)]
    loads = []
    for i in centers:
        load = [sum(instance.activities[j][a] for j in range(instance.n)
                    if assignment[j] == i) for a in range(2)]
        for a in range(2):
            low = (1 - instance.tolerances[a]) * mean[a]
            high = (1 + instance.tolerances[a]) * mean[a]
            if not low - 1e-5 <= load[a] <= high + 1e-5:
                raise RuntimeError(f"Territory {i} violates activity {a} balance")
        loads.append({"center": i, "nodes": sum(c == i for c in assignment),
                      "activities": load})
    distances = [math.dist(instance.coordinates[j], instance.coordinates[assignment[j]])
                 for j in range(instance.n)]
    value = sum(distances) if objective == "median" else max(distances)
    if not math.isclose(value, reported_value, rel_tol=1e-6, abs_tol=1e-5):
        raise RuntimeError(f"Objective mismatch: solver={reported_value}, recomputed={value}")
    return {"objective_value": value, "territory_loads": loads}
