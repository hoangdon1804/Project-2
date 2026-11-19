# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Territory Design System: a web app that manages sales regions, groups map zones (wards/communes) into territories, and runs an algorithm that splits a territory's zones among sales staff for each day. The stack is a FastAPI + SQLAlchemy + SQLite backend, a React (CRA) web frontend, and a .NET MAUI mobile app for the sales role. UI strings and many code comments are in Vietnamese.

## Commands

Backend (run from `backend/`, since modules import each other by bare name, e.g. `import models`):

```bash
pip install -r requirements.txt                              # from repo root, inside .venv
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000  # Swagger at /docs
python create_test_accounts.py                               # admin1/Admin123!, sales1/Sales123!
python -m unittest test_external_services                    # all backend tests
python -m unittest test_external_services.WardImportTests.test_city_aliases  # single test
```

Web frontend (`frontend/`):

```bash
npm install && npm start      # http://localhost:3000
npm run build
npm test                      # react-scripts / jest
```

The backend URL comes from `REACT_APP_API_BASE` (default `http://127.0.0.1:8000`, see `frontend/src/api.js`).

Mobile app (`frontend-mobileApp/`, sales only): `dotnet build -f net10.0-windows10.0.19041.0`, `dotnet build -f net10.0-android`, `dotnet test`. Backend URLs are set in `Resources/Raw/backend-settings.json`. The Android emulator reaches the host at `10.0.2.2:8000`.

## Architecture

### Backend (`backend/`)

- `main.py` creates the tables with `create_all`, then runs `ensure_sqlite_schema()`. That function is a hand-written migration that `ALTER TABLE`s missing columns into an existing DB. There is no Alembic, so new columns on existing tables must be added there as well.
- `database.py` always points at `app.db` in the **repo root**, not in `backend/`, whatever the working directory.
- `routes.py` is one large `APIRouter` holding every endpoint. `schemas.py` holds the Pydantic models.
- **Auth:** `/login` issues a JWT (`auth.py`, hard-coded secret). No route verifies it, so endpoints are not protected server-side and role checks happen in the frontend.
- `external_services.py` imports ward/commune boundaries from OpenStreetMap through the Overpass API, using a historical snapshot date and only Hà Nội or TP.HCM. It assembles polygons from relation members with Shapely. It raises `WardImportError` instead of importing partial data. `test_external_services.py` mocks the network calls.

### Domain model (`models.py`)

- `Region` → `User` (role `admin`/`sales`; a sales account must be approved through `is_approved`).
- `Zone` holds a GeoJSON `geometry`, a center lat/lng and activity metrics (`num_customers`, `num_orders`, `revenue`). `ZoneActivity` records the metric history.
- `Territory` stores its zones as a JSON list `zone_ids`, not as a foreign key. Versions are territories that are cloned with `parent_territory_id` and `version_no` set (`POST /territories/{id}/versions`).
- `ZoneAdjacency` is derived data. `_rebuild_zone_adjacency` in `routes.py` recomputes it from geometry intersections (Shapely `STRtree`) every time work is assigned, or on `POST /territories/{id}/rebuild-adjacency`.
- `WorkAssignment` stores, per territory and date, `assignment_data = {sales_id: [zone_ids]}`, the algorithm used, the quality metrics (CV %, total distance, Hoover index) and `is_finalized`.

### Assignment flow

1. `POST /admin/assign-work` validates that the chosen sales belong to the territory's region and are free that day.
2. It then rebuilds adjacency, builds `zones_data` and `adj_list`, and calls `AdvancedTerritoryDesign(zones_data, adj_list).solve(num_sales, algorithm)`.
3. The result maps territory index `i` to `sales_ids[i]`. Zones that end up unassigned are distributed afterwards.
4. The admin can adjust the result by hand. `POST /admin/save-assignment` and `POST /admin/finalize-assignment` then persist it. Finalize rejects a zone that is missing or assigned twice, and a sales with no zone. A sales whose zones are not contiguous only produces a warning, returned in `warnings` and `disconnected_sales`. The redesign asks for confirmation before saving such a result.
5. The `*-legacy` endpoints are older variants.

### Algorithms (`algorithms.py`)

- `AdvancedTerritoryDesign.solve()` supports only `'grasp'` (Reactive GRASP, the frontend default) and `'tabu_search'`. Any other name raises `ValueError`.
- Zone workload is `customers + 0.2 * orders`. Solutions are scored by CV % of workload, with a heavy penalty above 15%, plus distance.
- `_ensure_complete_assignment` repairs assignments that leave zones out or create disconnected regions.

### Algorithm comparison (`algorithm_comparison.py`, `research_algorithms/`)

