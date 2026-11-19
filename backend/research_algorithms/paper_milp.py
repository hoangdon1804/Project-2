"""MTDP/CTDP of Salazar-Aguilar et al. (2011), as written in the paper.

ICGP-TDP (Algorithm 1) with SolveMILP = CPLEX through GAMSPy, following the
paper as closely as possible:

  variables   x(i,j) = 1 if unit j is assigned to the territory centered at i (7)
  MTDP        min sum_{j,i} d_ij x_ij                                          (1)
  CTDP        min max_{i,j} d_ij x_ij, as min z s.t. z >= d_ij x_ij            (8)
  (2)         sum_i x_ii = p
  (3)         sum_i x_ij = 1                                   for all j
  (4), (5)    (1 -/+ tau^a) mu^a x_ii <=/>= sum_j w_j^a x_ij   for all i, a
  (6)         sum_{j in N(S)\\S} x_ij - sum_{j in S} x_ij >= 1-|S|, added as cuts
              for every component S of territory i that misses its center
              (Algorithm 2, BFS)
  (21)        sum_{l in N^j} x_il >= x_ij  for all i, j not in {i} u N^i  (R1 only)

Section 4 settings: CPLEX, relative gap 5e-6, 7200 s for the whole
procedure, branching priority on x_ii before x_ij. Nothing else is added to
the model.

Copied from "D:/territory problem/Code/NASE-Code/paper_milp.py". project-2 patch: the shared helpers
are imported from tdp_common.py (exact_milp.py and its OR-Tools model were removed from project 2).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
import tempfile
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

try:  # project-2 patch: package import, or standalone script next to tdp_common.py
    from .tdp_common import (Instance, adjacency, disconnected_components,
                             paper_settings, read_instance, validate_solution)
except ImportError:
    from tdp_common import (Instance, adjacency, disconnected_components,
                            paper_settings, read_instance, validate_solution)

HERE = Path(__file__).resolve().parent
NORMAL_COMPLETION, RESOURCE_INTERRUPT = 1, 3
INFEASIBLE_MODELSTAT = (4, 10, 19)


class TDPModel:
    """R_MTDP / R1_MTDP / R_CTDP / R1_CTDP in one GAMSPy container; cuts (6) grow."""

    def __init__(self, instance: Instance, objective: str, relaxation: str, workdir: Path):
        import gamspy as gp

        self.gp, self.instance = gp, instance
        n = instance.n
        # GAMSPy rejects working directories with spaces; run in a temp dir instead.
        self.scratch = Path(tempfile.mkdtemp(prefix="milp_"))
        self.workdir = workdir
        m = self.m = gp.Container(working_directory=str(self.scratch))
        nodes = [str(v) for v in range(n)]
        i = gp.Set(m, "i", records=nodes, description="Basic units (V)")
        j = gp.Alias(m, "j", i)
        l = gp.Alias(m, "l", i)
        a = gp.Set(m, "a", records=["customers", "demand"], description="Activities (A)")
        adj = gp.Set(m, "adj", domain=[i, j], description="Edges E, both directions",
                     records=[(str(u), str(v)) for e in instance.edges for u, v in (e, e[::-1])])
        d = gp.Parameter(m, "d", domain=[i, j], description="Euclidean distance d_ij",
                         records=[(str(u), str(v), math.dist(instance.coordinates[u],
                                                             instance.coordinates[v]))
                                  for u in range(n) for v in range(n) if u != v])
        w = gp.Parameter(m, "w", domain=[j, a], description="Activity w_j^a",
                         records=[(str(v), name, instance.activities[v][t]) for v in range(n)
                                  for t, name in enumerate(("customers", "demand"))])
        tau = gp.Parameter(m, "tau", domain=a,
                           records=list(zip(("customers", "demand"), instance.tolerances)))
        mu = gp.Parameter(m, "mu", domain=a, description="Average territory size mu^a")
        mu[a] = gp.Sum(j, w[j, a]) / instance.territories
        x = self.x = gp.Variable(m, "x", type="binary", domain=[i, j],
                                 description="x_ij = 1 if j is assigned to center i")  # (7)
        x.prior[i, j] = 10
        x.prior[i, i] = 1  # Section 4: branch on x_ii before x_ij

        eqs = []

        def equation(name, domain, definition, where=None):
            eq = gp.Equation(m, name, domain=domain)
            key = tuple(domain) if domain else ...
            if where is None:
                eq[key] = definition
            else:
                eq[key].where[where] = definition
            eqs.append(eq)

        equation("centers", [], gp.Sum(i, x[i, i]) == instance.territories)              # (2)
        equation("assign", [j], gp.Sum(i, x[i, j]) == 1)                                 # (3)
        equation("balance_lb", [i, a],
                 gp.Sum(j, w[j, a] * x[i, j]) >= (1 - tau[a]) * mu[a] * x[i, i])          # (4)
        equation("balance_ub", [i, a],
                 gp.Sum(j, w[j, a] * x[i, j]) <= (1 + tau[a]) * mu[a] * x[i, i])          # (5)
        if relaxation == "R1":                                                           # (21)
            equation("neighbor", [i, j], gp.Sum(l.where[adj[j, l]], x[i, l]) >= x[i, j],
                     where=(gp.Ord(i) != gp.Ord(j)) & ~adj[i, j])
        # Connectivity cuts (6); the cut set c starts empty and grows each iteration.
        self.c = gp.Set(m, "c", description="Generated cuts (6)")
        self.center = gp.Parameter(m, "cutcenter", domain=[self.c, i])
        self.sign = gp.Parameter(m, "cutsign", domain=[self.c, j])
        self.rhs = gp.Parameter(m, "cutrhs", domain=self.c)
        c, center, sign, rhs = self.c, self.center, self.sign, self.rhs
        equation("connect", [c], gp.Sum(gp.Domain(i, j).where[center[c, i] & sign[c, j]],
                                        sign[c, j] * x[i, j]) >= rhs[c])
        if objective == "median":
            z = gp.Sum((i, j), d[i, j] * x[i, j])                                        # (1)
        else:
            z = gp.Variable(m, "z", description="max d_ij x_ij")                         # (8)
            equation("radius", [i, j], z >= d[i, j] * x[i, j], where=d[i, j] > 0)
        self.model = gp.Model(m, "tdp", equations=eqs, problem="MIP", sense="min", objective=z)

    def set_cuts(self, cuts: list[tuple[int, frozenset[int], frozenset[int]]]) -> None:
        if not cuts:
            return
        ids = [str(s) for s in range(len(cuts))]
        self.c.setRecords(ids)
        self.center.setRecords([(ids[s], str(cut[0]), 1) for s, cut in enumerate(cuts)])
        self.sign.setRecords([(ids[s], str(v), coef) for s, (_, comp, bound) in enumerate(cuts)
                              for part, coef in ((bound, 1), (comp, -1)) for v in sorted(part)])
        # 1-|S| is 0 for |S| = 1; GAMS stores no zeros, which is the same value.
        self.rhs.setRecords([(ids[s], 1 - len(cut[1])) for s, cut in enumerate(cuts)
                             if len(cut[1]) != 1])

    def solve(self, reslim: float, iteration: int, optcr: float, threads: int | None):
        gp = self.gp
        options = gp.Options(time_limit=max(1, reslim), relative_optimality_gap=optcr,
                             enable_prior=True, threads=threads,
                             listing_file=str(self.scratch / "iter.lst"),
                             variable_listing_limit=0, equation_listing_limit=0)
        with (self.workdir / f"iter{iteration}.log").open("w") as log:
            self.model.solve(solver="cplex", options=options, output=log)
        listing = self.scratch / "iter.lst"
        if listing.is_file():
            shutil.copyfile(listing, self.workdir / f"iter{iteration}.lst")
        model = self.model
        modelstat, solvestat = int(model.status.value), int(model.solve_status.value)
        assignment = centers = None
        if modelstat not in INFEASIBLE_MODELSTAT and self.x.records is not None:
            chosen = self.x.records[self.x.records["level"] > 0.5]
            if len(chosen) == self.instance.n:
                center_of = {int(r.j): int(r.i) for r in chosen.itertuples()}
                assignment = [center_of.get(v, -1) for v in range(self.instance.n)]
                centers = sorted(int(r.i) for r in chosen.itertuples() if r.i == r.j)
        bound = model.objective_estimation  # best bound of the branch and bound
        return modelstat, solvestat, model.objective_value, bound, assignment, centers

    def close(self) -> None:
        """Stop the container's GAMS process; kill it if it does not stop in 60 s."""
        closer = threading.Thread(target=self.m.close, daemon=True)
        closer.start()
        closer.join(60)
        process = getattr(self.m._execution_engine, "_process", None)  # GAMSPy internals
        if closer.is_alive() and process is not None:
            process.kill()
        shutil.rmtree(self.scratch, ignore_errors=True)


