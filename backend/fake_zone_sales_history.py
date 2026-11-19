"""
Fake sales history for every zone, based on zone area.

For each zone, a base number of customers is drawn from its area (see fake_metrics.py):
    base customers = density x area_km2 x LogNormal(0, noise)
where the density is calibrated per territory so that a zone of median area gets about
fake_metrics.MEDIAN_ZONE_CUSTOMERS customers (or fixed with --customers-per-km2).
Then `months` monthly snapshots (ZoneActivity) are written with a small growth trend and
relative noise; the last snapshot becomes the zone's current num_customers / num_orders / revenue.
The zone area (km²) is stored in zone.area_size.

Run from project root:
    python backend/fake_zone_sales_history.py
    python backend/fake_zone_sales_history.py --seed 1 --months 12 --customers-per-km2 80
"""

import argparse
import random
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional

import fake_metrics
import models

NO_TERRITORY = "no-territory"


def zone_groups(db, zones) -> Dict[object, list]:
    """Group zones by territory (zone.territory_id, else the first territory listing it in zone_ids)."""
    listed_in = {}
    for territory in db.query(models.Territory).order_by(models.Territory.id).all():
        for zone_id in territory.zone_ids or []:
            listed_in.setdefault(int(zone_id), territory.id)
    groups = defaultdict(list)
    for zone in zones:
        groups[zone.territory_id or listed_in.get(zone.id, NO_TERRITORY)].append(zone)
    return groups


def fake_history_for_zones(db, zones, months: int = 6, rng: Optional[random.Random] = None,
                           noise: float = fake_metrics.DEFAULT_NOISE,
                           customers_per_km2: Optional[float] = None,
                           today: Optional[datetime] = None) -> Dict:
    """Write area-based fake history for `zones` (no commit). Returns a summary."""
    if months < 1:
        raise ValueError("months must be >= 1")
    rng = rng or random.Random()
    today = today or datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
    areas = {zone.id: fake_metrics.area_km2(zone.geometry) for zone in zones}
    created = 0
    densities = {}
    missing_geometry = []

    for group, group_zones in zone_groups(db, zones).items():
        try:
            density, median_area = fake_metrics.density_for((areas[z.id] for z in group_zones), customers_per_km2)
        except ValueError:  # no geometry in the whole group: fall back to the median area of all zones
            density, median_area = fake_metrics.density_for(areas.values(), customers_per_km2)
        densities[group] = round(density, 2)

        for zone in group_zones:
            area = areas[zone.id]
            if area:
                zone.area_size = round(area, 4)
            else:
                missing_geometry.append(zone.id)
                area = median_area
            db.query(models.ZoneActivity).filter(models.ZoneActivity.zone_id == zone.id).delete()

            base_customers = fake_metrics.fake_customers(rng, area, density, noise)
            base_orders = fake_metrics.fake_orders(rng, base_customers)
            base_aov = rng.randint(120_000, 850_000)

            for month_offset in range(months - 1, -1, -1):
                activity_date = today - timedelta(days=30 * month_offset)
                growth = 1 + ((months - month_offset - 1) * rng.uniform(0.015, 0.05))
                # relative noise keeps the numbers proportional to the zone area
                customers = max(1, round(base_customers * growth * rng.uniform(0.93, 1.07)))
                orders = max(1, round(base_orders * growth * rng.uniform(0.9, 1.1)))
                avg_order_value = max(50_000, base_aov + rng.randint(-45_000, 60_000))
                revenue = float(orders * avg_order_value)

                db.add(models.ZoneActivity(
                    zone_id=zone.id,
                    num_customers=customers,
                    num_orders=orders,
                    avg_order_value=float(avg_order_value),
                    total_revenue=revenue,
                    notes=f"Fake sales snapshot {activity_date.strftime('%Y-%m')} (by area)",
                    updated_at=activity_date,
                ))
                created += 1

            zone.num_customers = customers
            zone.num_orders = orders
            zone.revenue = revenue

    return {"zones": len(zones), "activities": created, "customers_per_km2": densities,
            "zones_without_geometry": missing_geometry}


def fake_zone_sales_history(months=6, seed=20260605, noise=fake_metrics.DEFAULT_NOISE, customers_per_km2=None):
    from database import SessionLocal, engine
    from main import ensure_sqlite_schema

    models.Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()

    db = SessionLocal()
    try:
        zones = db.query(models.Zone).all()
        if not zones:
            print("No zones found.")
            return
        summary = fake_history_for_zones(db, zones, months, random.Random(seed), noise, customers_per_km2)
        db.commit()
        print(f"Created {summary['activities']} sales history rows for {summary['zones']} zones (seed {seed}).")
        print("Density (customers/km2) per territory:", summary["customers_per_km2"])
        if summary["zones_without_geometry"]:
            print(f"{len(summary['zones_without_geometry'])} zones without geometry used the median area.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260605)
    parser.add_argument("--noise", type=float, default=fake_metrics.DEFAULT_NOISE,
                        help="std. deviation of the log-normal noise around density x area")
    parser.add_argument("--customers-per-km2", type=float, default=None,
                        help="fixed density instead of the per-territory calibration")
    args = parser.parse_args()
    fake_zone_sales_history(args.months, args.seed, args.noise, args.customers_per_km2)
