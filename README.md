# 🧠 BehavMetrix: Behavioral Welfare Analytics for Primate Colonies

**BehavMetrix** is a scalable behavioral monitoring platform built to track welfare, stress, social rank, and enrichment usage across large primate colonies (up to 80 individuals). Designed for researchers, field teams, and welfare managers, it combines real-time observation tools with scientifically grounded analytics.

> Built for primatologists, enriched for ethical labs.  
> Because meaningful care starts with measurable behavior.

---

## 🔍 Features

- **📊 Colony Dashboard**  
  Visual grid view of all animals with welfare scores, alerts, enrichment status, and social rank.

- **🐒 Behavior Logger**  
  Mobile-ready ethogram input for 1–80 animals; attach timestamps and observation reasons.

- **📈 Social Rank Engine**  
  Computes dynamic Elo and David’s Scores; highlights sudden rank shifts or dominance instability.

- **🎯 Stress Detection**  
  Tracks behavioral stress markers (SDBs, isolation, aggression) with customizable thresholds.

- **🧸 Enrichment Tracker**  
  Logs frequency and type of enrichment interaction; scores impact on welfare trends.

- **🗂️ Flexible Data Import**  
  Supports CSV, Excel, or SQL uploads with standard fields: Animal ID, Cage, Sex, Age, Weight.

---

## 🧪 Use Case Snapshot

1. Upload a CSV of 65 macaques with ID, weight, age, sex, and cage location.
2. Log behavior during post-feeding hour — grooming rises, aggression spikes in subgroup C.
3. Dashboard shows drop in enrichment use for 7 animals → flags for review.
4. Automatically ranks individuals via Elo score; alerts if high-ranking female shows social withdrawal.
5. Export PDF welfare report for staff or ethics board.

---

## ⚙️ Tech Stack

- **Frontend:** React + TailwindCSS  
- **Backend:** FastAPI (Python), SQLAlchemy  
- **Database:** PostgreSQL or Firebase  
- **Libraries:** Pandas, Chart.js, NetworkX  
- **Optional:** DeepLabCut, OpenWeather API

---

## 🧬 Run Locally

```bash
git clone https://github.com/your-org/behavmetrix.git
cd behavmetrix
pip install -r requirements.txt
npm install
uvicorn app.main:app --reload
npm run dev
