"""Tests for the area-based fake zone metrics (run from backend/: python -m unittest test_fake_zone_metrics).
Uses an in-memory SQLite database; app.db is not touched."""
import math
import random
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
import routes


def square(lng, lat, size_deg):
    return {"type": "Polygon", "coordinates": [[
        [lng, lat], [lng + size_deg, lat], [lng + size_deg, lat + size_deg], [lng, lat + size_deg], [lng, lat],
    ]]}


def expected_km2(lat, size_deg):
    lat0 = lat + size_deg / 2
    return (size_deg * 111.320 * math.cos(math.radians(lat0))) * (size_deg * 110.574)


class FakeZoneMetricsTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        models.Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        region = models.Region(name="Ha Noi")
        self.db.add(region)
        self.db.flush()
        sizes = [0.005, 0.01, 0.02, 0.03]  # square sides in degrees -> areas grow ~ 1 : 4 : 16 : 36
        self.zones = []
        for i, size in enumerate(sizes):
            zone = models.Zone(zone_code=f"Z{i}", name=f"Zone {i}", geometry=square(105.8 + 0.05 * i, 21.0, size),
                               center_lat=21.0, center_lng=105.8 + 0.05 * i)
            self.db.add(zone)
            self.zones.append(zone)
        self.db.add(models.Zone(zone_code="NOGEO", name="No geometry", geometry=None))
        self.db.flush()
        self.nogeo = self.db.query(models.Zone).filter_by(zone_code="NOGEO").one()
        self.territory = models.Territory(name="T", region_id=region.id,
                                          zone_ids=[z.id for z in self.zones] + [self.nogeo.id])
        self.db.add(self.territory)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def run_fake(self, **kw):
        args = {"seed": 1, "customers_per_km2": None, "noise": 0.25}
        args.update(kw)
        return routes.fake_territory_zone_metrics(self.territory.id, db=self.db, **args)

    def test_area_is_computed_and_stored(self):
        self.run_fake()
        for zone, size in zip(self.zones, [0.005, 0.01, 0.02, 0.03]):
            self.db.refresh(zone)
            self.assertAlmostEqual(zone.area_size, expected_km2(21.0, size), delta=expected_km2(21.0, size) * 0.01)

    def test_customers_proportional_to_area_without_noise(self):
        result = self.run_fake(noise=0.0, customers_per_km2=100.0)
        self.assertEqual(result["customers_per_km2"], 100.0)
        for zone in self.zones:
            self.db.refresh(zone)
            self.assertEqual(zone.num_customers, max(routes.FAKE_MIN_CUSTOMERS, round(100.0 * zone.area_size)))
            self.assertGreaterEqual(zone.num_orders, 1)
            self.assertGreater(zone.revenue, 0)

    def test_default_density_gives_median_zone_about_200_customers(self):
        result = self.run_fake(noise=0.0)
        self.assertAlmostEqual(result["customers_per_km2"] * result["median_area_km2"],
                               routes.FAKE_MEDIAN_ZONE_CUSTOMERS, delta=1)

    def test_zone_without_geometry_uses_median_area(self):
        result = self.run_fake(noise=0.0)
        self.assertEqual(result["zones_without_geometry"], [self.nogeo.id])
        self.db.refresh(self.nogeo)
        self.assertIsNone(self.nogeo.area_size)
        self.assertAlmostEqual(self.nogeo.num_customers, routes.FAKE_MEDIAN_ZONE_CUSTOMERS, delta=1)

    def test_larger_zones_get_more_customers_on_average(self):
        self.run_fake(noise=0.25)
        customers = []
        for zone in self.zones:
            self.db.refresh(zone)
            customers.append(zone.num_customers)
        self.assertLess(customers[0], customers[-1])

    def test_same_seed_same_data(self):
        self.run_fake(seed=42)
        first = [(z.num_customers, z.num_orders, z.revenue) for z in self.zones]
        self.run_fake(seed=7)
        self.run_fake(seed=42)
        for z in self.zones:
            self.db.refresh(z)
        self.assertEqual(first, [(z.num_customers, z.num_orders, z.revenue) for z in self.zones])


class FakeHistoryScriptTests(unittest.TestCase):
    """fake_zone_sales_history.fake_history_for_zones on two territories with very different zone sizes."""

    def setUp(self):
        engine = create_engine("sqlite://")
        models.Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        region = models.Region(name="Ha Noi")
        self.db.add(region)
        self.db.flush()
        self.groups = {}
        for t_index, scale in enumerate((0.005, 0.05)):  # small urban wards vs. large rural communes
            territory = models.Territory(name=f"T{t_index}", region_id=region.id, zone_ids=[])
            self.db.add(territory)
            self.db.flush()
            zones = []
            for i, factor in enumerate((1, 2, 4, 6)):
                zone = models.Zone(zone_code=f"T{t_index}Z{i}", name=f"Zone {t_index}-{i}",
                                   geometry=square(105.0 + t_index + 0.3 * i, 21.0, scale * factor),
                                   territory_id=territory.id)
                self.db.add(zone)
                zones.append(zone)
            self.db.flush()
            territory.zone_ids = [z.id for z in zones]
            self.groups[territory.id] = zones
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def run_script(self, months=6, seed=1, noise=0.0, density=None):
        import fake_zone_sales_history as script
        zones = [z for zs in self.groups.values() for z in zs]
        summary = script.fake_history_for_zones(self.db, zones, months, random.Random(seed), noise, density)
        self.db.commit()
        return summary

    def test_history_rows_and_area_written(self):
        summary = self.run_script(months=4)
        self.assertEqual(summary["activities"], 4 * 8)
        self.assertEqual(self.db.query(models.ZoneActivity).count(), 4 * 8)
        for zones in self.groups.values():
            for zone in zones:
                self.db.refresh(zone)
                self.assertGreater(zone.area_size, 0)
                last = (self.db.query(models.ZoneActivity).filter_by(zone_id=zone.id)
                        .order_by(models.ZoneActivity.updated_at.desc()).first())
                self.assertEqual(zone.num_customers, last.num_customers)

    def test_rerun_replaces_history(self):
        self.run_script(months=3)
        self.run_script(months=3)
        self.assertEqual(self.db.query(models.ZoneActivity).count(), 3 * 8)

    def test_customers_grow_with_area_inside_each_territory(self):
        self.run_script()
        for zones in self.groups.values():
            customers = []
            for zone in zones:
                self.db.refresh(zone)
                customers.append(zone.num_customers)
            # areas are 1 : 4 : 16 : 36; growth/noise per month is at most ~ +-30%
            self.assertEqual(customers, sorted(customers))

    def test_density_calibrated_per_territory(self):
        summary = self.run_script()
        densities = list(summary["customers_per_km2"].values())
        self.assertEqual(len(densities), 2)
        self.assertGreater(densities[0], 50 * densities[1])  # 10x smaller sides -> 100x larger density

    def test_fixed_density(self):
        summary = self.run_script(density=80.0)
        self.assertEqual(set(summary["customers_per_km2"].values()), {80.0})

    def test_months_must_be_positive(self):
        with self.assertRaises(ValueError):
            self.run_script(months=0)


if __name__ == "__main__":
    unittest.main()
