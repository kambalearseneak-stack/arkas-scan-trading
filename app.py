import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from google import genai
from google.genai import types

app = Flask(__name__)

# LA CLÉ POUR GARDER LA CONNEXION EN MÉMOIRE
app.secret_key = "arkas_secret_key_2026"

api_key = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    # Si pas connecté, on renvoie au login
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        # On enregistre l'email en mémoire
        email = request.form.get('email')
        if email:
            session['user'] = email
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

@app.route('/analyze', methods=['POST'])
def analyze_chart():
    if 'user' not in session:
        return jsonify({'error': 'Veuillez vous connecter.'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'Aucune image envoyée'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Fichier invalide'}), 400

    try:
        image_bytes = file.read()
        mime_type = file.content_type if file.content_type else "image/jpeg"
        prompt = "Analyse ce graphique (SMC/ICT) et donne : Tendance, Signal (Buy/Sell/Wait), Entry, SL, TP1, TP2."
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt]
        )
        return jsonify({'analysis': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