def solve(instance: Instance, objective: str, relaxation: str, time_limit: float,
          workdir: Path, optcr: float = 5e-6, threads: int | None = None,
          verbose: bool = False) -> dict:
    """Algorithm 1 (ICGP-TDP) with SolveMILP = CPLEX."""
    workdir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    build_seconds = 0.0
    neighbors = adjacency(instance)
    cuts: list[tuple[int, frozenset[int], frozenset[int]]] = []
    history: list[dict] = []
    first_connected = None
    status, final = "TIME_LIMIT", None
    while True:
        remaining = time_limit - (time.monotonic() - start)
        if remaining < 1:
            break
        iteration = len(history) + 1
        # A fresh container (GAMS process) per iteration: after a solve of about an
        # hour, the next request to the same GAMS process never got an answer.
        built = time.monotonic()
        tdp = TDPModel(instance, objective, relaxation, workdir)
        try:
            tdp.set_cuts(cuts)
            build_seconds += time.monotonic() - built
            remaining = time_limit - (time.monotonic() - start)
            call = time.monotonic()
            modelstat, solvestat, value, bound, assignment, centers = tdp.solve(
                remaining, iteration, optcr, threads)
        finally:
            tdp.close()
        record = {"iteration": iteration, "modelstat": modelstat, "solvestat": solvestat,
                  "objective": value, "bound": bound,
                  "seconds": round(time.monotonic() - call, 3)}
        history.append(record)
        if modelstat in INFEASIBLE_MODELSTAT:
            status = "INFEASIBLE"
            break
        if assignment is None or len(centers) != instance.territories:
            status = "TIME_LIMIT" if solvestat == RESOURCE_INTERRUPT else \
                f"NO_SOLUTION_MODELSTAT_{modelstat}"
            break
        components = disconnected_components(assignment, centers, neighbors)
        record["cuts"] = len(components)
        if first_connected is None:
            first_connected = not components
        if verbose:
            print(f"iter={iteration} modelstat={modelstat} solvestat={solvestat} "
                  f"z={value:.4f} bound={bound} cuts={len(components)}", file=sys.stderr)
        proven = solvestat == NORMAL_COMPLETION  # within the 5e-6 gap of Section 4
        if not components:
            final = (assignment, centers, value)
            status = "OPTIMAL" if proven else "FEASIBLE_TIME_LIMIT"
            break
        if not proven:
            break  # time is up and the incumbent is disconnected
        cuts += components
    result = {"status": status, "instance": str(instance.path),
              "model": "MTDP" if objective == "median" else "CTDP", "relaxation": relaxation,
              "solver": "GAMSPy/CPLEX", "optcr": optcr, "nodes": instance.n,
              "edges": len(instance.edges), "territories": instance.territories,
              "tolerances": list(instance.tolerances), "iterations": len(history),
              "first_iteration_connected": first_connected, "connectivity_cuts": len(cuts),
              "cut_sizes": [len(cut[1]) for cut in cuts],
              "best_lower_bound": history[-1]["bound"] if history else None,
              "build_seconds": round(build_seconds, 3),
              "elapsed_seconds": round(time.monotonic() - start, 3),
              "time_limit_seconds": time_limit, "history": history}
    if final is not None:
        assignment, centers, value = final
        result.update(validate_solution(instance, assignment, centers, objective, value))
        result.update({"centers": centers, "assignment": assignment})
    return result


