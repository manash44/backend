# Build VidGetNow Android APK

## ⚠️ First: Install Node.js

Node.js is **not installed** on this machine. You must install it first:

1. Download from **https://nodejs.org** (LTS version)
2. Run the installer — it adds `node` and `npm` to PATH automatically
3. **Restart your terminal** after installation

Verify install:
```
node --version
npm --version
```

---

## Build Steps (after Node.js is installed)

### 1. Open a terminal in the frontend folder
```
cd F:\Projects\vidgetnow\vidgrab_frontend-main\vidgrab_frontend-main
```

### 2. Install dependencies
```
npm install
```

### 3. Build & sync to Android
```
npm run cap:sync
```
This builds the Vite web app and syncs it into the `android/` folder.

### 4. Open in Android Studio
```
npm run cap:open
```
Or open the `android/` folder directly in Android Studio.

### 5. Build the APK
In Android Studio:
1. Wait for Gradle sync (bottom progress bar)
2. Go to **Build → Build Bundle(s)/APK(s) → Build APK(s)**
3. Click **"locate"** in the popup

APK location:
```
android\app\build\outputs\apk\debug\app-debug.apk
```

---

## Quick Command (all-in-one after Node install)
```cmd
cd F:\Projects\vidgetnow\vidgrab_frontend-main\vidgrab_frontend-main
npm install && npm run cap:sync
```
Then open Android Studio to build the APK.

---

## Transfer APK to Phone
1. Copy `app-debug.apk` to your phone
2. Enable **"Install from unknown sources"** in Android settings
3. Tap the APK to install
4. Open VidGetNow — it connects to `https://backend-iu1e.onrender.com` automatically

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `npm not found` | Install Node.js from nodejs.org |
| Gradle sync fails | Open Android Studio → File → Sync Project with Gradle Files |
| App won't install | Enable "Unknown sources" in Android settings |
| Videos won't download | Check backend is running on Render.com |
