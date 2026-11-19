"""Tests for algorithm_comparison (run from backend/: python -m unittest test_algorithm_comparison)."""
import importlib.util
import random
import unittest

import algorithm_comparison as ac


def grid_problem(rows=5, cols=4, num_sales=3, tolerance=0.3, time_limit=60, seed=7):
    rng = random.Random(seed)
    zones, adj = [], {}
    for r in range(rows):
        for c in range(cols):
            zid = 100 + r * cols + c
            zones.append({"id": zid, "code": f"Z{zid}", "lat": 21.00 + 0.01 * r, "lng": 105.80 + 0.01 * c,
                          "num_customers": rng.randint(50, 150), "num_orders": rng.randint(10, 60), "revenue": 0})
            adj[zid] = [100 + rr * cols + cc for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
                        if 0 <= rr < rows and 0 <= cc < cols]
    return ac.build_problem(zones, adj, num_sales, tolerance, time_limit, seed)


class HelperTests(unittest.TestCase):
    def test_bridges_join_components(self):
        problem = grid_problem()
        problem["adjacency"] = {z["id"]: [] for z in problem["zones"]}  # no adjacency at all
        edges, bridges = ac.bridged_edges(problem)
        self.assertEqual(len(bridges), len(problem["zones"]) - 1)
        self.assertEqual(len(ac._components([z["id"] for z in problem["zones"]],
                                            {u: [v for a, b in edges for v in ((b,) if a == u else (a,) if b == u else ())]
                                             for u in (z["id"] for z in problem["zones"])})), 1)

    def test_complete_territories_assigns_missing_zone_to_neighbour(self):
        problem = grid_problem()
        ids = [z["id"] for z in problem["zones"]]
        territories, repaired = ac.complete_territories(problem, [ids[:7], ids[7:13], ids[13:-1]])
        self.assertEqual(repaired, 1)
        self.assertEqual(sorted(z for t in territories for z in t), sorted(ids))

    def test_evaluate_flags_disconnected_territory(self):
        problem = grid_problem()
        ids = [z["id"] for z in problem["zones"]]
        metrics = ac.evaluate(problem, [[ids[0], ids[-1]], ids[1:10], ids[10:-1]])
        self.assertGreaterEqual(metrics["disconnected_territories"], 1)
        self.assertIn("cv_pct", metrics)

    def test_list_algorithms_has_grasp(self):
        keys = [a["key"] for a in ac.list_algorithms()]
        self.assertIn("grasp", keys)
        self.assertTrue(next(a for a in ac.list_algorithms() if a["key"] == "grasp")["available"])


class SolverTests(unittest.TestCase):
    def check_partition(self, report, problem):
        self.assertTrue(report["ok"], report)
        ids = sorted(z["id"] for z in problem["zones"])
        self.assertEqual(len(report["territories"]), problem["num_sales"])
        self.assertEqual(sorted(z for t in report["territories"] for z in t), ids)
        self.assertIsNotNone(report["metrics"])

    def run_one(self, name, **kw):
        problem = grid_problem(**kw)
        report = ac.compare(problem, [name])[0]
        return problem, report

    def test_grasp(self):
        problem, report = self.run_one("grasp")
        self.check_partition(report, problem)

    @unittest.skipUnless(importlib.util.find_spec("networkx"), "networkx missing")
    def test_probvns(self):
        problem, report = self.run_one("probvns")
        self.check_partition(report, problem)

    @unittest.skipUnless(importlib.util.find_spec("networkx"), "networkx missing")
    def test_probvns_two_sales_small(self):
        problem, report = self.run_one("probvns", rows=2, cols=3, num_sales=2)
        self.check_partition(report, problem)

    @unittest.skipUnless(importlib.util.find_spec("networkx"), "networkx missing")
    def test_probvns_all_metrics_zero_balances_zone_count(self):
        problem = grid_problem()
        for zone in problem["zones"]:
            zone["num_customers"] = zone["num_orders"] = 0
        report = ac.compare(problem, ["probvns"])[0]
        self.check_partition(report, problem)
        self.assertEqual(report["details"]["balanced_attributes"], ["zone_count"])

    @unittest.skipUnless(importlib.util.find_spec("gamspy"), "gamspy missing (MILP uses paper_milp.py / CPLEX)")
    def test_milp_center_connected_and_balanced(self):
        problem, report = self.run_one("milp_center")
        self.assertEqual(report["details"]["solver"], "GAMSPy/CPLEX")
        self.check_partition(report, problem)
        self.assertEqual(report["metrics"]["disconnected_territories"], 0)
        self.assertTrue(report["metrics"]["balanced"])

    @unittest.skipUnless(importlib.util.find_spec("gamspy"), "gamspy missing (MILP uses paper_milp.py / CPLEX)")
    def test_milp_uses_real_adjacency_when_graph_is_split(self):
        problem = grid_problem(rows=2, cols=4, num_sales=2, tolerance=0.9, time_limit=30)
        left = {z["id"] for z in problem["zones"] if (z["id"] - 100) % 4 < 2}
        problem["adjacency"] = {u: [v for v in ns if (u in left) == (v in left)]
                                for u, ns in problem["adjacency"].items()}
        report = ac.compare(problem, ["milp_median"])[0]
        self.assertEqual(report["details"]["adjacency_components"], 2)
        if report["ok"]:  # no bridge edges: a solution must be connected in the app's real adjacency
            self.check_partition(report, problem)
            self.assertEqual(report["metrics"]["disconnected_territories"], 0)
        else:
            self.assertTrue(report["status"] == "TIME_LIMIT" or report["status"].startswith("NO_SOLUTION"))
        problem["num_sales"] = 1
        blocked = ac.compare(problem, ["milp_median"])[0]
        self.assertEqual(blocked["status"], "INFEASIBLE")

    @unittest.skipUnless(importlib.util.find_spec("gamspy"), "gamspy missing (MILP uses paper_milp.py / CPLEX)")
    def test_milp_infeasible_tolerance_reported(self):
        problem, report = self.run_one("milp_median", rows=2, cols=2, num_sales=2, tolerance=0.0001)
        self.assertFalse(report["ok"])
        self.assertTrue(report["status"] in ("INFEASIBLE", "TIME_LIMIT") or report["status"].startswith("NO_SOLUTION"),
                        report["status"])

    @unittest.skipUnless(importlib.util.find_spec("gamspy"), "gamspy missing")
    def test_iqp_center(self):
        problem, report = self.run_one("iqp_center", rows=3, cols=3, num_sales=2, tolerance=0.3)
        if report["status"].startswith("GAMSPY_ERROR"):
            self.skipTest(f"GAMSPy unusable here: {report['message']}")
        self.check_partition(report, problem)

    def test_parallel_compare_keeps_order_and_aligns(self):
        names = ["grasp", "probvns", "milp_center"]
        problem = grid_problem()
        reports = ac.compare(problem, names)
        self.assertEqual([r["algorithm"] for r in reports], names)
        for r in reports:
            if r["ok"]:
                self.check_partition(r, problem)

    def test_unavailable_algorithm(self):
        problem = grid_problem()
        original = ac.ALGORITHMS["grasp"]["modules"]
        ac.ALGORITHMS["grasp"]["modules"] = ("module_that_does_not_exist_xyz",)
        try:
            report = ac.compare(problem, ["grasp"])[0]
        finally:
            ac.ALGORITHMS["grasp"]["modules"] = original
        self.assertEqual(report["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
