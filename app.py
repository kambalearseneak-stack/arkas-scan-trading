import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
import io

from flask import (
    Flask, flash, jsonify, redirect, render_template,
    request, session, url_for, send_from_directory
)
from werkzeug.security import check_password_hash
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = Path(os.environ.get("INSTANCE_DIR", BASE_DIR / "instance"))
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(INSTANCE_DIR / "arkas_history.db")))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "8"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "cle-secrete-par-defaut-a-changer-en-prod"),
    MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False, # Désactivé pour Render
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- ROUTE POUR L'IMAGE A LA RACINE ---
@app.route('/akas.jpg')
def serve_bg_image():
    # Sert l'image directement depuis la racine du projet
    return send_from_directory(BASE_DIR, 'akas.jpg')

# ... (Le reste des fonctions db_connect, init_db, admin_required, etc. reste identique) ...

def db_connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                result_text TEXT NOT NULL,
                signal TEXT,
                asset TEXT,
                timeframe TEXT,
                confidence REAL
            )
        """)
        conn.commit()

init_db()

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Non autorisé. Connecte-toi."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def csrf_token(): return ""
@app.context_processor
def inject_csrf(): return {"csrf_token": csrf_token}
def verify_csrf(): pass

def build_prompt(mode):
    common = """
Tu es ARKAS SCAN AI, un assistant d'analyse technique de graphiques (SMC, ICT, Price Action).
Analyse uniquement les informations réellement visibles sur l'image.
Réponds exclusivement en JSON valide avec exactement ces clés :
{"signal": "BUY|SELL|WAIT", "asset": "", "timeframe": "", "trend": "", "structure": "", "zones": [], "entry": "", "stop_loss": "", "take_profits": [], "confidence": 0, "reasons": [], "invalidation": "", "risk_warning": ""}
"""
    return common

def extract_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json", "").strip()
    try:
        return json.loads(text)
    except:
        return {"signal": "WAIT", "asset": "non déterminable", "timeframe": "non déterminable", "trend": "indéterminée", "structure": "Erreur", "zones": [], "entry": "non déterminable", "stop_loss": "non déterminable", "take_profits": [], "confidence": 0, "reasons": ["Réponse non structurée."], "invalidation": "-", "risk_warning": "-"}

@app.route("/")
def home():
    if session.get("admin_authenticated"): return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_authenticated"): return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not ADMIN_EMAIL or not ADMIN_PASSWORD_HASH:
            flash("Configuration manquante.", "error")
            return render_template("login.html")
        valid_email = secrets.compare_digest(email, ADMIN_EMAIL)
        try: valid_password = check_password_hash(ADMIN_PASSWORD_HASH, password)
        except: valid_password = False
        if valid_email and valid_password:
            session.clear()
            session["admin_authenticated"] = True
            session["admin_email"] = ADMIN_EMAIL
            session.permanent = True
            return redirect(url_for("dashboard"))
        flash("Identifiant ou mot de passe incorrect.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
@admin_required
def dashboard():
    return render_template("dashboard.html", admin_email=session.get("admin_email", "Administrateur"))

@app.route("/api/analyze", methods=["POST"])
@admin_required
def analyze():
    if not gemini_client: return jsonify({"error": "GOOGLE_API_KEY manquante."}), 503
    upload = request.files.get("file")
    if not upload: return jsonify({"error": "Aucune image."}), 400
    
    mode = request.form.get("mode", "scan").lower()
    image_bytes = upload.read(MAX_UPLOAD_BYTES + 1)
    
    # Mécanisme de retry si Gemini est surchargé (Erreur 503)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"), build_prompt(mode)],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2)
            )
            result = extract_json(response.text)
            with db_connect() as conn:
                conn.execute("INSERT INTO analyses (created_at, mode, original_filename, mime_type, result_text, signal, asset) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                             (datetime.now(timezone.utc).isoformat(), mode, upload.filename, "image/jpeg", json.dumps(result), result.get("signal"), result.get("asset")))
                conn.commit()
            return jsonify({"result": result})
        except Exception as e:
            if ("503" in str(e) or "UNAVAILABLE" in str(e)) and attempt < max_retries - 1:
                time.sleep(3) # On attend 3 secondes et on réessaie
                continue
            return jsonify({"error": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
@admin_required
def chat():
    if not gemini_client: return jsonify({"error": "GOOGLE_API_KEY manquante."}), 503
    data = request.get_json()
    user_message = data.get("message", "")
    if not user_message: return jsonify({"error": "Message vide."}), 400
    try:
        prompt = f"Tu es un expert en trading (SMC/ICT). Réponds de manière concise : {user_message}"
        response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=[prompt])
        return jsonify({"reply": response.text})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/history")
@admin_required
def history():
    with db_connect() as conn:
        rows = conn.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 50").fetchall()
    return jsonify({"items": [dict(row) for row in rows]})

@app.route("/api/history/<int:id>", methods=["DELETE"])
@admin_required
def delete_history_item(id):
    with db_connect() as conn:
        conn.execute("DELETE FROM analyses WHERE id = ?", (id,))
        conn.commit()
    return jsonify({"ok": True})

@app.route("/health")
def health(): return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)
