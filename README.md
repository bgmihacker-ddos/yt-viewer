# YouTube Cloud Viewer (Railway Ready)

A lightweight, automated YouTube / Shorts viewer optimized to run 24/7 on [Railway](https://railway.app).

## 🚀 Features
- **Docker-ready**: Pre-configured with Google Chrome & Selenium.
- **Railway Healthcheck**: Built-in HTTP health endpoint so Railway recognizes the service as Healthy (never gets killed for inactivity).
- **Live Status Webpage**: Visit your Railway domain (`https://your-service.up.railway.app`) to see live progress and completed views.
- **Cloud Safe**: Configured with `--no-sandbox`, `--disable-dev-shm-usage`, and minimal CPU/memory footprint.
- **Dynamic Config**: Change target URL, views, and workers directly in the Railway dashboard without re-deploying code.

---

## 🛠️ How to Deploy on Railway

### Option 1: Deploy with GitHub (Recommended)
1. Initialize git and push this folder (`youtube-viewer`) to a new GitHub repository:
   ```bash
   cd "D:\amazing hacks\youtube-viewer"
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   # Link to your github repo:
   # git remote add origin https://github.com/<YOUR_USER>/<REPO_NAME>.git
   # git push -u origin main
   ```
2. Go to [Railway Dashboard](https://railway.app/dashboard).
3. Click **"New Project"** -> **"Deploy from GitHub repo"**.
4. Select your repository. Railway will detect the `Dockerfile` and build it automatically!

---

### Option 2: Deploy using Railway CLI
1. Open PowerShell in `D:\amazing hacks\youtube-viewer`.
2. Login and deploy directly:
   ```bash
   railway login
   railway init
   railway up
   ```

---

## ⚙️ Environment Variables (Configurable in Railway Dashboard)

In your Railway project under **Variables**, you can set:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VIDEO_URL` | `https://www.youtube.com/shorts/eTSipzkBEpQ` | YouTube video or Shorts link |
| `TARGET_VIEWS` | `1000` | Total views to run |
| `CONCURRENT_WORKERS` | `2` | Number of simultaneous headless browsers (2-3 recommended for free/starter tiers) |
| `WATCH_MIN_SEC` | `35` | Minimum watch duration per view in seconds |
| `WATCH_MAX_SEC` | `55` | Maximum watch duration per view in seconds |
| `PROXIES` | _(empty)_ | Comma-separated list of residential/mobile proxies (`ip:port,user:pass@ip:port`) |
