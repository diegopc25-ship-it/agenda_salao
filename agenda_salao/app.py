from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from pathlib import Path
from functools import wraps
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

BASE = Path(__file__).resolve().parent
DB = BASE / "agenda.db"

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION"

SALON = {
    "name": "Salão da Minha Esposa",
    "address": "Adicionar endereço no painel",
    "phone": "Adicionar contacto no painel",
    "hours": "Segunda a sábado, mediante marcação"
}

SERVICES = [
    ("Corte", "Corte de cabelo"),
    ("Brushing", "Brushing"),
    ("Coloração", "Coloração"),
    ("Alisamento", "O valor é confirmado pelo salão conforme o cabelo e o serviço"),
    ("Tratamento", "Tratamento capilar"),
    ("Manicure", "Manicure"),
]

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        service_id INTEGER NOT NULL,
        booking_date TEXT NOT NULL,
        booking_time TEXT NOT NULL,
        notes TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pendente',
        created_at TEXT NOT NULL,
        FOREIGN KEY(service_id) REFERENCES services(id)
    );
    CREATE TABLE IF NOT EXISTS blocked (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        block_date TEXT NOT NULL,
        start_time TEXT DEFAULT '',
        end_time TEXT DEFAULT '',
        reason TEXT DEFAULT ''
    );
    """)
    defaults = {
        "name": SALON["name"],
        "address": SALON["address"],
        "phone": SALON["phone"],
        "hours": SALON["hours"],
        "opening": "09:00",
        "closing": "18:00",
        "slot_minutes": "30",
        "admin_password_hash": generate_password_hash(admin_password),
    }
    for k, v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (k, v))
    if conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
        conn.executemany("INSERT INTO services(name,description) VALUES (?,?)", SERVICES)
    conn.commit()
    conn.close()

def settings():
    conn = db()
    rows = conn.execute("SELECT key,value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

def time_slots():
    s = settings()
    start = datetime.strptime(s["opening"], "%H:%M")
    end = datetime.strptime(s["closing"], "%H:%M")
    step = int(s["slot_minutes"])
    out = []
    cur = start
    while cur < end:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step)
    return out

def slot_blocked(d, t):
    conn = db()
    rows = conn.execute("SELECT * FROM blocked WHERE block_date=?", (d,)).fetchall()
    for r in rows:
        if not r["start_time"] or not r["end_time"]:
            conn.close()
            return True
        if r["start_time"] <= t < r["end_time"]:
            conn.close()
            return True
    conn.close()
    return False

def slot_available(d, t):
    if d < date.today().isoformat():
        return False
    if slot_blocked(d, t):
        return False
    conn = db()
    row = conn.execute(
        "SELECT id FROM bookings WHERE booking_date=? AND booking_time=? AND status IN ('pendente','confirmado')",
        (d, t)
    ).fetchone()
    conn.close()
    return row is None

@app.context_processor
def inject():
    return {"salon": settings()}

@app.route("/")
def home():
    conn = db()
    services = conn.execute("SELECT * FROM services WHERE active=1 ORDER BY id").fetchall()
    conn.close()
    return render_template("home.html", services=services)

@app.route("/marcar", methods=["GET","POST"])
def booking():
    conn = db()
    services = conn.execute("SELECT * FROM services WHERE active=1 ORDER BY id").fetchall()
    conn.close()
    if request.method == "POST":
        name = request.form.get("name","").strip()
        phone = request.form.get("phone","").strip()
        service_id = request.form.get("service_id","")
        d = request.form.get("date","")
        t = request.form.get("time","")
        notes = request.form.get("notes","").strip()
        if not all([name, phone, service_id, d, t]):
            flash("Preencha nome, contacto, serviço, data e horário.", "error")
            return redirect(url_for("booking"))
        if not slot_available(d,t):
            flash("Esse horário já não está disponível. Escolha outro.", "error")
            return redirect(url_for("booking"))
        conn = db()
        conn.execute("""INSERT INTO bookings
            (name,phone,service_id,booking_date,booking_time,notes,status,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (name, phone, service_id, d, t, notes, "pendente", datetime.now().isoformat(timespec="seconds")))
        conn.commit()
        conn.close()
        flash("Pedido de marcação enviado. O salão irá confirmar.", "success")
        return redirect(url_for("booking"))
    return render_template("booking.html", services=services, slots=time_slots(), today=date.today().isoformat())

