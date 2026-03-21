## Deployment Guide: GitHub Pages + Railway Backend

This guide walks through hosting the UI on GitHub Pages and the Flask backend on Railway.

---

## Part 1: Deploy Flask Backend to Railway

### Step 1: Create a Railway Account
1. Go to https://railway.app
2. Sign up (free tier available)
3. Connect your GitHub account

### Step 2: Create a New Project
1. Click "Create New Project"
2. Select "Deploy from GitHub repo"
3. Choose the `Hospital-Triage` repository
4. Railway will auto-detect Flask and the `requirements.txt`

### Step 3: Configure Environment Variables
1. Go to your project settings
2. Add environment variable: `FLASK_ENV=production`
3. Railway will automatically assign a public URL (e.g., `https://hospital-triage.railway.app`)

### Step 4: Deploy
1. Railway deploys automatically on git push
2. Copy your public URL from the Railway dashboard

---

## Part 2: Enable GitHub Pages

### Step 1: Configure GitHub Pages
1. Go to your repo: https://github.com/HotokeZ/Hospital-Triage
2. Settings → Pages
3. Select "Deploy from a branch"
4. Branch: `main`, Folder: `/docs`
5. Save

Your site will be available at: `https://HotokeZ.github.io/Hospital-Triage`

---

## Part 3: Connect Frontend to Backend

### Option A: Manual (One-time setup)
1. Open https://HotokeZ.github.io/Hospital-Triage
2. Click the backend configuration banner
3. Enter your Railway URL: `https://hospital-triage.railway.app`
4. The setting is saved in browser localStorage

### Option B: Automatic (Hardcode in code)
Edit `docs/index.html` line ~180:
```javascript
let BACKEND_URL = 'https://hospital-triage.railway.app';
```

---

## Troubleshooting

### CORS Errors
- Flask app has CORS enabled in `app.py`
- If issues persist, check that Railway app is running: visit `https://your-railway-url/api/status`

### Simulation Timeout
- Railway free tier may timeout long simulations (>30 sec)
- Reduce `sim_time` or `num_replications` in the UI

### GitHub Pages Not Updating
- Git push changes
- Clear browser cache (Ctrl+Shift+Del)
- Pages rebuild takes ~1 min

---

## Alternative Backends

If Railway doesn't work, try:
- **Render**: https://render.com (free tier, auto-deploy from GitHub)
- **PythonAnywhere**: https://pythonanywhere.com (easy Python hosting)
- **Heroku** (paid): https://heroku.com

For any of these, update the backend URL in `docs/index.html`.

---

## Local Development

To test locally before deploying:

```bash
pip install -r requirements.txt
python app.py
```

Then visit:
- Flask UI: http://localhost:5000
- Static UI: Open `docs/index.html` in a browser and configure backend to `http://localhost:5000`

---

Questions? Check the Flask logs in the Railway dashboard or GitHub repo issues.
