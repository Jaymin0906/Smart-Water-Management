# AquaPulse - Smart Water Management System 💧

AquaPulse is a full-featured, modern Smart Water Management System built with Python Flask, SQLite, Chart.js, and CSS animations.

---

## 🌟 Key Features

1. **User Authentication & Isolation**
   - Secure sign-up and login with password hashing via PBKDF2/Werkzeug.
   - Complete multi-tenant data isolation: each user manages their own reservoir, settings, and telemetry history.
   - Built-in demo user: `admin` / `water123`.

2. **CSRF Protection & Hardened Sessions**
   - Cryptographically random session tokens (`secrets.token_hex(32)`).
   - Middleware-enforced validation via `hmac.compare_digest` on all state-changing requests (POST/PUT/DELETE).
   - Secure HTTP-only and SameSite session cookies.

3. **Live Animated Reservoir Graphic**
   - Dual-layered SVG wave effect with smooth CSS animations.
   - Color shifts to amber (low level) and pulsating red (overflow alert).
   - Real-time graduation ticks and level indicators.

4. **Configurable Thresholds & Automation**
   - Configurable total tank capacity in Litres.
   - Configurable alert limits: Low Level (%), High Level (%), and Overflow (%).
   - **Auto Pump Mode**: Automatically engages the pump when water drops to or below the low threshold, and turns it off when the high threshold is reached.
   - **Manual Mode**: Direct operator relay override.

5. **Tank-Empty Prediction Model**
   - Calculates depletion velocity ($\Delta\text{Level} / \Delta\text{Time}$) using chronological, time-separated telemetry rows.
   - Estimates decimal hours to empty and projects depletion timestamps.
   - Safely detects static consumption or refilling states to prevent invalid forecasts.

6. **Interactive Analytics & CSV Export**
   - Real-time line graph using Chart.js displaying Water Level (%) and Volume (Litres).
   - One-click CSV export of historical records (`/export/csv`).

---

## 📂 Project Structure

```
water_app/
├── .vscode/
│   └── launch.json            # One-click VS Code debugger configuration
├── app.py                     # Flask application & route controllers
├── requirements.txt           # Project dependencies
├── test_aquapulse.py          # Automated test suite (10 test cases)
├── instance/
│   └── aquapulse.db           # SQLite multi-user database
├── static/
│   ├── css/
│   │   └── style.css          # Navy sidebar, white cards & wave animation
│   └── js/
│       ├── main.js            # Mobile drawer & UI toast dismissals
│       ├── dashboard.js       # Animated wave tank logic
│       └── history.js         # Chart.js time-series trend renderer
└── templates/
    ├── base.html              # Core layout shell & navigation
    ├── login.html             # Sign in form with demo credentials
    ├── signup.html            # Registration form
    ├── dashboard.html         # Overview metrics & animated reservoir
    ├── monitor.html           # Sensor slider, test presets & pump switches
    ├── history.html           # Chart.js trends & tabular records
    ├── prediction.html        # Consumption rate & time-to-empty forecast
    └── settings.html          # Tank capacity & threshold calibrations
```

---

## 🚀 Running in VS Code

### 1. Open the Folder in VS Code
Open the directory:
```
C:\Users\HP\.gemini\antigravity\scratch\water_app
```
in VS Code (`File` > `Open Folder...`).

### 2. Install Dependencies
Open the VS Code Terminal (`Ctrl + ~`) and execute:
```powershell
pip install -r requirements.txt
```

### 3. Launch the Server
You can start the server in either of two ways:

- **Option A (One-click VS Code Debugger)**:
  Press `F5` or navigate to the **Run & Debug** tab and select **"Python: AquaPulse Flask App"**.

- **Option B (Terminal Command)**:
  ```powershell
  python app.py
  ```

### 4. Access the Dashboard
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

- **Demo Username**: `admin`
- **Demo Password**: `water123`

---

## 🧪 Running Automated Tests

Run the test suite from the terminal:
```powershell
python test_aquapulse.py
```
Expected result: `Ran 24 tests ... OK`.

