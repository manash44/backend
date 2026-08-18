# VidGetNow Deployment Guide

## Part 1: Backend Deployment (Render.com)

We will deploy the Python/Flask backend to Render using Docker. This works for free and supports the necessary tools (`ffmpeg`, `yt-dlp`).

### Method 1: Easy Setup (Web Dashboard)
1.  Push this code to your **GitHub** repository.
2.  Go to [dashboard.render.com](https://dashboard.render.com).
3.  Click **New +** -> **Web Service**.
4.  Connect your GitHub repository.
5.  Select the **Docker** runtime (it should auto-detect the `Dockerfile`).
6.  **Settings**:
    *   **Name**: `vidgetnow-backend`
    *   **Region**: Any (e.g., Oregon)
    *   **Instance Type**: Free
    *   **Environment Variables**: Add `PORT` = `10000` (Render's default).
7.  Click **Create Web Service**.
8.  Wait for the build to finish. Once live, copy the URL (e.g., `https://vidgetnow-backend.onrender.com`).

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
    *   **Base directory**: `vidgrab_frontend-main/vidgrab_frontend-main`
    *   **Build command**: `npm run build`
    *   **Publish directory**: `dist`
6.  Click **Deploy Site**.
7.  Once deployed, open your new Netlify website.

---

## Part 3: Connect Frontend to Backend

1.  In `vidgrab_frontend-main/vidgrab_frontend-main/netlify.toml`, set the `/api/*` redirect to your Render backend URL.
2.  Redeploy the Netlify site.
3.  Open `https://YOUR_RENDER_SERVICE.onrender.com/health`. It should return `{"status":"ok"}`.
4.  Open the frontend. The app calls `/api`, and Netlify forwards those requests to Render.

---

## YouTube / Cloud Blocking

Some sites, especially YouTube, often rate-limit or block Render/cloud IPs. If normal public MP4 URLs download but YouTube fails with verification, bot, or rate-limit errors:

1.  Export a fresh Netscape-format `cookies.txt` from your own browser session.
2.  Do not commit it to GitHub.
3.  Add it to Render as an environment variable:
    *   `YTDLP_COOKIES` for plain cookie text, or
    *   `YTDLP_COOKIES_B64` for base64-encoded cookie text.
4.  Redeploy the backend.

---

### ⚠️ Important Notes for Free Tier
*   **Render Free Tier**: The backend spins down after 15 minutes of inactivity. It may take **50-60 seconds** to wake up when you first try to connect. The app handles this, but be patient on the first download of the day.
*   **Storage**: Free Render web services use ephemeral storage. That is fine here because downloads are temporary and expire from the backend cache.
*   **Persistent disks**: Free Render web services do not support persistent disks, so `render.yaml` does not attach one.
