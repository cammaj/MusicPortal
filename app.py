import sqlite3
from datetime import datetime
from pathlib import Path
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

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "musicportal.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me"
_db_initialized = False


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
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('band', 'fan'))
        );

        CREATE TABLE IF NOT EXISTS concerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            band_name TEXT NOT NULL,
            concert_datetime TEXT NOT NULL,
            venue TEXT NOT NULL,
            cost TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'cancelled', 'full')),
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
        """
    )
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


@app.route("/")
def index():
    if g.user is None:
        return render_template("index.html")
    if g.user["role"] == "band":
        return redirect(url_for("band_dashboard"))
    return redirect(url_for("search_concerts"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
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
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), role),
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
        cost = request.form.get("cost", "").strip()
        status = request.form.get("status", "scheduled")
        error = None
        if not band_name or not date_time or not venue or not cost:
            error = "All fields are required."
        if error is None:
            db = get_db()
            db.execute(
                "INSERT INTO concerts (band_name, concert_datetime, venue, cost, status, user_id)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (band_name, date_time, venue, cost, status, g.user["id"]),
            )
            db.commit()
            flash("Concert created.")
            return redirect(url_for("band_dashboard"))
        flash(error)
    return render_template("concert_form.html", concert=None)


@app.route("/concerts/<int:concert_id>/edit", methods=["GET", "POST"])
def edit_concert(concert_id: int):
    if not band_required():
        return redirect(url_for("login"))
    db = get_db()
    concert = db.execute("SELECT * FROM concerts WHERE id = ?", (concert_id,)).fetchone()
    if concert is None or concert["user_id"] != g.user["id"]:
        flash("You can only edit your own concerts.")
        return redirect(url_for("band_dashboard"))
    if request.method == "POST":
        band_name = request.form.get("band_name", "").strip()
        date_time = request.form.get("concert_datetime")
        venue = request.form.get("venue", "").strip()
        cost = request.form.get("cost", "").strip()
        status = request.form.get("status", "scheduled")
        error = None
        if not band_name or not date_time or not venue or not cost:
            error = "All fields are required."
        if error is None:
            db.execute(
                "UPDATE concerts SET band_name = ?, concert_datetime = ?, venue = ?, cost = ?, status = ?"
                " WHERE id = ?",
                (band_name, date_time, venue, cost, status, concert_id),
            )
            db.commit()
            flash("Concert updated.")
            return redirect(url_for("band_dashboard"))
        flash(error)
    return render_template("concert_form.html", concert=concert)


@app.route("/concerts")
def search_concerts():
    db = get_db()
    band_query = request.args.get("band", "").strip()
    date_query = request.args.get("date")
    status_filter = request.args.get("status", "")
    query = "SELECT concerts.*, users.username FROM concerts JOIN users ON concerts.user_id = users.id WHERE 1=1"
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
    query += " ORDER BY concert_datetime"
    concerts = db.execute(query, params).fetchall()
    selected_ids = set()
    if g.user is not None and g.user["role"] == "fan":
        selected = db.execute(
            "SELECT concert_id FROM selected_concerts WHERE user_id = ?",
            (g.user["id"],),
        ).fetchall()
        selected_ids = {row["concert_id"] for row in selected}
    return render_template(
        "search.html",
        concerts=concerts,
        band_query=band_query,
        date_query=date_query,
        status_filter=status_filter,
        selected_ids=selected_ids,
    )


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
    return redirect(url_for("search_concerts"))


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
    return redirect(url_for("selected_concerts_view"))


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