@app.get("/api/slots")
def api_slots():
    d = request.args.get("date","")
    return jsonify([t for t in time_slots() if slot_available(d,t)])

@app.route("/cancelar/<int:booking_id>", methods=["GET","POST"])
def cancel_booking(booking_id):
    conn = db()
    b = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if not b:
        conn.close()
        return "Marcação não encontrada", 404
    if request.method == "POST":
        conn.execute("UPDATE bookings SET status='cancelado' WHERE id=?", (booking_id,))
        conn.commit()
        conn.close()
        flash("Marcação cancelada.", "success")
        return redirect(url_for("home"))
    conn.close()
    return render_template("cancel.html", booking=b)

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password","")
        s = settings()
        if check_password_hash(s["admin_password_hash"], password):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Palavra-passe incorreta.", "error")
    return render_template("admin_login.html")

@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

@app.get("/admin")
@admin_required
def admin():
    conn = db()
    bookings = conn.execute("""SELECT b.*, s.name AS service_name
        FROM bookings b JOIN services s ON s.id=b.service_id
        ORDER BY b.booking_date, b.booking_time""").fetchall()
    blocks = conn.execute("SELECT * FROM blocked ORDER BY block_date DESC").fetchall()
    services = conn.execute("SELECT * FROM services ORDER BY id").fetchall()
    conn.close()
    return render_template("admin.html", bookings=bookings, blocks=blocks, services=services)

@app.post("/admin/booking/<int:bid>/<action>")
@admin_required
def booking_action(bid, action):
    if action not in ("confirmado","cancelado","pendente"):
        return "Ação inválida", 400
    conn = db()
    conn.execute("UPDATE bookings SET status=? WHERE id=?", (action,bid))
    conn.commit()
    conn.close()
    flash("Marcação atualizada.", "success")
    return redirect(url_for("admin"))

@app.post("/admin/block")
@admin_required
def add_block():
    d = request.form.get("date","")
    start = request.form.get("start_time","")
    end = request.form.get("end_time","")
    reason = request.form.get("reason","").strip()
    if not d:
        flash("Escolha uma data.", "error")
        return redirect(url_for("admin"))
    conn = db()
    conn.execute("INSERT INTO blocked(block_date,start_time,end_time,reason) VALUES (?,?,?,?)",
                 (d,start,end,reason))
    conn.commit()
    conn.close()
    flash("Bloqueio criado.", "success")
    return redirect(url_for("admin"))

@app.post("/admin/block/<int:bid>/delete")
@admin_required
def delete_block(bid):
    conn = db()
    conn.execute("DELETE FROM blocked WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    flash("Bloqueio removido.", "success")
    return redirect(url_for("admin"))

@app.post("/admin/service")
@admin_required
def add_service():
    name = request.form.get("name","").strip()
    description = request.form.get("description","").strip()
    if name:
        conn = db()
        conn.execute("INSERT INTO services(name,description) VALUES (?,?)", (name,description))
        conn.commit()
        conn.close()
    return redirect(url_for("admin"))

@app.post("/admin/service/<int:sid>/toggle")
@admin_required
def toggle_service(sid):
    conn = db()
    conn.execute("UPDATE services SET active = CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.post("/admin/settings")
@admin_required
def save_settings():
    allowed = ["name","address","phone","hours","opening","closing","slot_minutes"]
    conn = db()
    for k in allowed:
        if k in request.form:
            conn.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         (k, request.form[k].strip()))
    conn.commit()
    conn.close()
    flash("Dados do salão atualizados.", "success")
    return redirect(url_for("admin"))

@app.post("/admin/password")
@admin_required
def change_password():
    p = request.form.get("password","")
    if len(p) < 8:
        flash("Use pelo menos 8 caracteres.", "error")
        return redirect(url_for("admin"))
    conn = db()
    conn.execute("UPDATE settings SET value=? WHERE key='admin_password_hash'", (generate_password_hash(p),))
    conn.commit()
    conn.close()
    flash("Palavra-passe alterada.", "success")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    print("\nAgenda do Salão")
    print("Abra no navegador: http://127.0.0.1:5000")
    print("Painel: http://127.0.0.1:5000/admin")
    app.run(host="0.0.0.0", port=5000, debug=False)
