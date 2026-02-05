# XHMaster Deployment Guide

## Part 1: Backend Deployment (Render.com)

We will deploy the Python/Flask backend to Render using Docker. This works for free and supports the necessary tools (`ffmpeg`, `yt-dlp`).

### Method 1: Easy Setup (Web Dashboard)
1.  Push this code to your **GitHub** repository.
2.  Go to [dashboard.render.com](https://dashboard.render.com).
3.  Click **New +** -> **Web Service**.
4.  Connect your GitHub repository.
5.  Select the **Docker** runtime (it should auto-detect the `Dockerfile`).
6.  **Settings**:
    *   **Name**: `xhmaster-backend`
    *   **Region**: Any (e.g., Oregon)
    *   **Instance Type**: Free
    *   **Environment Variables**: Add `PORT` = `10000` (Render's default).
7.  Click **Create Web Service**.
8.  Wait for the build to finish. Once live, copy the URL (e.g., `https://xhmaster-backend.onrender.com`).

### Method 2: Infrastructure as Code (Blueprint)
1.  Go to [Render Blueprints](https://dashboard.render.com/blueprints).
2.  Click **New Blueprint Instance**.
3.  Connect your repo. Render will read the `render.yaml` file and set everything up automatically.

---

## Part 2: Frontend Deployment (Netlify)

The frontend is a static React app.

1.  Push your code to **GitHub**.
2.  Go to [app.netlify.com](https://app.netlify.com).
3.  Click **Add new site** -> **Import from an existing project**.
4.  Connect GitHub and select your repository.
5.  **Build Settings** (should be auto-detected from `netlify.toml`):
    *   **Base directory**: `frontend`
    *   **Build command**: `npm run build`
    *   **Publish directory**: `dist`
6.  Click **Deploy Site**.
7.  Once deployed, open your new Netlify website.

---

## Part 3: Connect Frontend to Backend

1.  Open your **Netlify Website** (Frontend).
2.  Click the **Settings (Gear Icon)** in the top right.
3.  Paste your **Render Backend URL** (from Part 1, e.g., `https://xhmaster-backend.onrender.com`).
4.  Click **Save & Connect**.
5.  The app will test the connection. If it turns green, you are ready to download!

---

### ⚠️ Important Notes for Free Tier
*   **Render Free Tier**: The backend spins down after 15 minutes of inactivity. It may take **50-60 seconds** to wake up when you first try to connect. The app handles this, but be patient on the first download of the day.
*   **Storage**: The `render.yaml` requests a small disk for downloads, but transient storage is usually fine for temp files.
