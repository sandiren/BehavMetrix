# 🧠 BehavMetrix: Behavioral Welfare Analytics for Primate Colonies

BehavMetrix is a web-based MVP designed to help facilities track welfare outcomes for outdoor macaque colonies (up to 80 animals). The platform combines high-throughput data import, tablet-friendly ethogram logging, automated social-rank analytics, and proactive stress alerts.

---

## 📦 Repository Layout

```
backend/
  app/
    alerts_engine.py      # Welfare flag + stress threshold logic
    data_import.py        # CSV / Excel / SQL ingestion helpers
    elo_ranker.py         # Elo score computation and overrides
    ethogram_logger.py    # Touch-optimized behavioral logging helpers
    main.py               # FastAPI application with REST endpoints
    models.py             # SQLAlchemy ORM models
    reporting.py          # CSV / Excel exports and weekly PDF generation
    schemas.py            # Pydantic schema definitions
  requirements.txt        # Backend dependency pinning
frontend/
  src/components/dashboard_ui.jsx  # React dashboard UI
  ...                               # Vite + Tailwind scaffold
```

---

## 🚀 Getting Started

### 1. Backend API (FastAPI + SQLAlchemy)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

*Default database:* SQLite via `DATABASE_URL=sqlite+aiosqlite:///./behavmetrix.db`. Override with PostgreSQL for production.

### 2. Frontend (React + TailwindCSS)

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies API requests to `http://localhost:8000`.

---

## 🧩 Core Capabilities

### Data Input
- Upload CSV or Excel animal rosters with required fields: **Animal ID, Cage ID, Sex, Age, Weight**.
- Import directly from SQL queries against the configured database.

### Animal Dashboard
- Grid renders 80 animal cards with welfare score, social rank, enrichment summary, and weight trend sparkline.
- Flag colors: **green** (stable), **yellow** (watch), **red** (alert) driven by `alerts_engine` thresholds.

### Behavior Logging Interface
- Multi-animal batch logging via ethogram controls optimized for touch displays.
- Captures timestamped records with “Reason for Observation” selections.

### Social Hierarchy Module
- Computes Elo scores from aggression/submission logs and persists to animals.
- Force-directed graph visualizes rank dynamics with optional manual overrides.

### Enrichment Tracker
- Records enrichment item interactions (frequency, duration, category).
- Scatter chart reveals relationships between enrichment engagement and welfare scores.

### Stress Monitor
- Tracks stress indicators (e.g., self-biting, withdrawal, cortisol).
- Automatic alerts raised when averaged stress values exceed facility thresholds.

### Export & Reporting
- Download animals or behavior logs in CSV/Excel.
- Generate weekly PDF summary listing top five at-risk animals and recent stress events.

---

## 🛠️ Extending the MVP

- **Database Migrations:** Integrate Alembic for schema management in production.
- **Auth & Permissions:** Add OAuth2 or SSO to gate sensitive welfare data.
- **Realtime Sync:** Pair with WebSockets for live dashboard updates during observation sessions.
- **Analytics Enhancements:** Incorporate cortisol lab results, weather overlays, or machine-vision posture scores.

---

## 🧑‍🤝‍🧑 Contributing

1. Fork the repository and create a feature branch.
2. Ensure linting/tests pass and add/update documentation as needed.
3. Submit a pull request summarising your changes and testing evidence.

Care for the colony, care for the data. 💚
