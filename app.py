import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
import io

from flask import (
    Flask, abort, flash, jsonify, redirect, render_template,
    request, session, url_for
)
from werkzeug.security import check_password_hash
from PIL import Image, UnidentifiedImageError
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = Path(os.environ.get("INSTANCE_DIR", BASE_DIR / "instance"))
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = Path(os.environ.get(
    "DATABASE_PATH", str(INSTANCE_DIR / "arkas_history.db")
))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "8"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "cle-secrete-par-defaut-a-changer-en-prod"),
    MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash").strip()

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

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
                return jsonify({"error": "Session expirée. Reconnecte-toi."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token

@app.context_processor
def inject_csrf():
    return {"csrf_token": csrf_token}

def verify_csrf():
    expected = session.get("_csrf_token", "")
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        abort(400, description="Jeton de sécurité invalide. Recharge la page.")

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "private"
    return response

def build_prompt(mode):
    common = """
Tu es ARKAS SCAN AI, un assistant d'analyse technique de graphiques.
Analyse uniquement les informations réellement visibles sur l'image.
Ne prétends pas connaître le prix en temps réel ni un timeframe qui n'est pas lisible.
Ne fabrique jamais de prix, de niveau, de structure ou de confirmation.
Si l'image est floue, coupée ou insuffisante, indique WAIT et explique ce qui manque.
Un score de confiance est une appréciation qualitative de la lisibilité/cohérence,
pas une probabilité statistique de gain. N'affirme jamais qu'une stratégie est rentable.
Les niveaux numériques doivent être extraits du graphique ou explicitement marqués
"non déterminable". Ne transforme pas une hypothèse en signal confirmé.

Réponds exclusivement en JSON valide, sans markdown, avec exactement ces clés :
{
 "signal": "BUY NOW | SELL NOW | BUY LIMIT | SELL LIMIT | WAIT",
 "asset": "actif détecté ou non déterminable",
 "timeframe": "timeframe détecté ou non déterminable",
 "trend": "haussière | baissière | range | indéterminée",
 "structure": "BOS/CHoCH ou explication",
 "zones": ["OB", "FVG", "liquidité", "supports/résistances"],
 "entry": "prix ou non déterminable",
 "stop_loss": "prix ou non déterminable",
 "take_profits": ["TP1", "TP2", "TP3 ou non déterminables"],
 "confidence": 0,
 "reasons": ["raison 1", "raison 2"],
 "invalidation": "condition qui invaliderait le scénario",
 "risk_warning": "avertissement bref"
}
confidence doit être un nombre entier de 0 à 100.
"""
    if mode == "audit":
        return common + "\nMODE AUDIT : Évalue la cohérence du scénario visible. Le champ signal doit refléter ton verdict prudent, généralement WAIT si le plan n'est pas suffisamment démontré."
    return common + "\nMODE SCANNER : recherche une configuration potentielle. Ne propose BUY NOW ou SELL NOW que si les éléments visibles sont suffisamment clairs. Sinon WAIT."

def extract_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {
        "signal": "WAIT", "asset": "non déterminable", "timeframe": "non déterminable",
        "trend": "indéterminée", "structure": "Réponse IA non structurée", "zones": [],
        "entry": "non déterminable", "stop_loss": "non déterminable", "take_profits": ["non déterminables"],
        "confidence": 0, "reasons": [text[:5000] or "Aucun contenu reçu."],
        "invalidation": "Analyse à refaire.", "risk_warning": "Réponse non JSON."
    }

@app.route("/")
def home():
    if session.get("admin_authenticated"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_authenticated"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        verify_csrf()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not ADMIN_EMAIL or not ADMIN_PASSWORD_HASH:
            flash("Connexion non configurée. Vérifie les variables sur Render.", "error")
            return render_template("login.html"), 503

        valid_email = secrets.compare_digest(email, ADMIN_EMAIL)
        try:
            valid_password = check_password_hash(ADMIN_PASSWORD_HASH, password)
        except (ValueError, TypeError):
            valid_password = False

        if valid_email and valid_password:
            session.clear()
            session["admin_authenticated"] = True
            session["admin_email"] = ADMIN_EMAIL
            session.permanent = True
            csrf_token()
            return redirect(url_for("dashboard"))

        flash("Identifiant ou mot de passe incorrect.", "error")

    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@admin_required
def logout():
    verify_csrf()
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
@admin_required
def dashboard():
    return render_template("dashboard.html", admin_email=session.get("admin_email", "Administrateur"))

@app.route("/api/analyze", methods=["POST"])
@admin_required
def analyze():
    verify_csrf()

    if not gemini_client:
        return jsonify({"error": "GOOGLE_API_KEY n'est pas configurée."}), 503

    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"error": "Sélectionne une image."}), 400

    mode = request.form.get("mode", "scan").lower()
    if mode not in {"scan", "audit"}:
        return jsonify({"error": "Mode invalide."}), 400

    image_bytes = upload.read(MAX_UPLOAD_BYTES + 1)
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        return jsonify({"error": f"Image trop volumineuse. Max: {MAX_UPLOAD_MB} Mo."}), 413

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
        mime_type = Image.MIME.get(image.format)
        if mime_type not in ALLOWED_MIME:
            return jsonify({"error": "Format non accepté."}), 415
    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify({"error": "Image invalide."}), 415

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                build_prompt(mode)
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                max_output_tokens=1800
            )
        )
        result = extract_json(response.text)
        
        confidence = result.get("confidence")
        try:
            confidence = max(0, min(100, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0

        with db_connect() as conn:
            cursor = conn.execute("""
                INSERT INTO analyses (created_at, mode, original_filename, mime_type, result_text, signal, asset, timeframe, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(), mode, Path(upload.filename).name[:180],
                mime_type, json.dumps(result, ensure_ascii=False), str(result.get("signal", "WAIT"))[:40],
                str(result.get("asset", ""))[:100], str(result.get("timeframe", ""))[:40], confidence
            ))
            conn.commit()

        return jsonify({"id": cursor.lastrowid, "mode": mode, "result": result})

    except Exception as exc:
        app.logger.exception("Gemini analysis failed")
        return jsonify({"error": "L'analyse IA a échoué.", "detail": str(exc)[:300]}), 502

@app.route("/api/history")
@admin_required
def history():
    limit = min(max(request.args.get("limit", 50, type=int), 1), 100)
    with db_connect() as conn:
        rows = conn.execute("SELECT id, created_at, mode, original_filename, signal, asset, timeframe, confidence FROM analyses ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})

@app.route("/api/history/<int:analysis_id>")
@admin_required
def history_detail(analysis_id):
    with db_connect() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row: return jsonify({"error": "Analyse introuvable."}), 404
    item = dict(row)
    try: item["result"] = json.loads(item.pop("result_text"))
    except: item["result"] = {"reasons": [item.pop("result_text", "")]}
    return jsonify(item)

@app.route("/api/history/<int:analysis_id>", methods=["DELETE"])
@admin_required
def delete_history_item(analysis_id):
    verify_csrf()
    with db_connect() as conn:
        cursor = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        conn.commit()
    if cursor.rowcount == 0: return jsonify({"error": "Introuvable."}), 404
    return jsonify({"ok": True})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "ARKAS SCAN AI V2"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)
