import sqlite3
from datetime import datetime, timedelta
import random
from pathlib import Path
import os
import uuid
from typing import Optional

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "musicportal.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me"
_db_initialized = False

UPLOAD_DIR = BASE_DIR / "static" / "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def log_admin_action(action: str):
    if g.user is None or g.user["role"] != "admin":
        return
    today = datetime.now().strftime("%d-%m-%Y")
    filename = f"{today}-log.txt"
    log_path = BASE_DIR / filename
    timestamp = datetime.now().strftime("%H:%M:%S")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] Admin: {g.user['username']} (ID: {g.user['id']}) - {action}\n")
    except Exception as e:
        print(f"Logging failed: {e}")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error: Optional[BaseException]):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    
    # Migration: Check if users table needs update to include 'admin' role
    try:
        schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        if schema and "CHECK(role IN ('band', 'fan'))" in schema["sql"]:
            db.execute("PRAGMA foreign_keys=OFF")
            db.execute("ALTER TABLE users RENAME TO users_old")
            db.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('band', 'fan', 'admin'))
                )
            """)
            db.execute("INSERT INTO users (id, username, password_hash, role) SELECT id, username, password_hash, role FROM users_old")
            db.execute("DROP TABLE users_old")
            db.commit()
    except sqlite3.Error:
        pass

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('band', 'fan', 'admin'))
        );

        CREATE TABLE IF NOT EXISTS concerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_name TEXT NOT NULL,
            concert_datetime TEXT NOT NULL,
            venue TEXT NOT NULL,
            city TEXT,
            cost TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'cancelled', 'full')),
            image_filename TEXT,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS selected_concerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            concert_id INTEGER NOT NULL,
            UNIQUE(user_id, concert_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(concert_id) REFERENCES concerts(id)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concert_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            qty INTEGER NOT NULL CHECK(qty > 0),
            purchased_at TEXT NOT NULL,
            FOREIGN KEY(concert_id) REFERENCES concerts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    try:
        cols = db.execute("PRAGMA table_info(users)").fetchall()
        col_names = {c[1] for c in cols}
        if "email" not in col_names:
            db.execute("ALTER TABLE users ADD COLUMN email TEXT")
            db.commit()
        if "profile_image" not in col_names:
            db.execute("ALTER TABLE users ADD COLUMN profile_image TEXT")
            db.commit()
    except sqlite3.Error:
        pass

    try:
        cols = db.execute("PRAGMA table_info(concerts)").fetchall()
        col_names = {c[1] for c in cols}
        if "image_filename" not in col_names:
            db.execute("ALTER TABLE concerts ADD COLUMN image_filename TEXT")
            db.commit()
        if "city" not in col_names:
            db.execute("ALTER TABLE concerts ADD COLUMN city TEXT")
            db.commit()
        if "max_tickets" not in col_names:
            db.execute("ALTER TABLE concerts ADD COLUMN max_tickets INTEGER DEFAULT 100")
            db.commit()
        if "ticket_price" not in col_names:
            db.execute("ALTER TABLE concerts ADD COLUMN ticket_price REAL DEFAULT 0.0")
            db.commit()
            # Migrate cost to ticket_price
            rows = db.execute("SELECT id, cost FROM concerts").fetchall()
            for row in rows:
                try:
                    price = float(row["cost"].replace("$", "").strip())
                    db.execute("UPDATE concerts SET ticket_price = ? WHERE id = ?", (price, row["id"]))
                except:
                    pass
            db.commit()
    except sqlite3.Error:
        pass
    try:
        cities = [
            "London", "Manchester", "Birmingham", "Liverpool", "Leeds", "Bristol",
            "Glasgow", "Edinburgh", "Cardiff", "Belfast"
        ]
        missing = db.execute("SELECT id FROM concerts WHERE city IS NULL OR city = ''").fetchall()
        for row in missing:
            city = random.choice(cities)
            db.execute("UPDATE concerts SET city = ? WHERE id = ?", (city, row["id"]))
        db.commit()
    except sqlite3.Error:
        pass
    try:
        if not db.execute("SELECT 1 FROM users WHERE username='admin' AND role='admin'").fetchone():
            db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
                ("admin", generate_password_hash("1234")),
            )
            db.commit()
    except sqlite3.Error:
        pass
    try:
        count = db.execute("SELECT COUNT(*) as c FROM users WHERE role='band'").fetchone()[0]
        demo_bands = [
            "AquaTide", "BlueEcho", "CadenceCrew", "DeltaRiffs", "EchoNova", "FuzzFactory",
            "GoldenChords", "HarmonicHaze", "IndigoPulse", "JadeGroove", "KineticKeys",
            "LunarLicks", "MoonlitMuse", "NeonNoir", "OpalOrchestra", "PrismPulse",
            "QuasarQuartet", "RubyRhythm", "SolarSound", "TopazTempo", "Ultravox", "VioletVibe",
            "WaveWanderers", "XenonXylos", "YellowYodel", "ZenithZing"
        ]
        if count < 18:
            for name in demo_bands:
                if not db.execute("SELECT 1 FROM users WHERE username=?", (name,)).fetchone():
                    db.execute(
                        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'band')",
                        (name, generate_password_hash("demo123")),
                    )
            db.commit()
        venues = [
            "City Hall", "Riverside Arena", "Sunset Club", "Neon Dome", "Aurora Theater",
            "Echo Park Stage", "Harbor Lights", "Skyline Loft", "Indigo Lounge", "Velvet Room"
        ]
        cities = [
            "London", "Manchester", "Birmingham", "Liverpool", "Leeds", "Bristol",
            "Glasgow", "Edinburgh", "Cardiff", "Belfast"
        ]
        now = datetime.now()
        band_rows = db.execute("SELECT id, username FROM users WHERE role='band'").fetchall()
        for row in band_rows:
            uid, uname = row["id"], row["username"]
            c_count = db.execute("SELECT COUNT(*) FROM concerts WHERE user_id=?", (uid,)).fetchone()[0]
            if c_count == 0:
                past_dt = (now - timedelta(days=random.randint(20, 180))).replace(minute=0, second=0, microsecond=0)
                future_dt = (now + timedelta(days=random.randint(5, 120))).replace(minute=0, second=0, microsecond=0)
                maybe_future_2 = (now + timedelta(days=random.randint(121, 260))).replace(minute=0, second=0, microsecond=0)
                samples = [
                    (uname, past_dt.strftime("%Y-%m-%dT%H:%M"), random.choice(venues), random.choice(cities), f"${random.randint(15,60)}", random.choice(["scheduled", "full"])) ,
                    (uname, future_dt.strftime("%Y-%m-%dT%H:%M"), random.choice(venues), random.choice(cities), f"${random.randint(20,70)}", "scheduled"),
                ]
                if random.random() < 0.5:
                    samples.append((uname, maybe_future_2.strftime("%Y-%m-%dT%H:%M"), random.choice(venues), random.choice(cities), f"${random.randint(25,80)}", "scheduled"))
                for band_name, dt, venue, city, cost, status in samples:
                    db.execute(
                        "INSERT INTO concerts (band_name, concert_datetime, venue, city, cost, status, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (band_name, dt, venue, city, cost, status, uid),
                    )
        db.commit()
    except sqlite3.Error:
        pass
    db.commit()


@app.before_request
def ensure_db_ready():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if g.user is None:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        file = request.files.get("profile_image")
        
        db = get_db()
        new_filename = g.user["profile_image"]
        
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Unsupported image type.")
            else:
                filename = secure_filename(file.filename)
                ext = filename.rsplit(".", 1)[1].lower()
                unique_name = f"user_{g.user['id']}_{uuid.uuid4().hex}.{ext}"
                file.save(str(UPLOAD_DIR / unique_name))
                new_filename = unique_name
        
        try:
            db.execute("UPDATE users SET email = ?, profile_image = ? WHERE id = ?", (email, new_filename, g.user["id"]))
            db.commit()
            flash("Profile updated.")
        except sqlite3.Error:
            flash("Error updating profile.")
            
        return redirect(url_for("settings"))
        
    return render_template("settings.html")

@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
def admin_edit_user(user_id: int):
    if g.user is None or g.user["role"] != "admin":
        flash("Admin access required.")
        return redirect(url_for("login"))
        
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        flash("User not found.")
        return redirect(url_for("admin_users"))
        
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        role = request.form.get("role")
        password = request.form.get("password", "")
        file = request.files.get("profile_image")
        
        if not username or not role:
            flash("Username and role are required.")
        else:
            new_filename = user["profile_image"]
            if file and file.filename:
                if not allowed_file(file.filename):
                    flash("Unsupported image type.")
                else:
                    filename = secure_filename(file.filename)
                    ext = filename.rsplit(".", 1)[1].lower()
                    unique_name = f"user_{user_id}_{uuid.uuid4().hex}.{ext}"
                    file.save(str(UPLOAD_DIR / unique_name))
                    new_filename = unique_name
            
            try:
                if password:
                    db.execute(
                        "UPDATE users SET username = ?, email = ?, role = ?, profile_image = ?, password_hash = ? WHERE id = ?", 
                        (username, email, role, new_filename, generate_password_hash(password), user_id)
                    )
                    log_admin_action(f"Updated user {user_id} (username: {username}, role: {role}, password changed)")
                else:
                    db.execute(
                        "UPDATE users SET username = ?, email = ?, role = ?, profile_image = ? WHERE id = ?", 
                        (username, email, role, new_filename, user_id)
                    )
                    log_admin_action(f"Updated user {user_id} (username: {username}, role: {role})")
                
                db.commit()
                flash("User updated.")
                return redirect(url_for("admin_users"))
            except sqlite3.IntegrityError:
                flash("Username already taken.")
            except sqlite3.Error:
                flash("Error updating user.")
                
    return render_template("admin_user_edit.html", user=user)

@app.route("/")
def index():
    if g.user is not None and g.user["role"] == "band":
        return redirect(url_for("band_dashboard"))
    return render_discover()


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role")
        db = get_db()

        error = None
        if not username or not password:
            error = "Username and password are required."
        elif role not in {"band", "fan"}:
            error = "Please choose a role."
        elif db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
            error = "User already exists."

        if error is None:
            db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (username, email, generate_password_hash(password), role),
            )
            db.commit()
            flash("Account created. Please log in.")
            return redirect(url_for("login"))
        flash(error)
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        error = None
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Invalid credentials."
        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back!")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("index"))
        flash(error)
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("index"))


def band_required():
    if g.user is None or g.user["role"] != "band":
        flash("Band access required.")
        return False
    return True


def fan_required():
    if g.user is None or g.user["role"] != "fan":
        flash("Fan access required.")
        return False
    return True

def admin_required():
    if g.user is None or g.user["role"] != "admin":
        flash("Admin access required.")
        return False
    return True


def fetch_concerts(band_query: str, date_query: Optional[str], status_filter: str, city_query: Optional[str] = None):
    db = get_db()
    query = (
        "SELECT concerts.*, users.username FROM concerts "
        "JOIN users ON concerts.user_id = users.id WHERE 1=1"
    )
    params = []
    if band_query:
        query += " AND band_name LIKE ?"
        params.append(f"%{band_query}%")
    if date_query:
        try:
            datetime.strptime(date_query, "%Y-%m-%d")
            query += " AND date(concert_datetime) = date(?)"
            params.append(date_query)
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.")
    if status_filter in {"scheduled", "cancelled", "full"}:
        query += " AND status = ?"
        params.append(status_filter)
    if city_query:
        query += " AND (city = ? OR city LIKE ?)"
        params.extend([city_query, f"%{city_query}%"])
    query += " ORDER BY datetime(concert_datetime) ASC, band_name COLLATE NOCASE ASC"
    return get_db().execute(query, params).fetchall()


def selected_ids_for_user(user_id: int):
    db = get_db()
    selected = db.execute(
        "SELECT concert_id FROM selected_concerts WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {row["concert_id"] for row in selected}


def render_discover():
    band_query = request.args.get("band", "").strip()
    date_query = request.args.get("date")
    status_filter = request.args.get("status", "")
    city_query = request.args.get("city", "").strip()
    concerts = fetch_concerts(band_query, date_query, status_filter, city_query or None)
    db = get_db()
    band_rows = db.execute(
        "SELECT username, profile_image FROM users WHERE role='band' ORDER BY username COLLATE NOCASE"
    ).fetchall()
    # bands = [r["username"] for r in band_rows] # Old way
    bands = band_rows # Pass the rows directly
    selected_ids = set()
    if g.user is not None and g.user["role"] == "fan":
        selected_ids = selected_ids_for_user(g.user["id"])
    return render_template(
        "search.html",
        concerts=concerts,
        bands=bands,
        city_query=city_query,
        band_query=band_query,
        date_query=date_query,
        status_filter=status_filter,
        selected_ids=selected_ids,
    )


@app.route("/artists/<username>")
def artist_concerts(username: str):
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE role='band' AND username = ? COLLATE NOCASE",
        (username,),
    ).fetchone()
    if not user:
        flash("Artist not found.")
        return redirect(url_for("search_concerts"))
    rows = db.execute(
        "SELECT * FROM concerts WHERE user_id = ? ORDER BY concert_datetime DESC",
        (user["id"],),
    ).fetchall()

    def parse_dt(s: str):
        try:
            return datetime.fromisoformat(s)
        except Exception:
            try:
                return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

    now = datetime.now()
    concerts = []
    for r in rows:
        dt = parse_dt(r["concert_datetime"]) or now
        concerts.append({**dict(r), "archived": dt < now})

    selected_ids = set()
    if g.user is not None and g.user["role"] == "fan":
        selected_ids = selected_ids_for_user(g.user["id"])

    return render_template("artist_concerts.html", artist=user, concerts=concerts, selected_ids=selected_ids)


@app.route("/band")
def band_dashboard():
    if not band_required():
        return redirect(url_for("login"))
    db = get_db()
    concerts = db.execute(
        "SELECT * FROM concerts WHERE user_id = ? ORDER BY concert_datetime",
        (g.user["id"],),
    ).fetchall()
    return render_template("band_dashboard.html", concerts=concerts)


@app.route("/concerts/new", methods=["GET", "POST"])
def create_concert():
    if not band_required():
        return redirect(url_for("login"))
    if request.method == "POST":
        band_name = request.form.get("band_name", "").strip()
        date_time = request.form.get("concert_datetime")
        venue = request.form.get("venue", "").strip()
        city = request.form.get("city", "").strip()
        cost = request.form.get("cost", "").strip()
        max_tickets = request.form.get("max_tickets", "100")
        ticket_price = request.form.get("ticket_price", "0")
        # Status is always scheduled initially
        status = "scheduled"
        file = request.files.get("image")
        error = None
        if not band_name or not date_time or not venue or not city or not cost:
            error = "All fields are required."
        if error is None:
            db = get_db()
            saved_filename = None
            if file and file.filename:
                if not allowed_file(file.filename):
                    flash("Unsupported image type. Use PNG/JPG/GIF/WEBP.")
                    return render_template("concert_form.html", concert=None)
                filename = secure_filename(file.filename)
                ext = filename.rsplit(".", 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}.{ext}"
                file.save(str(UPLOAD_DIR / unique_name))
                saved_filename = unique_name
            db.execute(
                "INSERT INTO concerts (band_name, concert_datetime, venue, city, cost, max_tickets, ticket_price, status, image_filename, user_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (band_name, date_time, venue, city, cost, max_tickets, ticket_price, status, saved_filename, g.user["id"]),
            )
            db.commit()
            flash("Concert created.")
            return redirect(url_for("band_dashboard"))
        flash(error)
    return render_template("concert_form.html", concert=None)


@app.route("/concerts/<int:concert_id>/edit", methods=["GET", "POST"])
def edit_concert(concert_id: int):
    if g.user is None:
        return redirect(url_for("login"))
    
    # Allow band to edit own concerts, or admin to edit any
    is_admin = (g.user["role"] == "admin")
    is_band = (g.user["role"] == "band")
    
    if not (is_admin or is_band):
        flash("Access denied.")
        return redirect(url_for("index"))

    db = get_db()
    concert = db.execute("SELECT * FROM concerts WHERE id = ?", (concert_id,)).fetchone()
    
    if concert is None:
        flash("Concert not found.")
        return redirect(url_for("index"))

    # If not admin, check ownership
    if not is_admin and concert["user_id"] != g.user["id"]:
        flash("You can only edit your own concerts.")
        return redirect(url_for("band_dashboard"))

    if request.method == "POST":
        band_name = request.form.get("band_name", "").strip()
        date_time = request.form.get("concert_datetime")
        venue = request.form.get("venue", "").strip()
        city = request.form.get("city", "").strip()
        cost = request.form.get("cost", "").strip()
        max_tickets = request.form.get("max_tickets", "100")
        ticket_price = request.form.get("ticket_price", "0")
        
        # Only allow toggling between scheduled and cancelled
        status_input = request.form.get("status", "scheduled")
        if status_input not in {"scheduled", "cancelled"}:
            status_input = "scheduled"
            
        file = request.files.get("image")
        error = None
        if not band_name or not date_time or not venue or not city or not cost:
            error = "All fields are required."
        if error is None:
            new_filename = concert["image_filename"]
            if file and file.filename:
                if not allowed_file(file.filename):
                    flash("Unsupported image type. Use PNG/JPG/GIF/WEBP.")
                    return render_template("concert_form.html", concert=concert)
                filename = secure_filename(file.filename)
                ext = filename.rsplit(".", 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}.{ext}"
                file.save(str(UPLOAD_DIR / unique_name))
                new_filename = unique_name
            
            # Recalculate status if setting to scheduled
            final_status = status_input
            if final_status == "scheduled":
                # Check if actually full
                sold = db.execute("SELECT COALESCE(SUM(qty), 0) FROM tickets WHERE concert_id = ?", (concert_id,)).fetchone()[0]
                try:
                    mt = int(max_tickets)
                except:
                    mt = 100
                if sold >= mt:
                    final_status = "full"

            db.execute(
                "UPDATE concerts SET band_name = ?, concert_datetime = ?, venue = ?, city = ?, cost = ?, max_tickets = ?, ticket_price = ?, status = ?, image_filename = ?"
                " WHERE id = ?",
                (band_name, date_time, venue, city, cost, max_tickets, ticket_price, final_status, new_filename, concert_id),
            )
            db.commit()
            
            if is_admin:
                log_admin_action(f"Edited concert {concert_id} (status: {final_status})")
            
            flash("Concert updated.")
            if is_admin:
                return redirect(url_for("admin_concerts"))
            return redirect(url_for("band_dashboard"))
        flash(error)
    return render_template("concert_form.html", concert=concert)


@app.route("/concerts")
def search_concerts():
    if g.user is not None and g.user["role"] == "band":
        return redirect(url_for("band_dashboard"))
    return render_discover()

@app.route("/admin")
def admin_dashboard():
    if g.user is None or g.user["role"] != "admin":
        flash("Admin access required.")
        return redirect(url_for("login"))
    return render_template("admin_dashboard.html")

@app.route("/admin/users")
def admin_users():
    if g.user is None or g.user["role"] != "admin":
        flash("Admin access required.")
        return redirect(url_for("login"))
    db = get_db()
    q = request.args.get("q", "").strip()
    users = db.execute(
        "SELECT id, username, role, profile_image FROM users WHERE username LIKE ? ORDER BY role DESC, username COLLATE NOCASE",
        (f"%{q}%",),
    ).fetchall()
    return render_template("admin_users.html", users=users, q=q)

@app.route("/admin/concerts")
def admin_concerts():
    if g.user is None or g.user["role"] != "admin":
        flash("Admin access required.")
        return redirect(url_for("login"))
    db = get_db()
    q = request.args.get("q", "").strip()
    concerts = db.execute(
        """
        SELECT c.*, u.username, 
        (SELECT COUNT(*) FROM tickets t WHERE t.concert_id = c.id) as sold_count
        FROM concerts c 
        JOIN users u ON c.user_id=u.id 
        WHERE c.band_name LIKE ? OR c.venue LIKE ? OR c.city LIKE ?
        ORDER BY datetime(c.concert_datetime) ASC, c.band_name COLLATE NOCASE ASC
        """,
        (f"%{q}%", f"%{q}%", f"%{q}%"),
    ).fetchall()
    return render_template("admin_concerts.html", concerts=concerts, q=q)

@app.route("/admin/users/<int:user_id>/delete", methods=["POST"]) 
def admin_delete_user(user_id:int):
    if g.user is None or g.user["role"] != "admin":
        flash("Admin access required.")
        return redirect(url_for("login"))
    db = get_db()
    try:
        db.execute("DELETE FROM selected_concerts WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM concerts WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM users WHERE id=?", (user_id,))
        db.commit()
        log_admin_action(f"Deleted user {user_id}")
        flash("User deleted.")
    except sqlite3.Error:
        flash("Unable to delete user.")
    return redirect(url_for("admin_users"))

@app.route("/admin/concerts/<int:concert_id>/delete", methods=["POST"]) 
def admin_delete_concert(concert_id:int):
    if g.user is None or g.user["role"] != "admin":
        flash("Admin access required.")
        return redirect(url_for("login"))
    db = get_db()
    try:
        db.execute("DELETE FROM selected_concerts WHERE concert_id=?", (concert_id,))
        db.execute("DELETE FROM concerts WHERE id=?", (concert_id,))
        db.commit()
        log_admin_action(f"Deleted concert {concert_id}")
        flash("Concert deleted.")
    except sqlite3.Error:
        flash("Unable to delete concert.")
    return redirect(url_for("admin_concerts"))

@app.route("/admin/concerts/<int:concert_id>/status", methods=["POST"]) 
def admin_update_status(concert_id:int):
    if g.user is None or g.user["role"] != "admin":
        flash("Admin access required.")
        return redirect(url_for("login"))
    status = request.form.get("status", "scheduled")
    if status not in {"scheduled","cancelled","full"}:
        flash("Invalid status.")
        return redirect(url_for("admin_concerts"))
    db = get_db()
    try:
        db.execute("UPDATE concerts SET status=? WHERE id=?", (status, concert_id))
        db.commit()
        log_admin_action(f"Updated concert {concert_id} status to {status}")
        flash("Status updated.")
    except sqlite3.Error:
        flash("Unable to update status.")
    return redirect(url_for("admin_concerts"))


@app.route("/selected")
def selected_concerts_view():
    if not fan_required():
        return redirect(url_for("login"))
    db = get_db()
    concerts = db.execute(
        """
        SELECT concerts.* FROM selected_concerts
        JOIN concerts ON concerts.id = selected_concerts.concert_id
        WHERE selected_concerts.user_id = ?
        ORDER BY concert_datetime
        """,
        (g.user["id"],),
    ).fetchall()
    return render_template("selected.html", concerts=concerts)


@app.route("/selected/add/<int:concert_id>", methods=["POST"])
def add_selected(concert_id: int):
    if not fan_required():
        return redirect(url_for("login"))
    db = get_db()
    concert = db.execute("SELECT id FROM concerts WHERE id = ?", (concert_id,)).fetchone()
    if concert is None:
        flash("Concert not found.")
        return redirect(url_for("search_concerts"))
    try:
        db.execute(
            "INSERT OR IGNORE INTO selected_concerts (user_id, concert_id) VALUES (?, ?)",
            (g.user["id"], concert_id),
        )
        db.commit()
        flash("Added to Selected Concerts.")
    except sqlite3.Error:
        flash("Unable to add concert.")
    return redirect(request.referrer or url_for("search_concerts"))


@app.route("/selected/remove/<int:concert_id>", methods=["POST"])
def remove_selected(concert_id: int):
    if not fan_required():
        return redirect(url_for("login"))
    db = get_db()
    db.execute(
        "DELETE FROM selected_concerts WHERE user_id = ? AND concert_id = ?",
        (g.user["id"], concert_id),
    )
    db.commit()
    flash("Removed from Selected Concerts.")
    return redirect(request.referrer or url_for("selected_concerts_view"))


@app.route("/concert/<int:concert_id>")
def view_concert(concert_id: int):
    db = get_db()
    concert = db.execute("SELECT * FROM concerts WHERE id = ?", (concert_id,)).fetchone()
    if concert is None:
        flash("Concert not found.")
        return redirect(url_for("search_concerts"))
    
    sold = db.execute("SELECT COALESCE(SUM(qty), 0) FROM tickets WHERE concert_id = ?", (concert_id,)).fetchone()[0]
    remaining = concert["max_tickets"] - sold
    
    return render_template("concert_detail.html", concert=concert, remaining=remaining)


@app.route("/buy/<int:concert_id>", methods=["POST"])
def buy_ticket(concert_id: int):
    if not fan_required():
        return redirect(url_for("login"))
    
    try:
        qty = int(request.form.get("qty", 1))
    except ValueError:
        qty = 1

    if qty < 1:
        flash("Invalid quantity.")
        return redirect(url_for("view_concert", concert_id=concert_id))
        
    db = get_db()
    concert = db.execute("SELECT * FROM concerts WHERE id = ?", (concert_id,)).fetchone()
    if not concert:
        flash("Concert not found.")
        return redirect(url_for("search_concerts"))
        
    sold = db.execute("SELECT COALESCE(SUM(qty), 0) FROM tickets WHERE concert_id = ?", (concert_id,)).fetchone()[0]
    remaining = concert["max_tickets"] - sold
    
    if concert["status"] == "cancelled":
        flash("Concert is cancelled.")
        return redirect(url_for("view_concert", concert_id=concert_id))
        
    if remaining <= 0:
        flash("Sold out.")
        return redirect(url_for("view_concert", concert_id=concert_id))
        
    to_buy = min(qty, remaining)
    
    db.execute(
        "INSERT INTO tickets (concert_id, user_id, qty, purchased_at) VALUES (?, ?, ?, datetime('now'))",
        (concert_id, g.user["id"], to_buy)
    )
    
    # Check if sold out after purchase
    new_sold = sold + to_buy
    if new_sold >= concert["max_tickets"]:
        db.execute("UPDATE concerts SET status = 'full' WHERE id = ?", (concert_id,))
        
    db.commit()
    
    if to_buy < qty:
        flash(f"Partial purchase. Only {to_buy} tickets were available.")
    else:
        flash("Purchase complete!")
        
    return redirect(url_for("tickets_bought"))


@app.route("/fan-dashboard/tickets-bought")
def tickets_bought():
    if not fan_required():
        return redirect(url_for("login"))
        
    db = get_db()
    tickets = db.execute("""
        SELECT t.*, c.band_name, c.concert_datetime, c.venue, c.city, c.image_filename 
        FROM tickets t
        JOIN concerts c ON t.concert_id = c.id
        WHERE t.user_id = ?
        ORDER BY c.concert_datetime
    """, (g.user["id"],)).fetchall()
    
    return render_template("tickets_bought.html", tickets=tickets)


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
