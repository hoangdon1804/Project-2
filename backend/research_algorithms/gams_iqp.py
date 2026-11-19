"""QMTDP/QCTDP of Salazar-Aguilar et al. (2011) solved with GAMS/DICOPT.

A Python port of the authors' tdpPMedianQC.cpp (ICGP-TDP, Algorithm 1 with
SolveIQP = GAMS/DICOPT). Each iteration writes a complete GAMS model, runs it,
reads the assignment, separates connectivity by BFS (Algorithm 2) and adds
cut (16) for every unconnected component until all territories connect.

Model: binary x(j,k) = z_jq, y(i,k) = y_iq (2np variables), objective (10) or
(19), constraints (11)-(15), cuts (16), neighbor inequality (20) (R1; omit
with --relaxation R). Solver settings follow Section 4 of the paper: DICOPT,
gap <= 5e-6 (optcr), 7200 s for the whole procedure, and branching
priorities (centers y before assignments x, enabled with prioropt). Kept from
the original code: dicopt.opt "maxcycles 50" and accepted model status 1/2/8.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

try:  # project-2 patch: helpers moved to tdp_common.py (exact_milp.py removed); package or script import
    from .tdp_common import (Instance, adjacency, disconnected_components,
                             paper_settings, read_instance, validate_solution)
except ImportError:
    from tdp_common import (Instance, adjacency, disconnected_components,
                            paper_settings, read_instance, validate_solution)

HERE = Path(__file__).resolve().parent
ACCEPTED_MODELSTAT = {1: "OPTIMAL", 2: "LOCALLY_OPTIMAL", 8: "INTEGER_SOLUTION"}


def as_float32(value: float) -> float:
    """tdpPMedianQC.cpp stores coordinates as C float and writes them with %.6f."""
    return struct.unpack("f", struct.pack("f", value))[0]


def find_gams(explicit: str | None) -> str:
    candidates = [explicit, os.environ.get("GAMS"), shutil.which("gams")]
    candidates += sorted((str(p / "gams.exe") for p in Path("C:/GAMS").glob("*")),
                         reverse=True) if Path("C:/GAMS").is_dir() else []
    for candidate in candidates:
        if candidate and Path(candidate).is_file() or (candidate and shutil.which(candidate)):
            return candidate
    raise FileNotFoundError("GAMS executable not found; pass --gams or set GAMS")


def gams_model(instance: Instance, cuts: list[tuple[int, frozenset[int], frozenset[int]]],
               objective: str, relaxation: str, reslim: float, solfile: str,
               optcr: float | None = 5e-6, nlp: str | None = "conopt3") -> str:
    """Return the GAMS source written by MakeGamsFile() for the current cut set."""
    n, p = instance.n, instance.territories
    lines = ["$Title districting",
             "Sets",
             f"  I  'Basic areas (BAs)' / 0*{n - 1} /",
             "  A  'Activities' / customers, demand /",
             "  IC 'Co-ordinates' / cx, cy /",
             f"  K  'Territories' / 1*{p} /",
             "  arc(i,i)",
             "  E(i,i) 'Edge set' /"]
    edges = [f"{u}.{v}" for u, v in instance.edges]
    lines += ["    " + ", ".join(edges[s:s + 12]) + ("," if s + 12 < len(edges) else "")
              for s in range(0, len(edges), 12)]
    lines += ["  /;",
              "Alias (I,J);",
              f"Scalar p 'Number of territories' / {p} /;",
              "Parameter t(a) 'Tolerance for activity a' /",
              f"  customers {instance.tolerances[0]!r}",
              f"  demand    {instance.tolerances[1]!r} /;",
              "Parameter w(i,a) 'Value of activity a in BA i' /"]
    lines += [f"  {j}.customers {w[0]}, {j}.demand {w[1]}" + ("," if j < n - 1 else "")
              for j, w in enumerate(instance.activities)]
    lines += ["/;", "Parameter coor(i,ic) 'X-Y coordinates for basic area i' /"]
    lines += [f"  {j}.cx {as_float32(x):.6f}, {j}.cy {as_float32(y):.6f}" + ("," if j < n - 1 else "")
              for j, (x, y) in enumerate(instance.coordinates)]
    lines += ["/;",
              "Parameter d(i,j) 'Euclidean distance';",
              "d(i,j) = sqrt(sqr(coor(i,'cx')-coor(j,'cx')) + sqr(coor(i,'cy')-coor(j,'cy')));",
              "Parameter m(a) 'Average value of activity a';",
              "m(a) = sum(i, w(i,a))/p;",
              "arc(i,j)$(E(i,j) or E(j,i)) = yes;",
              "Free variables z, zd 'max dispersion objective';",
              "Binary variables",
              "  x(j,k) '=1 if j is assigned to territory k'",
              "  y(i,k) '=1 if i is the center of territory k';",
              "Equations dispersity, max_dispersity, dispersity_one(j), assignment(j),",
              "  location(k), balance_lb1(k), balance_ub1(k), balance_lb2(k),",
              "  balance_ub2(k), arcs(k,j), centers(j,k)"]
    lines += [f"  , Cuts_{c}" for c in range(len(cuts))]
    lines += [";",
              "dispersity..        z =e= sum((i,j,k)$(d(j,i)>0), d(j,i)*x(i,k)*y(j,k));",
              "max_dispersity..    z =e= zd;",
              "dispersity_one(j).. zd =g= sum((k,i), d(j,i)*x(j,k)*y(i,k));",
              "assignment(j)..     sum(k, x(j,k)) =e= 1;",
              "location(k)..       sum(j, y(j,k)) =e= 1;",
              "balance_lb1(k)..    sum(j, w(j,'customers')*x(j,k)) =g= (1-t('customers'))*m('customers');",
              "balance_ub1(k)..    sum(j, w(j,'customers')*x(j,k)) =l= (1+t('customers'))*m('customers');",
              "balance_lb2(k)..    sum(j, w(j,'demand')*x(j,k)) =g= (1-t('demand'))*m('demand');",
              "balance_ub2(k)..    sum(j, w(j,'demand')*x(j,k)) =l= (1+t('demand'))*m('demand');",
              "arcs(k,j)..         sum(i$arc(i,j), x(i,k)) =g= x(j,k);",
              "centers(j,k)..      x(j,k) =g= y(j,k);"]
    for c, (center, component, boundary) in enumerate(cuts):
        # Cut (16) with i = the territory center that S is disconnected from.
        plus = " + ".join(f"x('{v}',k)*y('{center}',k)" for v in sorted(boundary))
        minus = " + ".join(f"x('{v}',k)*y('{center}',k)" for v in sorted(component))
        lines.append(f"Cuts_{c}.. sum(k, {plus or '0'}) - sum(k, {minus}) =g= {1 - len(component)};")
    common = ["assignment", "location", "balance_lb1", "balance_ub1", "balance_lb2",
              "balance_ub2", "centers"] + (["arcs"] if relaxation == "R1" else [])
    common += [f"Cuts_{c}" for c in range(len(cuts))]
    head = ["dispersity"] if objective == "median" else ["max_dispersity", "dispersity_one"]
    lines += [f"Model tdp / {', '.join(head + common)} /;",
              "tdp.OptFile = 1;",
              # Lower value branches first: centers before assignments, as in Section 4.
              "tdp.prioropt = 1;",
              "x.prior(j,k) = 10;",
              "y.prior(i,k) = 1;",
              "option limcol = 0, limrow = 0, solprint = off;",
              # The paper's MIP solver; GAMS 54 otherwise gives DICOPT SCIP as master.
              "option minlp = dicopt, mip = cplex;"]
    # Paper Section 4: gap <= 5e-6. CONOPT3 was the GAMS default NLP in 2010.
    lines += [f"option optcr = {optcr!r};"] if optcr is not None else []
    lines += [f"option nlp = {nlp};"] if nlp else []
    lines += [
              f"option reslim = {max(1, int(reslim))};",
              "Solve tdp using minlp minimizing z;",
              f"file results / '{solfile}' /;",
              "put results;",
              "results.nd = 8;",
              "put tdp.modelstat:2:0 ' ' tdp.solvestat:2:0 ' ' z.l:20:8 ' ' tdp.resusd:12:3 /;",
              "loop((j,k)$(y.l(j,k) > 0.5), put j.tl:0 ' ' k.tl:0 /;);",
              "loop((i,k)$(x.l(i,k) > 0.5), put 'x ' i.tl:0 ' ' k.tl:0 /;);",
              "putclose results;"]
    return "\n".join(lines) + "\n"


def read_solution(path: Path, n: int, p: int):
    if not path.is_file():
        return None
    lines = path.read_text().split("\n")
    fields = lines[0].split()
    modelstat, solvestat, value, resusd = int(fields[0]), int(fields[1]), float(fields[2]), float(fields[3])
    centers: dict[int, int] = {}
    territory: dict[int, int] = {}
    for line in lines[1:]:
        parts = line.split()
        if len(parts) == 2:
            centers[int(parts[1])] = int(parts[0])
        elif len(parts) == 3 and parts[0] == "x":
            territory[int(parts[1])] = int(parts[2])
    return modelstat, solvestat, value, resusd, centers, territory


def gamspy_iteration(instance: Instance, cuts: list[tuple[int, frozenset[int], frozenset[int]]],
                     objective: str, relaxation: str, reslim: float, workdir: Path,
                     iteration: int, optcr: float | None, nlp: str | None,
                     threads: int | None):
    """The model of gams_model() built with the GAMSPy API.

    A GAMSPy academic license refuses plain GAMS programs and put files, so the
    solution is read back from the symbols. Returns read_solution()'s tuple.
    """
    import gamspy as gp

    # GAMSPy rejects working directories with spaces; run in a temp dir instead.
    scratch = Path(tempfile.mkdtemp(prefix="tdp_"))
    try:
        return _gamspy_iteration(gp, scratch, instance, cuts, objective, relaxation, reslim,
                                 workdir, iteration, optcr, nlp, threads)
    finally:
        listing = scratch / "iter.lst"
        if listing.is_file():
            shutil.copyfile(listing, workdir / f"iter{iteration}.lst")
        shutil.rmtree(scratch, ignore_errors=True)


def _gamspy_iteration(gp, scratch: Path, instance: Instance, cuts, objective: str,
                      relaxation: str, reslim: float, workdir: Path, iteration: int,
                      optcr: float | None, nlp: str | None, threads: int | None):
    n, p = instance.n, instance.territories
    m = gp.Container(working_directory=str(scratch))
    i = gp.Set(m, "i", records=[str(v) for v in range(n)], description="Basic areas (BAs)")
    j = gp.Alias(m, "j", i)
    k = gp.Set(m, "k", records=[str(q) for q in range(1, p + 1)], description="Territories")
    a = gp.Set(m, "a", records=["customers", "demand"], description="Activities")
    arc = gp.Set(m, "arc", domain=[i, j],
                 records=[(str(u), str(v)) for e in instance.edges for u, v in (e, e[::-1])])
    coor = [(float(f"{as_float32(cx):.6f}"), float(f"{as_float32(cy):.6f}"))
            for cx, cy in instance.coordinates]
    d = gp.Parameter(m, "d", domain=[i, j], description="Euclidean distance",
                     records=[(str(u), str(v), math.dist(coor[u], coor[v]))
                              for u in range(n) for v in range(n) if u != v])
    w = gp.Parameter(m, "w", domain=[i, a],
                     records=[(str(v), name, instance.activities[v][t])
                              for v in range(n) for t, name in enumerate(("customers", "demand"))])
    t = gp.Parameter(m, "t", domain=a, records=list(zip(("customers", "demand"),
                                                        instance.tolerances)))
    mu = gp.Parameter(m, "mu", domain=a)
    mu[a] = gp.Sum(i, w[i, a]) / p
    x = gp.Variable(m, "x", type="binary", domain=[i, k], description="z_jq: j in territory q")
    y = gp.Variable(m, "y", type="binary", domain=[i, k], description="y_iq: i centers q")
    x.prior[i, k] = 10
    y.prior[i, k] = 1

    equations = []

    def equation(name, domain, definition):
        eq = gp.Equation(m, name, domain=domain)
        eq[tuple(domain)] = definition
        equations.append(eq)

    equation("location", [k], gp.Sum(i, y[i, k]) == 1)                                   # (11)
    equation("assignment", [i], gp.Sum(k, x[i, k]) == 1)                                 # (12)
    equation("centers", [i, k], x[i, k] >= y[i, k])                                      # (13)
    equation("balance_lb", [k, a], gp.Sum(i, w[i, a] * x[i, k]) >= (1 - t[a]) * mu[a])  # (14)
    equation("balance_ub", [k, a], gp.Sum(i, w[i, a] * x[i, k]) <= (1 + t[a]) * mu[a])  # (15)
    if relaxation == "R1":
        equation("arcs", [k, j], gp.Sum(i.where[arc[i, j]], x[i, k]) >= x[j, k])        # (20)
    if cuts:
        # (16): sum_q sum_{v in N(S)\S} z_vq y_cq - sum_q sum_{v in S} z_vq y_cq >= 1-|S|.
        c = gp.Set(m, "c", records=[str(s) for s in range(len(cuts))])
        center = gp.Parameter(m, "center", domain=[c, i],
                              records=[(str(s), str(cut[0]), 1) for s, cut in enumerate(cuts)])
        sign = gp.Parameter(m, "sign", domain=[c, j],
                            records=[(str(s), str(v), coef) for s, (_, comp, bound) in enumerate(cuts)
                                     for part, coef in ((bound, 1), (comp, -1)) for v in sorted(part)])
        rhs = gp.Parameter(m, "rhs", domain=c,
                           records=[(str(s), 1 - len(cut[1])) for s, cut in enumerate(cuts)])
        equation("cuts", [c], gp.Sum(gp.Domain(k, j, i).where[sign[c, j] & center[c, i]],
                                     sign[c, j] * x[j, k] * y[i, k]) >= rhs[c])
    if objective == "median":                                                            # (10)
        z = gp.Sum(gp.Domain(i, j, k).where[d[j, i] > 0], d[j, i] * x[i, k] * y[j, k])
    else:                                                                                # (19)
        z = gp.Variable(m, "zd")
        equation("dispersity_one", [j], z >= gp.Sum((k, i), d[j, i] * x[j, k] * y[i, k]))
    tdp = gp.Model(m, "tdp", equations=equations, problem="MINLP", sense="min", objective=z)
    options = gp.Options(time_limit=max(1, int(reslim)), mip="cplex", nlp=nlp,
                         relative_optimality_gap=optcr, enable_prior=True, threads=threads,
                         listing_file=str(scratch / "iter.lst"),
                         variable_listing_limit=0, equation_listing_limit=0)
    with (workdir / f"iter{iteration}.log").open("w") as log:
        tdp.solve(solver="dicopt", options=options, solver_options=HERE / "dicopt.opt",
                  output=log)
    modelstat, solvestat = int(tdp.status.value), int(tdp.solve_status.value)
    centers: dict[int, int] = {}
    territory: dict[int, int] = {}
    if modelstat in ACCEPTED_MODELSTAT:
        for row in y.records.itertuples():
            if row.level > 0.5:
                centers[int(row.k)] = int(row.i)
        for row in x.records.itertuples():
            if row.level > 0.5:
                territory[int(row.i)] = int(row.k)
    value = tdp.objective_value if tdp.objective_value is not None else math.nan
    resusd = tdp.solve_model_time
    m.close()  # stop the container's GAMS process; it otherwise outlives the call
    return modelstat, solvestat, value, resusd, centers, territory


def solve(instance: Instance, objective: str, relaxation: str, time_limit: float,
          gams: str, workdir: Path, verbose: bool = False,
          optcr: float | None = 5e-6, nlp: str | None = "conopt3",
          threads: int | None = None, backend: str = "gams") -> dict:
    if relaxation == "R1":
        # (20) is valid only if w_j^a < (1 - tau^a) mu^a for all j, a (Section 2.2).
        totals = [sum(w[a] for w in instance.activities) for a in range(2)]
        if not all(w[a] < (1 - instance.tolerances[a]) * totals[a] / instance.territories
                   for w in instance.activities for a in range(2)):
            raise ValueError("inequality (20) needs w_j^a < (1-tau^a)mu^a; use --relaxation R")
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "dicopt.opt").write_text((HERE / "dicopt.opt").read_text())
    neighbors = adjacency(instance)
    n, p = instance.n, instance.territories
    start = time.monotonic()
    cuts: list[tuple[int, frozenset[int], frozenset[int]]] = []
    cut_sizes: list[int] = []
    history = []
    first_connected = None
    iteration = 0
    status = "TIME_LIMIT"
    final = None
    while True:
        remaining = time_limit - (time.monotonic() - start)
        if remaining < 1:
            break
        iteration += 1
        call = time.monotonic()
        if backend == "gamspy":
            from gamspy.exceptions import GamspyException
            try:
                parsed = gamspy_iteration(instance, cuts, objective, relaxation, remaining,
                                          workdir, iteration, optcr, nlp, threads)
            except GamspyException as exc:
                # e.g. return code 7: the model exceeds the license size limit.
                status = f"GAMSPY_ERROR_{getattr(exc, 'return_code', '')}"
                history.append({"iteration": iteration,
                                "seconds": round(time.monotonic() - call, 3),
                                "error": str(exc).splitlines()[0]})
                break
        else:
            gms, sol = workdir / "model.gms", workdir / "solution.txt"
            sol.unlink(missing_ok=True)
            gms.write_text(gams_model(instance, cuts, objective, relaxation, remaining,
                                      sol.name, optcr, nlp))
            proc = subprocess.run([gams, gms.name, "lo=2", f"o=iter{iteration}.lst",
                                   f"lf=iter{iteration}.log", "optdir=."]
                                  + ([f"threads={threads}"] if threads else []),
                                  cwd=workdir, capture_output=True, text=True,
                                  timeout=remaining + 120)
            parsed = read_solution(sol, n, p)
            if parsed is None:
                status = f"GAMS_ERROR_{proc.returncode}"
                history.append({"iteration": iteration,
                                "seconds": round(time.monotonic() - call, 3),
                                "gams_returncode": proc.returncode})
                break
        seconds = time.monotonic() - call
        modelstat, solvestat, value, resusd, center_of, territory = parsed
        record = {"iteration": iteration, "modelstat": modelstat, "solvestat": solvestat,
                  "objective": value, "seconds": round(seconds, 3), "resusd": resusd}
        if modelstat not in ACCEPTED_MODELSTAT or len(center_of) != p or len(territory) != n:
            history.append(record)
            status = "INFEASIBLE" if modelstat in (4, 10, 19) else f"NO_SOLUTION_MODELSTAT_{modelstat}"
            break
        centers = [center_of[k] for k in range(1, p + 1)]
        assignment = [center_of[territory[j]] for j in range(n)]
        components = disconnected_components(assignment, centers, neighbors)
        record["cuts"] = len(components)
        history.append(record)
        if verbose:
            print(f"iter={iteration} modelstat={modelstat} z={value:.4f} "
                  f"t={seconds:.1f}s cuts={len(components)}", file=sys.stderr)
        if first_connected is None:
            first_connected = not components
        if not components:
            final = (assignment, centers, value, ACCEPTED_MODELSTAT[modelstat])
            status = "CONNECTED"
            break
        cuts += components
        cut_sizes += [len(c[1]) for c in components]
    result = {"status": status, "instance": str(instance.path),
              "solver": "GAMSPy/DICOPT" if backend == "gamspy" else "GAMS/DICOPT",
              "model": "QMPTDP" if objective == "median" else "QCPTDP",
              "relaxation": relaxation, "nodes": n, "edges": len(instance.edges),
              "territories": p, "tolerances": list(instance.tolerances),
              "iterations": iteration, "first_iteration_connected": first_connected,
              "connectivity_cuts": len(cut_sizes), "cut_sizes": cut_sizes,
              "elapsed_seconds": round(time.monotonic() - start, 3),
              "time_limit_seconds": time_limit, "optcr": optcr, "nlp": nlp or "default",
              "history": history}
    if final is not None:
        assignment, centers, value, last_modelstat = final
        result["last_modelstat"] = last_modelstat
        result["gams_objective"] = value  # on float32-rounded coordinates
        dist = [math.dist(instance.coordinates[j], instance.coordinates[assignment[j]])
                for j in range(n)]
        exact = sum(dist) if objective == "median" else max(dist)
        if not math.isclose(value, exact, rel_tol=1e-5):
            raise RuntimeError(f"GAMS objective {value} != recomputed {exact}")
        # objective_value is recomputed with the double-precision input coordinates.
        result.update(validate_solution(instance, assignment, centers, objective, exact))
        result.update({"centers": centers, "assignment": assignment})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("instances", nargs="+", type=Path, help=".dat files")
    parser.add_argument("--objective", choices=("median", "center"), default="median")
    parser.add_argument("--relaxation", choices=("R", "R1"), default="R1")
    parser.add_argument("--settings", choices=("source", "paper"), default="paper")
    parser.add_argument("--time-limit", type=float, default=7200)
    parser.add_argument("--gams", help="path to gams.exe")
    parser.add_argument("--results", type=Path, default=HERE / "benchmark_results_gams")
    parser.add_argument("--optcr", type=float, default=5e-6,
                        help="master-MIP relative gap; the paper uses 5e-6")
    parser.add_argument("--nlp", default="conopt3",
                        help="NLP subsolver; CONOPT3 was the GAMS default in 2010")
    parser.add_argument("--modern-defaults", action="store_true",
                        help="use GAMS 54 defaults instead of --optcr/--nlp")
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--jobs", type=int, default=1,
                        help="instances solved in parallel; each GAMS call then uses 1 thread")
    parser.add_argument("--backend", choices=("gams", "gamspy"), default="gams",
                        help="gamspy runs the model through the GAMSPy API (GAMSPy license)")
    args = parser.parse_args()
    args.gams_exe = find_gams(args.gams) if args.backend == "gams" else None
    with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for message in pool.map(run_case, args.instances, [args] * len(args.instances)):
            print(message, flush=True)
    write_summary(args.results)
    return 0


def run_case(path: Path, args: argparse.Namespace) -> str:
    variant = f"{'QMPTDP' if args.objective == 'median' else 'QCPTDP'}_{args.relaxation}"
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
                       args.gams_exe, args.results / "work" / variant / path.stem, args.verbose,
                       None if args.modern_defaults else args.optcr,
                       None if args.modern_defaults else args.nlp,
                       1 if args.jobs > 1 else None, args.backend)
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
                     "last_modelstat": r.get("last_modelstat"),
                     "iterations": r["iterations"],
                     "first_iteration_connected": r["first_iteration_connected"],
                     "connectivity_cuts": r["connectivity_cuts"],
                     "cut_sizes": r["cut_sizes"], "elapsed_seconds": r["elapsed_seconds"]})
    if rows:
        with (results / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
