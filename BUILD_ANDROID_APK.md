# Building VidGetNow Android APK

This guide explains how to build the VidGetNow Android APK from source.

## Prerequisites

1. **Android Studio** - Download from https://developer.android.com/studio
2. **Java JDK 17+** - Usually bundled with Android Studio
3. **Node.js** - Already installed if you've been running the app

## Quick Build Steps

### 1. Sync the Project

Open a terminal in the `frontend` folder and run:

```bash
npm run cap:sync
```

This builds the web app and syncs it to the Android project.

### 2. Open in Android Studio

```bash
npm run cap:open
```

Or manually open `frontend/android` folder in Android Studio.

### 3. Build the APK

In Android Studio:

1. Wait for Gradle sync to complete (bottom progress bar)
2. Go to **Build** → **Build Bundle(s) / APK(s)** → **Build APK(s)**
3. Wait for build to complete
4. Click **"locate"** in the popup to find the APK

The APK will be at:
```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

## Building Release APK (Signed)

For a release build that can be distributed:

### 1. Create a Signing Key

```bash
keytool -genkey -v -keystore vidgetnow-release.keystore -alias vidgetnow -keyalg RSA -keysize 2048 -validity 10000
```

### 2. Configure Signing in Android Studio

1. Open **Build** → **Generate Signed Bundle / APK**
2. Select **APK**
3. Choose your keystore file
4. Enter passwords and alias
5. Select **release** build variant
6. Click **Finish**

The signed APK will be at:
```
frontend/android/app/release/app-release.apk
```

## Using the APK

### Option A: Same WiFi Network (Local Mode)

#### On Your PC (Server)
1. Run the VidGetNow server:
   ```bash
   python app.py
   ```
2. Note the **Network URL** shown (e.g., `http://192.168.1.100:5000`)

#### On Your Android Phone
1. Transfer the APK to your phone
2. Install it (you may need to enable "Install from unknown sources")
3. Open VidGetNow app
4. Tap the **Settings** icon (⚙️) in the top-right corner
5. Enter your PC's IP and port: `192.168.1.100:5000`
6. Tap **Save & Connect**
7. Start downloading videos!

---

### Option B: Internet Access (Use from ANYWHERE!)

This allows your phone to connect from **anywhere** - different WiFi, mobile data, even from another country!

#### One-Time Setup (ngrok):
1. Go to https://dashboard.ngrok.com/signup and create a **free account**
2. Copy your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
3. Run this command **once** to save your token:
   ```bash
   ngrok config add-authtoken YOUR_AUTH_TOKEN_HERE
   ```

#### Running with Internet Access:
1. Run the server with the `--ngrok` flag:
   ```bash
   python app.py --ngrok
   ```
2. Copy the **INTERNET URL** shown (looks like `https://xxxx-xx-xx-xx-xx.ngrok-free.app`)
3. In the Android app, tap **Settings** and enter this URL
4. Now you can download videos from **anywhere with internet**!

**Note:** The free ngrok URL changes each time you restart the server. For a permanent URL, consider ngrok's paid plan or deploy to a cloud server.

## Troubleshooting

### "Cannot connect to server" (Local Mode)

- Ensure both phone and PC are on the same WiFi network
- Check if Windows Firewall is blocking port 5000
- Try disabling Windows Firewall temporarily or add an exception
- Make sure the server is running (`python app.py`)

### "Cannot connect to server" (ngrok/Internet Mode)

- Make sure you ran `ngrok config add-authtoken YOUR_TOKEN` first
- The ngrok URL changes each restart - update the app settings with the new URL
- Check if ngrok is running (look for the URL in the console output)
- Try visiting the ngrok URL in your phone's browser first to test

### "App won't install"

- Enable "Install from unknown sources" in Android settings
- For Android 8+: Settings → Apps → Special access → Install unknown apps

### "Connection refused"

Run this in Command Prompt (Admin) to allow port 5000:
```cmd
netsh advfirewall firewall add rule name="VidGetNow" dir=in action=allow protocol=TCP localport=5000
```

## Development Commands

| Command | Description |
|---------|-------------|
| `npm run cap:sync` | Build web + sync to Android |
| `npm run cap:open` | Open in Android Studio |
| `npm run cap:copy` | Copy web assets to Android (no plugin update) |
| `npm run cap:build` | Full build pipeline |

## Updating the App

After making changes to the web app:

```bash
cd frontend
npm run cap:sync
```

Then rebuild in Android Studio.
