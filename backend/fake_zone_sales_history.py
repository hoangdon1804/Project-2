"""
Fake sales history for every zone.

Run from project root:
    python backend/fake_zone_sales_history.py
"""

import random
from datetime import datetime, timedelta

import models
from database import SessionLocal, engine
from main import ensure_sqlite_schema


def fake_zone_sales_history(months=6, seed=20260605):
    random.seed(seed)
    models.Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()

    db = SessionLocal()
    try:
        zones = db.query(models.Zone).all()
        if not zones:
            print("No zones found.")
            return

        created = 0
        today = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)

        for zone in zones:
            db.query(models.ZoneActivity).filter(models.ZoneActivity.zone_id == zone.id).delete()

            base_customers = max(zone.num_customers or 0, random.randint(35, 180))
            base_orders = max(zone.num_orders or 0, random.randint(20, 140))
            base_aov = random.randint(120_000, 850_000)

            latest_customers = base_customers
            latest_orders = base_orders
            latest_revenue = float(base_orders * base_aov)

            for month_offset in range(months - 1, -1, -1):
                activity_date = today - timedelta(days=30 * month_offset)
                growth = 1 + ((months - month_offset - 1) * random.uniform(0.015, 0.05))
                customers = max(1, int(base_customers * growth + random.randint(-12, 18)))
                orders = max(1, int(base_orders * growth + random.randint(-10, 20)))
                avg_order_value = max(50_000, base_aov + random.randint(-45_000, 60_000))
                revenue = float(orders * avg_order_value)

                activity = models.ZoneActivity(
                    zone_id=zone.id,
                    num_customers=customers,
                    num_orders=orders,
                    avg_order_value=float(avg_order_value),
                    total_revenue=revenue,
                    notes=f"Fake sales snapshot {activity_date.strftime('%Y-%m')}",
                    updated_at=activity_date,
                )
                db.add(activity)
                created += 1

                latest_customers = customers
                latest_orders = orders
                latest_revenue = revenue

            zone.num_customers = latest_customers
            zone.num_orders = latest_orders
            zone.revenue = latest_revenue

        db.commit()
        print(f"Created {created} sales history rows for {len(zones)} zones.")
    finally:
        db.close()


if __name__ == "__main__":
    fake_zone_sales_history()
