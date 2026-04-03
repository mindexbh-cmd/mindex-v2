# Mindex Portal
from flask import Flask, make_response, request, jsonify, session, redirect, g
import sqlite3, hashlib, os, json
from datetime import date
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mindx2026")
DB = os.environ.get("DB_PATH", "mindx.db")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def hp(p): return hashlib.sha256(p.encode()).hexdigest()

def init_db():
    db = sqlite3.connect(DB)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT,name TEXT,role TEXT);
    CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY,name TEXT,group_name TEXT,teacher TEXT,whatsapp TEXT,status TEXT DEFAULT active);
    CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY,student_name TEXT,group_name TEXT,date TEXT,status TEXT);
    CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY,student_name TEXT,amount REAL,status TEXT DEFAULT pending);
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,title TEXT,department TEXT,status TEXT DEFAULT pending,priority TEXT DEFAULT medium);
    """)
    users = [("admin","admin123","admin"),("reception","rec123","reception"),("students","stu123","students"),("teacher1","tea123","teacher"),("teacher2","tea456","teacher"),("parent1","par123","parent")]
    for u,p,r in users:
        try: db.execute("INSERT INTO users(username,password,name,role)VALUES(?,?,?,?)",(u,hp(p),u,r))
        except: pass
    db.commit(); db.close()

if not os.path.exists(DB): init_db()

def login_required(f):
    @wraps(f)
    def dec(*a,**k):
        if "user" not in session: return redirect("/")
        return f(*a,**k)
    return dec

LOGIN_HTML = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"login.html")).read()
APP_HTML = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"app.html")).read()

@app.route("/")
def index():
    if "user" in session: return redirect("/dashboard")
    return make_response(LOGIN_HTML)

@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.json
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND password=?",(d["username"],hp(d["password"]))).fetchone()
    if not user: return jsonify({"ok":False})
    session["user"] = dict(user)
    return jsonify({"ok":True})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok":True})

@app.route("/dashboard")
@login_required
def dashboard():
    return make_response(APP_HTML)

@app.route("/api/dashboard")
@login_required
def api_dashboard():
    db = get_db()
    today = date.today().isoformat()
    return jsonify({
        "total_students": db.execute("SELECT COUNT(*) FROM students WHERE status=?",("active",)).fetchone()[0],
        "absent_today": db.execute("SELECT COUNT(*) FROM attendance WHERE date=? AND status=?",(today,"absent")).fetchone()[0],
        "pending_tasks": db.execute("SELECT COUNT(*) FROM tasks WHERE status=?",("pending",)).fetchone()[0],
        "recent_tasks": [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY rowid DESC LIMIT 6").fetchall()],
    })

@app.route("/api/students")
@login_required
def api_students():
    db = get_db()
    q = request.args.get("q","")
    if q:
        rows = db.execute("SELECT * FROM students WHERE name LIKE ? OR group_name LIKE ?",(f"%{q}%",f"%{q}%")).fetchall()
    else:
        rows = db.execute("SELECT * FROM students WHERE status=? ORDER BY name",("active",)).fetchall()
    return jsonify({"students":[dict(r) for r in rows]})

@app.route("/api/students", methods=["POST"])
@login_required
def api_add_student():
    d = request.json
    db = get_db()
    db.execute("INSERT INTO students(name,group_name,teacher,whatsapp)VALUES(?,?,?,?)",(d["name"],d.get("group_name",""),d.get("teacher",""),d.get("whatsapp","")))
    db.commit()
    return jsonify({"ok":True})

@app.route("/api/tasks")
@login_required
def api_tasks():
    db = get_db()
    return jsonify({"tasks":[dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY rowid DESC").fetchall()]})

@app.route("/api/tasks", methods=["POST"])
@login_required
def api_add_task():
    d = request.json
    db = get_db()
    db.execute("INSERT INTO tasks(title,department,priority)VALUES(?,?,?)",(d["title"],d.get("department",""),d.get("priority","medium")))
    db.commit()
    return jsonify({"ok":True})

@app.route("/api/tasks/<int:tid>", methods=["PUT"])
@login_required
def api_update_task(tid):
    d = request.json
    db = get_db()
    db.execute("UPDATE tasks SET status=? WHERE id=?",(d["status"],tid))
    db.commit()
    return jsonify({"ok":True})

@app.route("/api/attendance", methods=["POST"])
@login_required
def api_attendance():
    d = request.json
    db = get_db()
    db.execute("DELETE FROM attendance WHERE student_name=? AND date=?",(d["student_name"],d["date"]))
    db.execute("INSERT INTO attendance(student_name,group_name,date,status)VALUES(?,?,?,?)",(d["student_name"],d.get("group_name",""),d["date"],d["status"]))
    db.commit()
    return jsonify({"ok":True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
