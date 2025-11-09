# 🧠 BehavMetrix: Behavioral Welfare Analytics for Primate Colonies

BehavMetrix is a FAIR-compliant Flask web application that enables animal care teams to log, analyze, and share welfare insights for large outdoor macaque colonies (up to 80 animals). The platform focuses on reproducible behavioral data capture, transparent metadata, and interoperable exports so that labs can collaborate around shared ethograms and enrichment outcomes.

---

## ✨ Key Modules

- **Data Ingestion** – Upload CSV/Excel sheets or stream SQL tables. Required fields (Animal ID, Cage ID, Sex, Age, Weight) are validated and every import generates provenance metadata (user, timestamp, source, notes).
- **Colony Dashboard** – Tablet-friendly dashboard with animal profile cards (stress score, weight, enrichment use, rank) and colony-level summaries (grooming %, aggression, play). Rank instability is visualized through an interactive network graph.
- **Behavior Logging** – Ontology-aligned macaque ethogram buttons for grooming, aggression, play, pacing, and SDBs. Supports scan samples and focal follows tied to animal IDs with observer metadata.
- **Social Ranking System** – Calculates Elo scores from interaction logs, surfaces potential instability, and links rank values back to timestamped behavior events.
- **Enrichment Tracker** – Logs enrichment inventory usage (item, duration, response, success tag) and tracks correlations with stress/SDB reduction.
- **Stress Monitor** – Daily logging of stress indicators (withdrawal, fear grimace, self-biting) with linkage to behavior and hormone measurements.
- **Incident & Observation Tracker** – Capture ad-hoc notes, attach media links, and assign FAIR tags to incidents or enrichment trials.
- **Exports & API** – Download CSV/JSON/Excel snapshots with full metadata or integrate via REST endpoints for animals, behaviors, and enrichment logs.

---

## 🗂️ Project Structure

```
BehavMetrix/
├── app/
│   ├── __init__.py            # Flask app factory, extensions, CLI
│   ├── api.py                 # REST API blueprint
│   ├── models.py              # SQLAlchemy models & Marshmallow schemas
│   ├── mock_data.py           # Faker-powered mock dataset generator
│   ├── routes.py              # Web routes and dashboard logic
│   ├── utils/
│   │   ├── analytics.py       # Elo ranking, colony stats helpers
│   │   └── ingestion.py       # FAIR data ingestion helpers
│   ├── templates/             # Bootstrap/Jinja2 UI
│   └── static/                # Styles and assets
├── behavmetrix.py             # WSGI/CLI entry point
├── requirements.txt           # Python dependencies
└── README.md
```

---

## 🚀 Getting Started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=behavmetrix.py
flask --app behavmetrix.py db upgrade  # if migrations configured
flask --app behavmetrix.py create-mock-data
flask --app behavmetrix.py run
```

Visit `http://127.0.0.1:5000/` for the dashboard.

> **Note:** The scaffold ships with mock data so you can explore dashboards without instrumentation. Replace the dataset using the ingestion module to load your colony records.

---

## 📄 FAIR & Compliance Considerations

- **Findable:** Global search/filter fields, persistent IDs, and ranked exports ensure that animals and events are discoverable.
- **Accessible:** REST API endpoints (`/api/animals`, `/api/behaviors`, `/api/enrichment`) return JSON structures compatible with downstream tools.
- **Interoperable:** Behavior definitions align with NC3Rs/NBO ontology codes; exports include schema-complete metadata for reuse by partner labs.
- **Reusable:** MIT-licensed code and CC-BY recommended for exported datasets. Documentation describes behavior definitions, scoring logic, and enrichment success criteria.

---

## 📚 Additional Notes

- Configure `DATABASE_URL` to switch from SQLite to PostgreSQL or MySQL.
- Extend `app/utils/ingestion.py` to connect directly to lab SQL servers.
- Use the `/behavior-log` module during focal follows; `/enrichment` for enrichment trials; `/stress` to capture daily welfare scores; `/incident` for ad-hoc notes.
- Customize the ethogram by editing `BEHAVIOR_DEFINITIONS` in `app/mock_data.py` and inserting additional `BehaviorDefinition` rows via ingestion or migrations.

---

## 📜 License

- **Code:** MIT License (see `LICENSE` once added).
- **Data Outputs:** Recommend CC-BY 4.0 for shared exports.
