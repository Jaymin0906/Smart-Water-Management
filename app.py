import os
import csv
import io
import sqlite3
import secrets
import hmac
import re
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, Response, flash, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Security & Session Settings
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "aquapulse-super-secret-key-99a38f12")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

DB_PATH = os.path.join(app.instance_path, "aquapulse.db")


# ---------- DATABASE HELPERS ----------
def get_db():
    if "db" not in g:
        os.makedirs(app.instance_path, exist_ok=True)
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def parse_timestamp(ts_str):
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(ts_str).strip(), fmt)
        except (ValueError, TypeError):
            pass
    return None


def init_db():
    os.makedirs(app.instance_path, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute("PRAGMA foreign_keys = ON;")
        
        # Users Table
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # User Settings Table
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                tank_capacity REAL DEFAULT 1000.0,
                low_threshold REAL DEFAULT 20.0,
                high_threshold REAL DEFAULT 80.0,
                overflow_threshold REAL DEFAULT 95.0,
                pump_mode TEXT DEFAULT 'Manual',
                current_pump_state TEXT DEFAULT 'OFF',
                current_level REAL DEFAULT 80.0,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)

        # Timestamped Readings Table
        con.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                level REAL NOT NULL,
                litres REAL NOT NULL,
                pump_state TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)

        # Seed Default Admin Account if table is empty
        cursor = con.execute("SELECT id FROM users WHERE username = ?", ("admin",))
        admin = cursor.fetchone()
        if not admin:
            hashed_pwd = generate_password_hash("water123")
            cur = con.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                ("admin", "admin@aquapulse.io", hashed_pwd)
            )
            admin_id = cur.lastrowid
            con.execute(
                """INSERT INTO user_settings (
                    user_id, tank_capacity, low_threshold, high_threshold,
                    overflow_threshold, pump_mode, current_pump_state, current_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (admin_id, 1000.0, 20.0, 80.0, 95.0, "Manual", "OFF", 78.0)
            )

            # Seed realistic time-separated sample readings for the admin
            now = datetime.now()
            sample_readings = [
                (92.0, 920.0, "OFF", (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")),
                (88.0, 880.0, "OFF", (now - timedelta(hours=4, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")),
                (84.0, 840.0, "OFF", (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")),
                (81.0, 810.0, "OFF", (now - timedelta(hours=1, minutes=45)).strftime("%Y-%m-%d %H:%M:%S")),
                (78.0, 780.0, "OFF", (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"))
            ]
            for r in sample_readings:
                con.execute(
                    "INSERT INTO readings (user_id, level, litres, pump_state, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (admin_id, r[0], r[1], r[2], r[3])
                )
        # Check and preserve legacy records from existing water.db if practical
        admin_row = con.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if admin_row:
            admin_id = admin_row[0]
            legacy_paths = [
                os.path.join(os.path.dirname(app.instance_path), "water.db"),
                "water.db"
            ]
            for leg_path in legacy_paths:
                if os.path.exists(leg_path):
                    try:
                        with sqlite3.connect(leg_path) as leg_con:
                            leg_readings = leg_con.execute("SELECT level, pump, time FROM readings").fetchall()
                            for lr in leg_readings:
                                parsed_lr = parse_timestamp(lr[2])
                                clean_ts = parsed_lr.strftime("%Y-%m-%d %H:%M:%S") if parsed_lr else str(lr[2])
                                exists = con.execute(
                                    "SELECT id FROM readings WHERE timestamp = ? AND user_id = ?",
                                    (clean_ts, admin_id)
                                ).fetchone()
                                if not exists:
                                    con.execute(
                                        "INSERT INTO readings (user_id, level, litres, pump_state, timestamp) VALUES (?, ?, ?, ?, ?)",
                                        (admin_id, float(lr[0]), round(1000.0 * float(lr[0]) / 100.0, 1), str(lr[1]), clean_ts)
                                    )
                    except Exception:
                        pass
                    break

        # Standardize any existing non-ISO legacy timestamps in readings table
        try:
            cur_fix = con.execute("SELECT id, timestamp FROM readings WHERE timestamp LIKE '__-__-____%'").fetchall()
            for r_id, r_ts in cur_fix:
                p_ts = parse_timestamp(r_ts)
                if p_ts:
                    con.execute("UPDATE readings SET timestamp = ? WHERE id = ?", (p_ts.strftime("%Y-%m-%d %H:%M:%S"), r_id))
        except Exception:
            pass

        con.commit()


# Initialize database tables on module load
init_db()


# ---------- CSRF PROTECTION & CONTEXT ----------
def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


@app.context_processor
def inject_template_globals():
    return {
        "csrf_token": generate_csrf_token,
        "current_user": g.get("user"),
        "now": datetime.now()
    }


@app.before_request
def security_and_auth_middleware():
    # Load logged-in user
    user_id = session.get("user_id")
    if user_id:
        db = get_db()
        g.user = db.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,)).fetchone()
    else:
        g.user = None

    # CSRF check on state-changing requests
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        exempt_paths = []
        if request.path not in exempt_paths:
            submitted_token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
            session_token = session.get("_csrf_token")
            is_valid = False
            if session_token and submitted_token and isinstance(submitted_token, str):
                try:
                    is_valid = hmac.compare_digest(submitted_token.encode("utf-8"), session_token.encode("utf-8"))
                except Exception:
                    is_valid = False

            if not is_valid:
                flash("Security verification failed (Invalid or missing CSRF token). Please try again.", "danger")
                return redirect(request.referrer or url_for("dashboard"))


# ---------- AUTHENTICATION DECORATOR ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id") or not g.get("user"):
            flash("Please sign in to access AquaPulse.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ---------- BUSINESS LOGIC HELPERS ----------
def get_or_create_settings(user_id):
    db = get_db()
    settings = db.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    if not settings:
        db.execute(
            """INSERT INTO user_settings (
                user_id, tank_capacity, low_threshold, high_threshold,
                overflow_threshold, pump_mode, current_pump_state, current_level
            ) VALUES (?, 1000.0, 20.0, 80.0, 95.0, 'Manual', 'OFF', 80.0)""",
            (user_id,)
        )
        db.commit()
        settings = db.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    return settings


def get_tank_status(level, settings):
    overflow = float(settings["overflow_threshold"])
    low = float(settings["low_threshold"])
    high = float(settings["high_threshold"])

    if level >= overflow:
        return "Overflow Alert", "danger", "#ef4444"
    elif level <= low:
        return "Low Water Alert", "warning", "#f59e0b"
    elif level >= high:
        return "High Level", "info", "#06b6d4"
    else:
        return "Normal", "success", "#10b981"


def save_reading_record(user_id, level, pump_state):
    db = get_db()
    settings = get_or_create_settings(user_id)
    capacity = float(settings["tank_capacity"])
    litres = round(capacity * (level / 100.0), 1)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Insert historical telemetry
    db.execute(
        "INSERT INTO readings (user_id, level, litres, pump_state, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user_id, level, litres, pump_state, timestamp)
    )

    # Update live state in settings
    db.execute(
        "UPDATE user_settings SET current_level = ?, current_pump_state = ? WHERE user_id = ?",
        (level, pump_state, user_id)
    )
    db.commit()


def calculate_empty_prediction(user_id, current_level, tank_capacity):
    """
    Calculates estimated hours until empty from valid, time-separated falling readings.
    """
    db = get_db()
    rows = db.execute(
        "SELECT level, timestamp FROM readings WHERE user_id = ? ORDER BY id DESC LIMIT 20",
        (user_id,)
    ).fetchall()

    if len(rows) < 2:
        return {
            "available": False,
            "message": "Not enough readings. At least 2 time-separated readings are required.",
            "rate_percent_per_hour": 0.0,
            "rate_litres_per_hour": 0.0,
            "hours_remaining": None,
            "formatted_time": None,
            "projected_empty_date": None,
            "trend": "Insufficient Data"
        }

    # Search for a valid pair of readings that show consumption over a meaningful time window (> 30 seconds)
    newest = rows[0]
    newest_time = parse_timestamp(newest["timestamp"])
    if not newest_time:
        return {
            "available": False,
            "message": "Timestamp parsing unavailable for recent reading.",
            "rate_percent_per_hour": 0.0,
            "rate_litres_per_hour": 0.0,
            "hours_remaining": None,
            "formatted_time": None,
            "projected_empty_date": None,
            "trend": "Insufficient Data"
        }

    valid_drop_found = False
    rate_pct_per_hr = 0.0
    elapsed_hours_total = 0.0
    level_diff_total = 0.0

    for older in rows[1:]:
        older_time = parse_timestamp(older["timestamp"])
        if not older_time:
            continue
        elapsed_seconds = (newest_time - older_time).total_seconds()
        
        # Require at least 30 seconds separation for calculation
        if elapsed_seconds >= 30:
            level_diff = older["level"] - newest["level"]
            elapsed_hours = elapsed_seconds / 3600.0

            if level_diff > 0:  # Water level dropped
                level_diff_total = level_diff
                elapsed_hours_total = elapsed_hours
                rate_pct_per_hr = level_diff_total / elapsed_hours_total
                valid_drop_found = True
                break
            elif level_diff < 0:
                # Water level is rising
                return {
                    "available": False,
                    "message": "Tank water level is currently increasing or refilling.",
                    "rate_percent_per_hour": round(abs(level_diff / elapsed_hours), 2),
                    "rate_litres_per_hour": round(abs((level_diff / 100.0) * tank_capacity / elapsed_hours), 1),
                    "hours_remaining": None,
                    "formatted_time": None,
                    "projected_empty_date": None,
                    "trend": "Refilling"
                }

    if not valid_drop_found or rate_pct_per_hr <= 0.001:
        return {
            "available": False,
            "message": "Water consumption is static. No downward trend detected in recent readings.",
            "rate_percent_per_hour": 0.0,
            "rate_litres_per_hour": 0.0,
            "hours_remaining": None,
            "formatted_time": None,
            "projected_empty_date": None,
            "trend": "Static / No Consumption"
        }

    hours_remaining = round(current_level / rate_pct_per_hr, 1)
    rate_litres = round((rate_pct_per_hr / 100.0) * tank_capacity, 1)
    
    # Format readable time
    hrs = int(hours_remaining)
    mins = int(round((hours_remaining - hrs) * 60))
    if hrs > 0:
        formatted_time = f"{hrs}h {mins}m"
    else:
        formatted_time = f"{mins} minutes"

    projected_date = datetime.now() + timedelta(hours=hours_remaining)

    return {
        "available": True,
        "message": "Calculation based on recent consumption trends.",
        "rate_percent_per_hour": round(rate_pct_per_hr, 2),
        "rate_litres_per_hour": rate_litres,
        "hours_remaining": hours_remaining,
        "formatted_time": formatted_time,
        "projected_empty_date": projected_date.strftime("%d %b %Y, %I:%M %p"),
        "trend": "Consuming"
    }


# ---------- AUTH ROUTES ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both operator username and password.", "danger")
            return render_template("login.html")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            # Session fixation protection: reset session and regenerate CSRF
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["_csrf_token"] = secrets.token_hex(32)
            flash(f"Welcome back, {user['username']}! Operator session active.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid operator username or password.", "danger")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("signup.html")

        # Validate username format and length
        if not re.match(r"^[a-zA-Z0-9_.-]{3,30}$", username):
            flash("Username must be between 3 and 30 characters (letters, numbers, dots, dashes, underscores).", "danger")
            return render_template("signup.html")

        # Validate email if provided
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash("Please provide a valid email address.", "danger")
            return render_template("signup.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("signup.html")

        if len(password) > 128:
            flash("Password must not exceed 128 characters.", "danger")
            return render_template("signup.html")

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("signup.html")

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,)).fetchone()
        if existing:
            flash("Username is already taken. Please choose another.", "danger")
            return render_template("signup.html")

        # Secure password hashing via Werkzeug PBKDF2/scrypt
        hashed_pwd = generate_password_hash(password)
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hashed_pwd)
        )
        new_user_id = cur.lastrowid

        # Initialize default user settings and an initial reading
        db.execute(
            """INSERT INTO user_settings (
                user_id, tank_capacity, low_threshold, high_threshold,
                overflow_threshold, pump_mode, current_pump_state, current_level
            ) VALUES (?, 1000.0, 20.0, 80.0, 95.0, 'Manual', 'OFF', 80.0)""",
            (new_user_id,)
        )
        db.execute(
            "INSERT INTO readings (user_id, level, litres, pump_state, timestamp) VALUES (?, 80.0, 800.0, 'OFF', ?)",
            (new_user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()

        # Session fixation defense
        session.clear()
        session.permanent = True
        session["user_id"] = new_user_id
        session["_csrf_token"] = secrets.token_hex(32)

        flash("Account created successfully! Welcome to AquaPulse.", "success")
        return redirect(url_for("dashboard"))

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out. Operator session terminated.", "info")
    return redirect(url_for("login"))


# ---------- CORE APP ROUTES ----------
@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    db = get_db()
    settings = get_or_create_settings(user_id)

    level = float(settings["current_level"])
    capacity = float(settings["tank_capacity"])
    litres = round(capacity * (level / 100.0), 1)
    pump_state = settings["current_pump_state"]
    pump_mode = settings["pump_mode"]

    status_text, status_class, status_color = get_tank_status(level, settings)

    # Fetch recent readings for table & summary
    readings = db.execute(
        "SELECT * FROM readings WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (user_id,)
    ).fetchall()

    total_readings_count = db.execute(
        "SELECT COUNT(*) FROM readings WHERE user_id = ?",
        (user_id,)
    ).fetchone()[0]

    # Tank empty prediction quick estimate
    prediction = calculate_empty_prediction(user_id, level, capacity)

    return render_template(
        "dashboard.html",
        settings=settings,
        level=level,
        capacity=capacity,
        litres=litres,
        pump_state=pump_state,
        pump_mode=pump_mode,
        status_text=status_text,
        status_class=status_class,
        status_color=status_color,
        readings=readings,
        total_readings_count=total_readings_count,
        prediction=prediction
    )


@app.route("/monitor")
@login_required
def monitor():
    user_id = session["user_id"]
    db = get_db()
    settings = get_or_create_settings(user_id)

    level = float(settings["current_level"])
    capacity = float(settings["tank_capacity"])
    litres = round(capacity * (level / 100.0), 1)
    status_text, status_class, status_color = get_tank_status(level, settings)

    recent_readings = db.execute(
        "SELECT * FROM readings WHERE user_id = ? ORDER BY id DESC LIMIT 5",
        (user_id,)
    ).fetchall()

    return render_template(
        "monitor.html",
        settings=settings,
        level=level,
        capacity=capacity,
        litres=litres,
        pump_state=settings["current_pump_state"],
        pump_mode=settings["pump_mode"],
        status_text=status_text,
        status_class=status_class,
        status_color=status_color,
        recent_readings=recent_readings
    )


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    db = get_db()
    settings = get_or_create_settings(user_id)

    # Optional limit query parameter
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50

    readings = db.execute(
        "SELECT * FROM readings WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()

    total_count = db.execute(
        "SELECT COUNT(*) FROM readings WHERE user_id = ?",
        (user_id,)
    ).fetchone()[0]

    return render_template(
        "history.html",
        readings=readings,
        total_count=total_count,
        limit=limit,
        settings=settings
    )


@app.route("/prediction")
@login_required
def prediction():
    user_id = session["user_id"]
    settings = get_or_create_settings(user_id)

    level = float(settings["current_level"])
    capacity = float(settings["tank_capacity"])
    prediction_data = calculate_empty_prediction(user_id, level, capacity)

    db = get_db()
    recent_readings = db.execute(
        "SELECT * FROM readings WHERE user_id = ? ORDER BY id DESC LIMIT 15",
        (user_id,)
    ).fetchall()

    return render_template(
        "prediction.html",
        prediction=prediction_data,
        settings=settings,
        level=level,
        capacity=capacity,
        recent_readings=recent_readings
    )


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    user_id = session["user_id"]
    db = get_db()
    settings = get_or_create_settings(user_id)

    if request.method == "POST":
        action = request.form.get("action", "thresholds")

        if action == "thresholds":
            try:
                capacity = float(request.form.get("capacity", 1000.0))
                low = float(request.form.get("low_threshold", 20.0))
                high = float(request.form.get("high_threshold", 80.0))
                overflow = float(request.form.get("overflow_threshold", 95.0))
                pump_mode = request.form.get("pump_mode", "Manual")

                if capacity <= 0:
                    flash("Tank capacity must be a positive number.", "danger")
                    return redirect(url_for("settings_page"))

                if not (0 <= low < high < overflow <= 100):
                    flash("Thresholds must follow: 0 ≤ Low < High < Overflow ≤ 100.", "danger")
                    return redirect(url_for("settings_page"))

                current_level = float(settings["current_level"])
                current_pump = settings["current_pump_state"]
                if pump_mode == "Auto":
                    if current_level <= low:
                        current_pump = "ON"
                    elif current_level >= high:
                        current_pump = "OFF"

                db.execute(
                    """UPDATE user_settings SET
                        tank_capacity = ?, low_threshold = ?, high_threshold = ?,
                        overflow_threshold = ?, pump_mode = ?, current_pump_state = ?
                        WHERE user_id = ?""",
                    (capacity, low, high, overflow, pump_mode, current_pump, user_id)
                )
                db.commit()
                flash("Tank calibration and threshold limits successfully updated.", "success")
            except ValueError:
                flash("Invalid numeric value entered.", "danger")

        elif action == "profile":
            email = request.form.get("email", "").strip()
            current_pass = request.form.get("current_password", "")
            new_pass = request.form.get("new_password", "")

            if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                flash("Please provide a valid email address.", "danger")
                return redirect(url_for("settings_page"))

            user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            
            # Update email
            db.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
            db.commit()

            # If changing password
            if new_pass:
                if not current_pass or not check_password_hash(user["password_hash"], current_pass):
                    flash("Current password does not match.", "danger")
                    return redirect(url_for("settings_page"))
                if len(new_pass) < 6:
                    flash("New password must be at least 6 characters.", "danger")
                    return redirect(url_for("settings_page"))

                hashed = generate_password_hash(new_pass)
                db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, user_id))
                db.commit()
                flash("Password updated successfully.", "success")
            else:
                flash("Profile details updated successfully.", "success")

        return redirect(url_for("settings_page"))

    return render_template("settings.html", settings=settings)


# ---------- INTERACTIVE & SIMULATION CONTROLS ----------
@app.route("/level", methods=["POST"])
@login_required
def update_level():
    user_id = session["user_id"]
    settings = get_or_create_settings(user_id)

    try:
        new_level = float(request.form.get("level", 80.0))
        new_level = max(0.0, min(100.0, round(new_level, 1)))
    except ValueError:
        flash("Invalid water level value.", "danger")
        return redirect(url_for("monitor"))

    current_pump = settings["current_pump_state"]
    pump_mode = settings["pump_mode"]

    # Automated pump threshold handling if in Auto mode
    if pump_mode == "Auto":
        low_t = float(settings["low_threshold"])
        high_t = float(settings["high_threshold"])
        if new_level <= low_t and current_pump != "ON":
            current_pump = "ON"
            flash(f"Auto-Pump activated! Water level ({new_level}%) reached low threshold ({low_t}%).", "info")
        elif new_level >= high_t and current_pump != "OFF":
            current_pump = "OFF"
            flash(f"Auto-Pump stopped! Water level ({new_level}%) reached high threshold ({high_t}%).", "info")

    save_reading_record(user_id, new_level, current_pump)
    flash(f"Water level updated to {new_level}% and reading saved.", "success")

    redirect_to = request.form.get("redirect_to", "monitor")
    if redirect_to == "dashboard":
        return redirect(url_for("dashboard"))
    return redirect(url_for("monitor"))


@app.route("/control", methods=["POST"])
@login_required
def pump_control():
    user_id = session["user_id"]
    settings = get_or_create_settings(user_id)

    command = request.form.get("command", "").lower()
    current_level = float(settings["current_level"])
    redirect_to = request.form.get("redirect_to", "dashboard")
    target_endpoint = "monitor" if redirect_to == "monitor" else "dashboard"

    if command == "on":
        new_pump = "ON"
        flash("Pump turned ON (Simulated Hardware Relay Actuated).", "success")
    elif command == "off":
        new_pump = "OFF"
        flash("Pump turned OFF (Simulated Hardware Relay Deactivated).", "info")
    else:
        flash("Invalid pump control command.", "danger")
        return redirect(url_for(target_endpoint))

    save_reading_record(user_id, current_level, new_pump)
    return redirect(url_for(target_endpoint))


@app.route("/mode", methods=["POST"])
@login_required
def change_mode():
    user_id = session["user_id"]
    db = get_db()
    settings = get_or_create_settings(user_id)

    mode = request.form.get("mode", "Manual")
    if mode not in ["Manual", "Auto"]:
        mode = "Manual"

    current_pump = settings["current_pump_state"]
    current_level = float(settings["current_level"])

    # If switching to Auto, immediately evaluate current thresholds
    if mode == "Auto":
        low_t = float(settings["low_threshold"])
        high_t = float(settings["high_threshold"])
        if current_level <= low_t:
            current_pump = "ON"
        elif current_level >= high_t:
            current_pump = "OFF"

    db.execute(
        "UPDATE user_settings SET pump_mode = ?, current_pump_state = ? WHERE user_id = ?",
        (mode, current_pump, user_id)
    )
    db.commit()

    # Save a reading reflecting current pump condition
    save_reading_record(user_id, current_level, current_pump)

    flash(f"Pump control mode switched to {mode}.", "success")
    redirect_to = request.form.get("redirect_to", "monitor")
    if redirect_to == "dashboard":
        return redirect(url_for("dashboard"))
    return redirect(url_for("monitor"))


# ---------- CSV EXPORT ----------
@app.route("/export")
@app.route("/export/csv")
@login_required
def export_csv():
    user_id = session["user_id"]
    db = get_db()
    settings = get_or_create_settings(user_id)

    readings = db.execute(
        "SELECT id, timestamp, level, litres, pump_state FROM readings WHERE user_id = ? ORDER BY id ASC",
        (user_id,)
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Reading ID",
        "Timestamp",
        "Water Level (%)",
        "Volume (Litres)",
        "Tank Capacity (Litres)",
        "Pump State",
        "Threshold Status"
    ])

    for r in readings:
        status_text, _, _ = get_tank_status(r["level"], settings)
        writer.writerow([
            r["id"],
            r["timestamp"],
            r["level"],
            r["litres"],
            settings["tank_capacity"],
            r["pump_state"],
            status_text
        ])

    filename = f"aquapulse_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ---------- JSON API FOR CHART.JS & TELEMETRY ----------
@app.route("/api/history")
@login_required
def api_history():
    user_id = session["user_id"]
    db = get_db()
    limit = request.args.get("limit", 20, type=int)

    rows = db.execute(
        "SELECT id, level, litres, pump_state, timestamp FROM readings WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()

    # Reverse to chronological order for charts
    chronological = list(reversed(rows))
    return jsonify({
        "labels": [r["timestamp"] for r in chronological],
        "levels": [r["level"] for r in chronological],
        "litres": [r["litres"] for r in chronological],
        "pumps": [r["pump_state"] for r in chronological]
    })


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
