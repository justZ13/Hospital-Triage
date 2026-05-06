# Hospital Triage — Computational Simulation

A discrete-event simulation of a hospital triage system using SimPy, with a modern Flask backend and GitHub Pages frontend.

## 🚀 Quick Start (Local)

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## 🌐 Live Deployment

- **Frontend (GitHub Pages):** https://justz13.github.io/Hospital-Triage/
- **Backend (Railway production):** https://hospital-triage-production.up.railway.app

(The frontend is configured to use the Railway backend above. If you change the backend, update `docs/index.html` or set `backendUrl` in your browser's localStorage.)

## 📁 Project Structure

```
Hospital-Triage/
├── app.py                 # Flask backend (SimPy API)
├── simulation.py          # SimPy queuing model
├── requirements.txt       # Python dependencies
├── Procfile              # Railway deployment config
├── docs/
│   └── index.html        # GitHub Pages static UI
├── templates/
│   ├── base.html         # Flask base template
│   └── index.html        # Flask main template
├── static/
│   └── style.css         # Professional styling
└── DEPLOYMENT.md         # Step-by-step hosting guide
```

## 🎯 Features

- **Stochastic Simulation:** Exponential arrivals, priority queuing (3 severity levels)
- **Monte Carlo:** Run multiple replications for confidence intervals
- **Interactive Dashboard:** Real-time charts, progress tracking, CSV export
- **Async Processing:** Long runs don't block the UI
- **CORS-Enabled:** Supports remote frontend (GitHub Pages) + backend (Railway)

## 📊 Simulation Metrics

- Total patients treated
- Average / max / min wait times by severity
- Throughput (patients/hour)
- Service time distribution
- Wait time trends over simulation

## 🛠️ Tech Stack

- **Backend:** Flask, SimPy, Pandas, Plotly
- **Frontend:** Bootstrap 5, Plotly.js, Vanilla JS
- **Hosting:** Railway (backend), GitHub Pages (frontend)

## 📖 Usage

### Local Development
```bash
python app.py
# Visit http://localhost:5000
```

### Production Deployment
See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions on:
1. Deploying Flask to Railway
2. Enabling GitHub Pages
3. Connecting frontend to remote backend

## 📝 Simulation Parameters

| Parameter | Range | Description |
|-----------|-------|-------------|
| Number of Staff | 1–20 | Server capacity |
| Avg Arrival Rate | 0.1–60 min | Exponential inter-arrival time mean |
| Simulation Time | 10–10000 min | Total run duration |
| Replications | 1–100 | Monte Carlo runs for confidence intervals |

## 📋 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/run` | POST | Start a simulation |
| `/api/status` | GET | Check simulation progress |
| `/api/results` | GET | Fetch latest results + charts |
| `/api/download` | GET | Download results as CSV |

## ✅ Project Requirements Met

- [x] Discrete-event simulation of a real-world system
- [x] Stochastic modeling (exponential arrivals, Monte Carlo)
- [x] Priority queuing with 3 severity levels
- [x] Performance metrics (wait times, throughput)
- [x] Multiple simulation runs (replications)
- [x] Validation & sensitivity analysis (via UI parameters)
- [x] Professional UI/UX with interactive charts
- [x] Deployed online (GitHub Pages + Railway)

## 📄 Project Report & Presentation

Report: See `REPORT.md` (APA format, 10–15 pages)  
Slides: See `presentation/` folder  
Demo: Run locally or visit the live link above

## 🔗 Links

- GitHub: https://github.com/HotokeZ/Hospital-Triage
- Live UI: https://justz13.github.io/Hospital-Triage/
- Deployment: [DEPLOYMENT.md](DEPLOYMENT.md)

---

**CSEL 303 Final Project — Computational Science | 2026**

