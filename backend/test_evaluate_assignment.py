"""Tests for POST /admin/evaluate-assignment (run from backend/: python -m unittest test_evaluate_assignment).
Uses an in-memory SQLite database; app.db is not touched."""
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
import routes
import schemas


def square(lng, lat, size=0.01):
    return {"type": "Polygon", "coordinates": [[
        [lng, lat], [lng + size, lat], [lng + size, lat + size], [lng, lat + size], [lng, lat]]]}


class EvaluateAssignmentTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        models.Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        region = models.Region(name="Ha Noi")
        self.db.add(region)
        self.db.flush()
        territory = models.Territory(name="T", region_id=region.id, zone_ids=[])
        self.db.add(territory)
        self.db.flush()
        # a row of 4 zones: Z0 - Z1 - Z2 - Z3
        self.zones = []
        for i, customers in enumerate((100, 100, 100, 100)):
            zone = models.Zone(zone_code=f"Z{i}", name=f"Zone {i}", geometry=square(105.80 + 0.01 * i, 21.0),
                               center_lat=21.005, center_lng=105.805 + 0.01 * i, territory_id=territory.id,
                               num_customers=customers, num_orders=20)
            self.db.add(zone)
            self.zones.append(zone)
        self.db.flush()
        territory.zone_ids = [z.id for z in self.zones]
        for a, b in zip(self.zones, self.zones[1:]):
            self.db.add(models.ZoneAdjacency(zone_id1=a.id, zone_id2=b.id, is_adjacent=True))
        self.db.commit()
        self.territory = territory
        self.ids = [z.id for z in self.zones]

    def tearDown(self):
        self.db.close()

    def evaluate(self, assignment, tolerance=0.05):
        request = schemas.EvaluateAssignmentRequest(territory_id=self.territory.id, assignment=assignment,
                                                    tolerance=tolerance)
        return routes.evaluate_assignment(request, db=self.db)["metrics"]

    def test_balanced_connected_assignment(self):
        m = self.evaluate({"7": self.ids[:2], "8": self.ids[2:]})
        self.assertEqual(m["cv_pct"], 0)
        self.assertTrue(m["balanced"])
        self.assertEqual(m["disconnected_territories"], 0)
        self.assertEqual(m["per_sales"]["7"]["customers"], 200)
        self.assertEqual(m["unassigned_zones"], [])

    def test_edit_makes_territory_disconnected_and_unbalanced(self):
        m = self.evaluate({"7": [self.ids[0], self.ids[2]], "8": [self.ids[1]], "9": [self.ids[3]]})
        self.assertEqual(m["disconnected_territories"], 1)
        self.assertGreater(m["cv_pct"], 0)
        self.assertFalse(m["balanced"])

    def test_duplicate_or_foreign_zone_rejected(self):
        with self.assertRaises(HTTPException):
            self.evaluate({"7": self.ids, "8": [self.ids[0]]})
        with self.assertRaises(HTTPException):
            self.evaluate({"7": self.ids + [99999]})

    def test_unassigned_zones_reported(self):
        m = self.evaluate({"7": self.ids[:3]})
        self.assertEqual(m["unassigned_zones"], [self.ids[3]])


if __name__ == "__main__":
    unittest.main()
