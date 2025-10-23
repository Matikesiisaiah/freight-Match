# app.py
# Single-file Load Board (Flask + SQLite + inline HTML/CSS)
# Run:  pip install -r requirements.txt
# Then: python app.py  -> http://127.0.0.1:5000
#
# Default admin (created on first run):
#   email: admin@demo.com
#   pass : admin123

import sqlite3, os, re, datetime
from functools import wraps
from flask import Flask, g, request, redirect, url_for, session, abort, flash, send_from_directory
from flask import render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

APP_TITLE = "SwiftLoad Board"
DB_PATH   = "loadboard.db"
SECRET    = "change-this-secret"

app = Flask(__name__)
app.secret_key = SECRET

# ---------------------------- DB HELPERS ----------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    PRAGMA foreign_keys=ON;

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT CHECK(role IN ('shipper','trucker','admin')) NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        company TEXT,
        phone TEXT,
        mc_number TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS loads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shipper_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        pickup_city TEXT NOT NULL,
        pickup_state TEXT,
        pickup_date TEXT,
        delivery_city TEXT NOT NULL,
        delivery_state TEXT,
        delivery_date TEXT,
        weight REAL,
        equipment TEXT,
        rate REAL,
        notes TEXT,
        status TEXT CHECK(status IN ('open','assigned','in_transit','delivered','cancelled')) DEFAULT 'open',
        trucker_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shipper_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (trucker_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS bids (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        load_id INTEGER NOT NULL,
        trucker_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        message TEXT,
        status TEXT CHECK(status IN ('pending','accepted','rejected')) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (load_id) REFERENCES loads(id) ON DELETE CASCADE,
        FOREIGN KEY (trucker_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        load_id INTEGER,
        body TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (load_id) REFERENCES loads(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS saved_loads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        load_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, load_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (load_id) REFERENCES loads(id) ON DELETE CASCADE
    );
    """)
    # Seed admin
    cur = db.execute("SELECT id FROM users WHERE email=?", ("admin@demo.com",))
    if not cur.fetchone():
        db.execute(
            "INSERT INTO users(role,name,email,password_hash,company,phone) VALUES(?,?,?,?,?,?)",
            ("admin","Administrator","admin@demo.com", generate_password_hash("admin123"), "SwiftLoad LLC","+000000000")
        )
    db.commit()

if not os.path.exists(DB_PATH):
    with app.app_context():
        init_db()

# ---------------------------- AUTH DECORATORS ----------------------------
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrap

def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrap(*a, **k):
            if "user_id" not in session: return redirect(url_for("login", next=request.path))
            if session.get("role") not in roles and session.get("role")!="admin":
                abort(403)
            return f(*a, **k)
        return wrap
    return deco

# ---------------------------- HTML SHELL ----------------------------
BASE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title or APP_TITLE }}</title>
<style>
:root{--bg:#0f1221;--card:#171a2b;--muted:#9aa3b2;--acc:#7c5cff;--acc2:#22c55e;--danger:#ef4444;--text:#e5e7eb}
*{box-sizing:border-box}
body{margin:0;font-family:Inter,system-ui,Segoe UI,Roboto,Arial,sans-serif;background:linear-gradient(180deg,#0b0e1a, #0f1221);color:var(--text)}
a{color:var(--acc);text-decoration:none}
.container{max-width:1100px;margin:0 auto;padding:20px}
.nav{display:flex;gap:14px;align-items:center;justify-content:space-between;margin:8px 0 20px}
.logo{font-weight:800;letter-spacing:.3px}
.btn{display:inline-block;padding:10px 14px;border-radius:12px;background:var(--acc);color:white;border:0;cursor:pointer;font-weight:600}
.btn-light{background:#2a2f45}
.btn-success{background:var(--acc2)}
.btn-danger{background:var(--danger)}
.btn-sm{padding:6px 10px;border-radius:10px;font-size:.9rem}
.grid{display:grid;gap:16px}
.grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}
.grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}
.card{background:var(--card);border:1px solid #262a40;border-radius:18px;padding:18px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
input,select,textarea{width:100%;padding:12px 13px;background:#0f1327;color:var(--text);border:1px solid #2b3150;border-radius:12px;outline:none}
label{font-size:.9rem;color:var(--muted);display:block;margin:6px 0}
.badge{padding:4px 8px;border-radius:10px;background:#29304a;color:#cfd6e6;font-size:.8rem}
.table{width:100%;border-collapse:collapse;margin-top:8px}
.table th,.table td{padding:10px;border-bottom:1px solid #2b3150;text-align:left}
.flex{display:flex;gap:10px;align-items:center}
.right{margin-left:auto}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.kpi{background:#121633;padding:14px;border:1px solid #2b3150;border-radius:16px}
.flash{background:#142036;border:1px solid #24406e;color:#cfe2ff;padding:10px;border-radius:10px;margin-bottom:12px}
hr{border:0;border-top:1px solid #2b3150;margin:16px 0}
footer{color:#8b93a7;font-size:.85rem;margin-top:24px;text-align:center}
@media (max-width:900px){.grid-3{grid-template-columns:1fr}.grid-2{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="container">
  <div class="nav">
    <div class="flex" style="gap:12px">
      <a href="{{ url_for('home') }}" class="logo">🚚 {{ APP_TITLE }}</a>
      <a href="{{ url_for('loads') }}">Loads</a>
      {% if session.get('role') in ['shipper','admin'] %}<a href="{{ url_for('new_load') }}">Post Load</a>{% endif %}
      {% if session.get('role') in ['trucker','admin'] %}<a href="{{ url_for('saved') }}">Saved</a>{% endif %}
      <a href="{{ url_for('inbox') }}">Messages</a>
      {% if session.get('role')=='admin' %}<a href="{{ url_for('admin') }}">Admin</a>{% endif %}
    </div>
    <div class="flex">
      {% if session.get('user_id') %}
        <span class="badge">{{ session.get('role')|title }}</span>
        <a class="btn btn-sm btn-light" href="{{ url_for('dashboard') }}">Dashboard</a>
        <a class="btn btn-sm btn-danger" href="{{ url_for('logout') }}">Logout</a>
      {% else %}
        <a class="btn btn-sm btn-light" href="{{ url_for('login') }}">Login</a>
        <a class="btn btn-sm" href="{{ url_for('register') }}">Register</a>
      {% endif %}
    </div>
  </div>

  {% with msgs = get_flashed_messages() %}
    {% if msgs %}{% for m in msgs %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}
  {% endwith %}

  {{ content|safe }}

  <footer>© {{ now.year }} {{ APP_TITLE }}. Built with Flask + SQLite.</footer>
</div>
</body>
</html>
"""

def page(content, title=None):
    return render_template_string(BASE, content=content, title=title, APP_TITLE=APP_TITLE, now=datetime.datetime.utcnow())

# ---------------------------- UTIL ----------------------------
def current_user():
    if "user_id" not in session: return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

def sanitize_numeric(val, default=None):
    try:
        return float(val)
    except: return default

# ---------------------------- ROUTES ----------------------------
@app.route("/")
def home():
    db = get_db()
    stats = {
        "users": db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "loads": db.execute("SELECT COUNT(*) c FROM loads").fetchone()["c"],
        "open":  db.execute("SELECT COUNT(*) c FROM loads WHERE status='open'").fetchone()["c"],
        "bids":  db.execute("SELECT COUNT(*) c FROM bids").fetchone()["c"],
    }
    content = f"""
    <div class="grid grid-2">
      <div class="card">
        <h2>Find a Load</h2>
        <form method="get" action="{ url_for('loads') }" class="grid grid-3" style="grid-template-columns:1.2fr 1.2fr .8fr">
          <div><label>Pickup City</label><input name="pickup_city" placeholder="e.g., Dallas"></div>
          <div><label>Delivery City</label><input name="delivery_city" placeholder="e.g., Atlanta"></div>
          <div><label>Equipment</label><input name="equipment" placeholder="Dry Van / Reefer / Flatbed"></div>
          <div><label>Min Rate ($)</label><input name="min_rate" type="number" step="0.01"></div>
          <div><label>Max Weight (lbs)</label><input name="max_weight" type="number" step="0.1"></div>
          <div style="align-self:end"><button class="btn btn-success" type="submit">Search</button></div>
        </form>
      </div>
      <div class="card">
        <h2>Stats</h2>
        <div class="kpis">
          <div class="kpi"><div class="badge">Users</div><h3>{stats['users']}</h3></div>
          <div class="kpi"><div class="badge">Loads</div><h3>{stats['loads']}</h3></div>
          <div class="kpi"><div class="badge">Open Loads</div><h3>{stats['open']}</h3></div>
          <div class="kpi"><div class="badge">Bids</div><h3>{stats['bids']}</h3></div>
        </div>
        <hr>
        <p>Post loads as a <b>Shipper</b> or bid & haul as a <b>Trucker</b>. Built for speed—no plugins or external files.</p>
      </div>
    </div>
    """
    return page(content, "Home")

# ---------------------------- AUTH ----------------------------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name  = request.form.get("name","").strip()
        email = request.form.get("email","").lower().strip()
        role  = request.form.get("role","shipper")
        pwd   = request.form.get("password","")
        company = request.form.get("company")
        phone   = request.form.get("phone")
        mc      = request.form.get("mc_number")

        if not re.match(r"[^@]+@[^@]+", email): 
            flash("Invalid email"); 
        elif len(pwd) < 6:
            flash("Password must be at least 6 chars")
        else:
            try:
                db = get_db()
                db.execute("INSERT INTO users(role,name,email,password_hash,company,phone,mc_number) VALUES(?,?,?,?,?,?,?)",
                           (role, name, email, generate_password_hash(pwd), company, phone, mc))
                db.commit()
                flash("Registration successful. Please login.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Email already registered.")
    content = """
    <div class="card">
      <h2>Create Account</h2>
      <form method="post" class="grid grid-2">
        <div><label>Name</label><input name="name" required></div>
        <div><label>Email</label><input name="email" type="email" required></div>
        <div><label>Password</label><input name="password" type="password" required></div>
        <div>
          <label>Role</label>
          <select name="role">
            <option value="shipper">Shipper</option>
            <option value="trucker">Trucker</option>
          </select>
        </div>
        <div><label>Company</label><input name="company"></div>
        <div><label>Phone</label><input name="phone"></div>
        <div><label>MC/DOT</label><input name="mc_number"></div>
        <div style="align-self:end"><button class="btn">Register</button></div>
      </form>
    </div>
    """
    return page(content, "Register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").lower().strip()
        pwd   = request.form.get("password","")
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if u and check_password_hash(u["password_hash"], pwd):
            session["user_id"] = u["id"]
            session["role"]    = u["role"]
            session["name"]    = u["name"]
            flash("Welcome back, "+u["name"])
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid credentials")
    content = f"""
    <div class="card">
      <h2>Login</h2>
      <form method="post" class="grid grid-2">
        <div><label>Email</label><input name="email" type="email" required></div>
        <div><label>Password</label><input name="password" type="password" required></div>
        <div style="grid-column:1/-1"><button class="btn">Login</button> <a class="btn btn-light" href="{url_for('register')}">Create account</a></div>
      </form>
    </div>
    """
    return page(content, "Login")

@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.")
    return redirect(url_for("home"))

# ---------------------------- DASHBOARD ----------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    u = current_user()
    if session["role"] == "shipper":
        myloads = db.execute("SELECT * FROM loads WHERE shipper_id=? ORDER BY created_at DESC", (u["id"],)).fetchall()
        bids = db.execute("""SELECT b.*, l.title FROM bids b 
                             JOIN loads l ON l.id=b.load_id 
                             WHERE l.shipper_id=? ORDER BY b.created_at DESC""", (u["id"],)).fetchall()
    elif session["role"] == "trucker":
        myloads = db.execute("SELECT * FROM loads WHERE trucker_id=? ORDER BY created_at DESC", (u["id"],)).fetchall()
        bids = db.execute("""SELECT b.*, l.title FROM bids b 
                             JOIN loads l ON l.id=b.load_id 
                             WHERE b.trucker_id=? ORDER BY b.created_at DESC""", (u["id"],)).fetchall()
    else:
        myloads = db.execute("SELECT * FROM loads ORDER BY created_at DESC LIMIT 10").fetchall()
        bids = db.execute("SELECT * FROM bids ORDER BY created_at DESC LIMIT 10").fetchall()

    def load_row(l):
        st = f"<span class='badge'>{l['status']}</span>"
        return f"<tr><td>#{l['id']}</td><td>{l['title']}</td><td>{l['pickup_city']} → {l['delivery_city']}</td><td>${l['rate'] or 0:.0f}</td><td>{st}</td><td><a class='btn btn-sm btn-light' href='{url_for('view_load', load_id=l['id'])}'>Open</a></td></tr>"

    loads_html = "".join(load_row(l) for l in myloads) or "<tr><td colspan=6>No records.</td></tr>"
    bid_html = "".join([f"<tr><td>#{b['id']}</td><td>${b['amount']:.0f}</td><td>{b['status']}</td><td>{b.get('title','')}</td></tr>" for b in bids]) or "<tr><td colspan=4>No bids.</td></tr>"

    content = f"""
    <div class="grid grid-2">
      <div class="card">
        <h2>My Loads</h2>
        <table class="table">
          <tr><th>ID</th><th>Title</th><th>Route</th><th>Rate</th><th>Status</th><th></th></tr>
          {loads_html}
        </table>
      </div>
      <div class="card">
        <h2>Recent Bids</h2>
        <table class="table">
          <tr><th>ID</th><th>Amount</th><th>Status</th><th>Load</th></tr>
          {bid_html}
        </table>
      </div>
    </div>
    """
    return page(content, "Dashboard")

# ---------------------------- LOADS ----------------------------
@app.route("/loads")
def loads():
    q = []
    args = []
    if request.args.get("pickup_city"):
        q.append("LOWER(pickup_city) LIKE ?"); args.append("%"+request.args["pickup_city"].lower()+"%")
    if request.args.get("delivery_city"):
        q.append("LOWER(delivery_city) LIKE ?"); args.append("%"+request.args["delivery_city"].lower()+"%")
    if request.args.get("equipment"):
        q.append("LOWER(equipment) LIKE ?"); args.append("%"+request.args["equipment"].lower()+"%")
    if request.args.get("min_rate"):
        q.append("rate >= ?"); args.append(sanitize_numeric(request.args["min_rate"],0))
    if request.args.get("max_weight"):
        q.append("weight <= ?"); args.append(sanitize_numeric(request.args["max_weight"],1e12))

    where = "WHERE " + " AND ".join(q) if q else ""
    db = get_db()
    rows = db.execute(f"SELECT * FROM loads {where} ORDER BY created_at DESC").fetchall()

    def row(l):
        badge = f"<span class='badge'>{l['status']}</span>"
        rate = f"${(l['rate'] or 0):.0f}"
        return f"""
        <div class="card">
          <div class="flex">
            <h3 style="margin:0">{l['title']}</h3>
            <span class="right">{badge}</span>
          </div>
          <p>{l['pickup_city']}, {l['pickup_state'] or ''} → {l['delivery_city']}, {l['delivery_state'] or ''}</p>
          <div class="flex"><span class="badge">Weight: {l['weight'] or '—'} lbs</span><span class="badge">Equip: {l['equipment'] or '—'}</span><span class="badge">Rate: {rate}</span></div>
          <div style="margin-top:10px">
            <a class="btn btn-sm btn-light" href="{ url_for('view_load', load_id=l['id']) }">View</a>
            {% if session.get('role')=='trucker' %}
            <a class="btn btn-sm" href="{ url_for('save_load', load_id=l['id']) }">Save</a>
            {% endif %}
          </div>
        </div>
        """
    cards = "\n".join(row(l) for l in rows) or "<div class='card'>No loads yet.</div>"

    content = f"""
    <div class="grid grid-3">{cards}</div>
    """
    return page(content, "Browse Loads")

@app.route("/load/new", methods=["GET","POST"])
@role_required("shipper","admin")
def new_load():
    if request.method == "POST":
        f = request.form
        db = get_db()
        db.execute("""INSERT INTO loads(shipper_id,title,pickup_city,pickup_state,pickup_date,delivery_city,delivery_state,delivery_date,weight,equipment,rate,notes)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (session["user_id"], f.get("title"), f.get("pickup_city"), f.get("pickup_state"),
                    f.get("pickup_date"), f.get("delivery_city"), f.get("delivery_state"),
                    f.get("delivery_date"), sanitize_numeric(f.get("weight")), f.get("equipment"),
                    sanitize_numeric(f.get("rate")), f.get("notes")))
        db.commit()
        flash("Load posted.")
        return redirect(url_for("loads"))
    content = """
    <div class="card">
      <h2>Post a Load</h2>
      <form method="post" class="grid grid-3">
        <div><label>Title</label><input name="title" required placeholder="e.g., Dry Van TX→GA"></div>
        <div><label>Pickup City</label><input name="pickup_city" required></div>
        <div><label>Pickup State</label><input name="pickup_state"></div>
        <div><label>Pickup Date</label><input name="pickup_date" type="date"></div>
        <div><label>Delivery City</label><input name="delivery_city" required></div>
        <div><label>Delivery State</label><input name="delivery_state"></div>
        <div><label>Delivery Date</label><input name="delivery_date" type="date"></div>
        <div><label>Weight (lbs)</label><input name="weight" type="number" step="0.1"></div>
        <div><label>Equipment</label><input name="equipment" placeholder="Dry Van / Reefer / Flatbed"></div>
        <div><label>Rate ($)</label><input name="rate" type="number" step="0.01"></div>
        <div style="grid-column:1/-1"><label>Notes</label><textarea name="notes" rows="3"></textarea></div>
        <div style="grid-column:1/-1"><button class="btn">Publish Load</button></div>
      </form>
    </div>
    """
    return page(content, "New Load")

@app.route("/load/<int:load_id>")
def view_load(load_id):
    db = get_db()
    l = db.execute("SELECT * FROM loads WHERE id=?", (load_id,)).fetchone()
    if not l: abort(404)
    shipper = db.execute("SELECT name,company,phone,email FROM users WHERE id=?", (l["shipper_id"]),).fetchone()
    if shipper is None:
        shipper = {"name": "Unknown", "company": None, "phone": None, "email": "unknown@example.com"}
    bids = db.execute("""SELECT b.*, u.name FROM bids b JOIN users u ON u.id=b.trucker_id
                         WHERE b.load_id=? ORDER BY b.created_at DESC""", (load_id,)).fetchall()

    # Bid list
    bid_html = "".join([
        f"<tr><td>${b['amount']:.0f}</td><td>{b['name']}</td><td>{b['status']}</td>"
        + ( f"<td><a class='btn btn-sm btn-success' href='{url_for('accept_bid', bid_id=b['id'])}'>Accept</a> "
            f"<a class='btn btn-sm btn-danger' href='{url_for('reject_bid', bid_id=b['id'])}'>Reject</a></td>" if session.get("user_id")==l["shipper_id"] or session.get("role")=='admin' else "<td></td>")
        + "</tr>"
    ]) or "<tr><td colspan=4>No bids yet.</td></tr>"

    # Actions
    act = ""
    if session.get("role") == "trucker" and l["status"] == "open":
        act = f"""
        <div class="card">
          <h3>Place a Bid</h3>
          <form method="post" action="{ url_for('place_bid', load_id=l['id']) }" class="grid grid-2">
            <div><label>Amount ($)</label><input name="amount" type="number" step="0.01" required></div>
            <div><label>Message</label><input name="message" placeholder="Short note (optional)"></div>
            <div style="grid-column:1/-1"><button class="btn">Submit Bid</button>
            <a class="btn btn-light" href="{ url_for('save_load', load_id=l['id']) }">Save Load</a></div>
          </form>
        </div>
        """
    if session.get("user_id")==l["shipper_id"] or session.get("role")=="admin":
        act += f"""
        <div class="card">
          <h3>Manage Load</h3>
          <div class="flex">
            <a class="btn btn-light btn-sm" href="{ url_for('update_status', load_id=l['id'], status='assigned') }">Mark Assigned</a>
            <a class="btn btn-light btn-sm" href="{ url_for('update_status', load_id=l['id'], status='in_transit') }">In Transit</a>
            <a class="btn btn-success btn-sm" href="{ url_for('update_status', load_id=l['id'], status='delivered') }">Delivered</a>
            <a class="btn btn-danger btn-sm" href="{ url_for('update_status', load_id=l['id'], status='cancelled') }">Cancel</a>
          </div>
        </div>
        """

    # Compose widget function rendered directly here is not available; replace with simple compose form when logged in
    compose_form = ""
    if session.get("user_id"):
        compose_form = f"""
        <form method="post" action="{url_for('send_message')}" class="grid grid-3" style="grid-template-columns:1fr .6fr .4fr">
          <input type="hidden" name="load_id" value="{l['id']}">
          <div><label>Message</label><input name="body" placeholder="Type a quick note..." required></div>
          <div><label>To (User ID)</label><input name="to" required></div>
          <div style="align-self:end"><button class="btn btn-light btn-sm">Send</button></div>
        </form>
        """

    content = f"""
    <div class="grid grid-2">
      <div class="card">
        <h2>{l['title']}</h2>
        <div class="flex" style="gap:8px">
          <span class="badge">#{l['id']}</span>
          <span class="badge">{l['status']}</span>
          <span class="badge">Rate: ${l['rate'] or 0:.0f}</span>
          <span class="badge">Equip: {l['equipment'] or '—'}</span>
          <span class="badge">Weight: {l['weight'] or '—'} lbs</span>
        </div>
        <hr>
        <p><b>Route:</b> {l['pickup_city']}, {l['pickup_state'] or ''} → {l['delivery_city']}, {l['delivery_state'] or ''}</p>
        <p><b>Pickup:</b> {l['pickup_date'] or 'TBD'} &nbsp; | &nbsp; <b>Delivery:</b> {l['delivery_date'] or 'TBD'}</p>
        <p style="white-space:pre-wrap">{(l['notes'] or '').strip()}</p>
      </div>
      <div class="card">
        <h3>Shipper</h3>
        <p><b>{shipper['name']}</b> — {shipper['company'] or '—'}</p>
        <p>☎ {shipper['phone'] or '—'} &nbsp; · &nbsp; ✉ {shipper['email']}</p>
      </div>
    </div>

    {act}

    <div class="card">
      <h3>Bids</h3>
      <table class="table">
        <tr><th>Amount</th><th>Trucker</th><th>Status</th><th></th></tr>
        {bid_html}
      </table>
    </div>
    {compose_form}
    """
    return page(content, f"Load #{load_id}")

@app.route("/load/<int:load_id>/bid", methods=["POST"])
@role_required("trucker")
def place_bid(load_id):
    amt = sanitize_numeric(request.form.get("amount"))
    msg = request.form.get("message")
    if amt is None or amt<=0:
        flash("Enter a valid bid amount.")
        return redirect(url_for("view_load", load_id=load_id))
    db = get_db()
    # prevent duplicate pending bid
    existing = db.execute("SELECT id FROM bids WHERE load_id=? AND trucker_id=? AND status='pending'",
                          (load_id, session["user_id"])).fetchone()
    if existing:
        flash("You already have a pending bid on this load.")
        return redirect(url_for("view_load", load_id=load_id))
    db.execute("INSERT INTO bids(load_id,trucker_id,amount,message) VALUES(?,?,?,?)",
               (load_id, session["user_id"], amt, msg))
    db.commit()
    flash("Bid submitted.")
    return redirect(url_for("view_load", load_id=load_id))

@app.route("/bid/<int:bid_id>/accept")
@login_required
def accept_bid(bid_id):
    db = get_db()
    b = db.execute("""SELECT b.*, l.shipper_id FROM bids b 
                      JOIN loads l ON l.id=b.load_id WHERE b.id=?""",(bid_id,)).fetchone()
    if not b: abort(404)
    if session["user_id"] != b["shipper_id"] and session.get("role")!="admin": abort(403)
    # Accept this bid, reject others, assign load to trucker
    db.execute("UPDATE bids SET status='accepted' WHERE id=?", (bid_id,))
    db.execute("UPDATE bids SET status='rejected' WHERE load_id=? AND id<>?", (b["load_id"], bid_id))
    db.execute("UPDATE loads SET status='assigned', trucker_id=? WHERE id=?", (b["trucker_id"], b["load_id"]))
    db.commit()
    flash("Bid accepted and load assigned.")
    return redirect(url_for("view_load", load_id=b["load_id"]))

@app.route("/bid/<int:bid_id>/reject")
@login_required
def reject_bid(bid_id):
    db = get_db()
    b = db.execute("""SELECT b.*, l.shipper_id FROM bids b 
                      JOIN loads l ON l.id=b.load_id WHERE b.id=?""",(bid_id,)).fetchone()
    if not b: abort(404)
    if session["user_id"] != b["shipper_id"] and session.get("role")!="admin": abort(403)
    db.execute("UPDATE bids SET status='rejected' WHERE id=?", (bid_id,))
    db.commit()
    flash("Bid rejected.")
    return redirect(url_for("view_load", load_id=b["load_id"]))

@app.route("/load/<int:load_id>/status/<status>")
@login_required
def update_status(load_id, status):
    if status not in ("open","assigned","in_transit","delivered","cancelled"): abort(400)
    db = get_db()
    l = db.execute("SELECT shipper_id FROM loads WHERE id=?", (load_id,)).fetchone()
    if not l: abort(404)
    if session["user_id"] != l["shipper_id"] and session.get("role")!="admin": abort(403)
    db.execute("UPDATE loads SET status=? WHERE id=?", (status, load_id))
    db.commit()
    flash(f"Status updated to {status}.")
    return redirect(url_for("view_load", load_id=load_id))

# ---------------------------- SAVE / FAVORITES ----------------------------
@app.route("/save/<int:load_id>")
@role_required("trucker")
def save_load(load_id):
    db = get_db()
    try:
        db.execute("INSERT OR IGNORE INTO saved_loads(user_id,load_id) VALUES(?,?)", (session["user_id"], load_id))
        db.commit()
        flash("Saved.")
    except:
        flash("Could not save.")
    return redirect(url_for("view_load", load_id=load_id))

@app.route("/saved")
@role_required("trucker")
def saved():
    db = get_db()
    rows = db.execute("""SELECT l.* FROM saved_loads s 
                         JOIN loads l ON l.id=s.load_id
                         WHERE s.user_id=? ORDER BY s.created_at DESC""", (session["user_id"],)).fetchall()
    items = "".join([f"<li><a href='{url_for('view_load', load_id=r['id'])}'>#{r['id']} · {r['title']} · {r['pickup_city']}→{r['delivery_city']}</a></li>" for r in rows]) or "<li>None</li>"
    content = f"""
    <div class="card">
      <h2>Saved Loads</h2>
      <ul>{items}</ul>
    </div>
    """
    return page(content, "Saved Loads")

# ---------------------------- MESSAGING ----------------------------
@app.route("/inbox")
@login_required
def inbox():
    db = get_db()
    msgs = db.execute("""SELECT m.*, u.name AS sender_name 
                         FROM messages m JOIN users u ON u.id=m.sender_id
                         WHERE receiver_id=? ORDER BY created_at DESC""", (session["user_id"],)).fetchall()
    rows = "".join([f"<tr><td>{m['sender_name']}</td><td style='max-width:520px'>{m['body']}</td><td>{m['created_at']}</td></tr>" for m in msgs]) or "<tr><td colspan=3>No messages.</td></tr>"
    content = f"""
    <div class="card">
      <h2>Inbox</h2>
      <table class="table"><tr><th>From</th><th>Message</th><th>When</th></tr>{rows}</table>
    </div>
    """
    return page(content, "Inbox")

@app.route("/message/send", methods=["POST"])
@login_required
def send_message():
    receiver_id = request.form.get("to")
    load_id     = request.form.get("load_id")
    body        = (request.form.get("body") or "").strip()
    if not receiver_id or not body:
        flash("Message needs a recipient and content.")
        return redirect(request.referrer or url_for("inbox"))
    db = get_db()
    db.execute("INSERT INTO messages(sender_id,receiver_id,load_id,body) VALUES(?,?,?,?)",
               (session["user_id"], int(receiver_id), int(load_id) if load_id else None, body))
    db.commit()
    flash("Message sent.")
    return redirect(request.referrer or url_for("inbox"))

# Quick compose widget (render helper)
def compose_widget(to_id=None, load_id=None):
    to_id = to_id or ""
    load_id = load_id or ""
    return f"""
    <form method="post" action="{url_for('send_message')}" class="grid grid-3" style="grid-template-columns:1fr .6fr .4fr">
      <input type="hidden" name="load_id" value="{load_id}">
      <div><label>Message</label><input name="body" placeholder="Type a quick note..." required></div>
      <div><label>To (User ID)</label><input name="to" value="{to_id}" required></div>
      <div style="align-self:end"><button class="btn btn-light btn-sm">Send</button></div>
    </form>
    """

# ---------------------------- ADMIN ----------------------------
@app.route("/admin")
@role_required("admin")
def admin():
    db = get_db()
    ucount = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    lcount = db.execute("SELECT COUNT(*) c FROM loads").fetchone()["c"]
    bcount = db.execute("SELECT COUNT(*) c FROM bids").fetchone()["c"]
    users  = db.execute("SELECT id,name,email,role,company FROM users ORDER BY created_at DESC LIMIT 20").fetchall()
    rows = "".join([f"<tr><td>{u['id']}</td><td>{u['name']}</td><td>{u['email']}</td><td>{u['role']}</td><td>{u['company'] or ''}</td></tr>" for u in users])
    content = f"""
    <div class="card">
      <h2>Admin Dashboard</h2>
      <div class="kpis">
        <div class="kpi"><div class="badge">Users</div><h3>{ucount}</h3></div>
        <div class="kpi"><div class="badge">Loads</div><h3>{lcount}</h3></div>
        <div class="kpi"><div class="badge">Bids</div><h3>{bcount}</h3></div>
      </div>
      <hr>
      <h3>Recent Users</h3>
      <table class="table"><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Company</th></tr>{rows}</table>
    </div>
    """
    return page(content, "Admin")

# ---------------------------- PROFILE (quick view + compose) ----------------------------
@app.route("/user/<int:user_id>")
@login_required
def user_profile(user_id):
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not u: abort(404)
    content = f"""
    <div class="grid grid-2">
      <div class="card">
        <h2>{u['name']}</h2>
        <p><b>Role:</b> {u['role']}</p>
        <p><b>Company:</b> {u['company'] or '—'}</p>
        <p><b>Phone:</b> {u['phone'] or '—'} &nbsp; · &nbsp; <b>Email:</b> {u['email']}</p>
        <p><b>MC/DOT:</b> {u['mc_number'] or '—'}</p>
      </div>
      <div class="card">
        <h3>Send Message</h3>
        {compose_widget(to_id=u['id'])}
      </div>
    </div>
    """
    return page(content, f"{u['name']} - Profile")

# ---------------------------- QUICK COMPOSE ON LOAD PAGE ----------------------------
@app.context_processor
def inject_helpers():
    return dict(compose_widget=compose_widget)

# ---------------------------- EXTRA: headers ----------------------------
@app.after_request
def add_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp

# ---------------------------- 404/403 ----------------------------
@app.errorhandler(403)
def e403(_e):
    return page("<div class='card'><h2>Forbidden</h2><p>You don’t have permission for that action.</p></div>","Forbidden"), 403

@app.errorhandler(404)
def e404(_e):
    return page("<div class='card'><h2>Not Found</h2><p>The resource you requested doesn’t exist.</p></div>","Not Found"), 404

# ---------------------------- LAUNCH ----------------------------
if __name__ == "__main__":
    # Ensure DB exists
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
