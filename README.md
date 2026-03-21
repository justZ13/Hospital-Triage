# Hospital Triage — Dash Prototype

This project contains a SimPy-based hospital triage simulation and a Dash-based UI prototype for visualizing results.

Quick start (Windows, with Python environment active):

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Run the Dash app:

```powershell
python dash_app.py
```

3. Open http://127.0.0.1:8050 in your browser.

Notes:
- The simulation logic is in `simulation.py` (function `run_simulation`).
- `dash_app.py` is a simple synchronous prototype. For long Monte Carlo runs, consider adding background workers.
