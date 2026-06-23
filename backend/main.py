from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
from database import engine
from routes import router
import uvicorn
from sqlalchemy import text

models.Base.metadata.create_all(bind=engine)


def ensure_sqlite_schema():
    with engine.begin() as conn:
        territory_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(territories)"))}
        if "parent_territory_id" not in territory_cols:
            conn.execute(text("ALTER TABLE territories ADD COLUMN parent_territory_id INTEGER"))
        if "version_no" not in territory_cols:
            conn.execute(text("ALTER TABLE territories ADD COLUMN version_no INTEGER DEFAULT 1"))

        activity_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(zone_activities)"))}
        activity_additions = {
            "avg_order_value": "FLOAT DEFAULT 0",
            "population_density": "FLOAT",
            "business_density": "FLOAT",
            "traffic_density": "FLOAT",
            "notes": "TEXT",
        }
        for column, column_type in activity_additions.items():
            if column not in activity_cols:
                conn.execute(text(f"ALTER TABLE zone_activities ADD COLUMN {column} {column_type}"))


ensure_sqlite_schema()

app = FastAPI(title="Territory Design System API")

# Sửa allow_origins thành ["*"] để fix triệt để lỗi CORS/Fetch
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    # Đổi host thành 0.0.0.0 để máy tính có thể hiểu cả localhost và 127.0.0.1
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