def run_case(path: Path, args: argparse.Namespace) -> str:
    variant = f"{'MTDP' if args.objective == 'median' else 'CTDP'}_{args.relaxation}"
    out_dir = args.results / variant
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{path.stem}.json"
    if target.exists() and not args.rerun:
        return f"skip {path.name} (exists)"
    instance = read_instance(path)
    if args.settings == "paper":
        instance = paper_settings(instance)
    try:
        result = solve(instance, args.objective, args.relaxation, args.time_limit,
                       args.results / "work" / variant / path.stem, args.optcr,
                       1 if args.jobs > 1 else None, args.verbose)
    except Exception as exc:  # keep the other cases of a batch running
        return f"{path.name}: ERROR {type(exc).__name__}: {exc}"
    result["settings"] = args.settings
    result["jobs"] = args.jobs
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return (f"{path.name}: {result['status']} z={result.get('objective_value')} "
            f"iters={result['iterations']} cuts={result['connectivity_cuts']} "
            f"t={result['elapsed_seconds']}s")


def write_summary(results: Path) -> None:
    rows = []
    for path in sorted(results.glob("*/*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"variant": path.parent.name, "instance": Path(r["instance"]).name,
                     "n": r["nodes"], "p": r["territories"], "status": r["status"],
                     "objective_value": r.get("objective_value"),
                     "best_lower_bound": r["best_lower_bound"], "iterations": r["iterations"],
                     "first_iteration_connected": r["first_iteration_connected"],
                     "connectivity_cuts": r["connectivity_cuts"], "cut_sizes": r["cut_sizes"],
                     "elapsed_seconds": r["elapsed_seconds"]})
    if rows:
        with (results / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("instances", nargs="+", type=Path, help=".dat files")
    parser.add_argument("--objective", choices=("median", "center"), default="median")
    parser.add_argument("--relaxation", choices=("R", "R1"), default="R")
    parser.add_argument("--settings", choices=("source", "paper"), default="paper")
    parser.add_argument("--time-limit", type=float, default=7200,
                        help="seconds for the whole procedure (paper: 7200)")
    parser.add_argument("--optcr", type=float, default=5e-6, help="relative gap (paper: 5e-6)")
    parser.add_argument("--results", type=Path, default=HERE / "benchmark_results_milp_paper")
    parser.add_argument("--jobs", type=int, default=1,
                        help="instances solved in parallel; each CPLEX then uses 1 thread")
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    # cmd.exe and PowerShell pass wildcards through unexpanded.
    args.instances = [match for path in args.instances
                      for match in (sorted(path.parent.glob(path.name)) if "*" in path.name
                                    else [path])]
    with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for message in pool.map(run_case, args.instances, [args] * len(args.instances)):
            print(message, flush=True)
    write_summary(args.results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