- `GET /admin/algorithms` lists the comparable algorithms and whether their Python packages are installed. `POST /admin/compare-algorithms` runs the selected ones on the same territory and sales (same checks as assign-work, via `_prepare_assignment_problem`) and returns, per algorithm, the assignment, a status and the same metrics (CV %, Hoover, max deviation of customers/orders, balance violation G for ±τ, max diameter/radius in km, disconnected and empty territories).
- Keys: `grasp` (the existing `AdvancedTerritoryDesign`, unchanged), `probvns` (Aly et al. 2024), `milp_center` / `milp_median` (Salazar-Aguilar 2011 as written in the paper: `paper_milp.py`, CPLEX through GAMSPy, ICGP-TDP with connectivity cuts, relaxation R1, gap 5e-6), `iqp_center` / `iqp_median` (same paper, GAMSPy/DICOPT). MILP and IQP need a GAMSPy license. The former OR-Tools/SCIP `exact_milp.py` was removed.
- Each algorithm runs in its own `multiprocessing` spawn process, in parallel, with `time_limit + 60 s` as a hard cap. `time_limit` can be 5–7200 s (7200 s is the paper's setting). There is no zone limit for MILP/IQP. The user's GAMSPy academic license runs CPLEX on the 458-zone territory, but such sizes need long time limits.
- `research_algorithms/` holds copies of the research code from `D:\territory problem\` (`TerritoryDesign_PaperFaithful/DTDPAlgorithms_paper.py` → `dtdp_probvns.py`, `Code/NASE-Code/paper_milp.py`, `gams_iqp.py`, `dicopt.opt`). `tdp_common.py` holds the instance format and helpers both use (taken from the old `exact_milp.py`). Edits to the copies are marked `project-2 patch`.
- `POST /admin/evaluate-assignment` recomputes the same metrics for any assignment `{sales_id: [zone_ids]}` (used after manual edits). It is read-only: it uses the stored adjacency and does not rebuild it. It rejects duplicate or foreign zones, and lists unassigned zones in `unassigned_zones`.
- Mapping: balance attributes are customers and orders (Prob-VNS also workload = customers + 0.2·orders); distances are Haversine km between zone centres. MILP/IQP use only the real adjacency, so their territories are contiguous in the app's sense. Prob-VNS does **not** enforce contiguity; when the adjacency graph is split it adds "bridge" edges only to compute distances.
- Frontend: `AlgorithmComparison.js` exists in `frontend/src/pages/` and `frontend-redesign/src/pages/`. The redesign copy has more: editing a zone's sales on each result map, metrics recomputed through `evaluate-assignment`, "Hoàn tác" per result, and exported `evaluateAssignment` / `moveZone` helpers. In the redesign, work assignment lives in its own tab "Phân công công việc" (`activeTab === "assignments"`). That tab has a territory selector and a "Chỉnh sửa phân vùng" button back to the territory tab. Its editor shows live metrics with deltas against the original result, and "Hoàn tác về kết quả ban đầu". Each app has its own `styles/AlgorithmComparison.css`. The component offers algorithm checkboxes, τ and time limit, comparison table, one Leaflet map per algorithm side by side, "Chọn kết quả này" loads a result into the existing edit/finalize flow). Finalize stores the chosen algorithm key, or `manual_adjusted` after manual edits.
- Tests: `python -m unittest test_algorithm_comparison test_evaluate_assignment` from `backend/` (runs the real solvers, about 30 s–4 min).

### Frontends

- `frontend/` is the main React app. It uses React Router, with pages in `src/pages`: `AdminDashboard` (map drawing with Leaflet and Turf, running and adjusting assignments) and `SalesDashboard` (shift, zones, invoices).
- `frontend-redesign/` is a parallel copy of the React app with a different UI.
- The `*.js` files in the repo root (`AdminDashboard.js`, `Login.js`, …) are untracked loose copies that differ from both apps. Edit the files under `frontend/src/pages/` unless asked otherwise.

## Data scripts (`backend/`)

- `create_100_sales.py` and `create_test_accounts.py` seed users.
- Fake zone metrics are area-based, through the shared helpers in `fake_metrics.py`: customers = density × area (km², computed from the geometry and stored in `zone.area_size`) × log-normal noise. The density is calibrated per territory so that a zone of median area gets about 200 customers, unless a fixed `customers_per_km2` is given. Orders and revenue follow the customers.
  - `POST /territories/{id}/fake-zone-metrics` (the "Fake dữ liệu" button) does this for one territory. It accepts the optional query params `seed`, `customers_per_km2` and `noise`.
  - `fake_zone_sales_history.py` does it for every zone, with 6 monthly `ZoneActivity` snapshots. Run it from the repo root as `python backend/fake_zone_sales_history.py [--seed N] [--months M] [--customers-per-km2 D] [--noise S]`. It writes to `app.db`.
  - Tests: `python -m unittest test_fake_zone_metrics` (in-memory SQLite).
- `generate_adjacency.py` is an old standalone script that filters on a `Zone.district_id` that no longer exists in the model. Prefer the rebuild-adjacency endpoint.
