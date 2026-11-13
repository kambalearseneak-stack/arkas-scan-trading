import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from google import genai
from google.genai import types

app = Flask(__name__)

# INDISPENSABLE : Une clé secrète pour que Flask puisse garder la session en mémoire
app.secret_key = os.environ.get("SECRET_KEY", "une_cle_tres_secrete_arkas_2026")

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("ATTENTION : La variable GOOGLE_API_KEY est manquante.")
    # On ne lève pas d'erreur ici pour ne pas crasher le site si la clé manque au démarrage

client = genai.Client(api_key=api_key) if api_key else None

# --- ROUTES DES PAGES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    # SÉCURITÉ : Si l'utilisateur n'est pas connecté, on le renvoie vers le login
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        # Ici, on simule la connexion (on accepte n'importe quel email/mdp pour l'instant)
        # Plus tard, vous pourrez vérifier dans une base de données
        email = request.form.get('email')
        if email:
            session['user'] = email  # On sauvegarde l'utilisateur dans la session
            return redirect(url_for('dashboard')) # On redirige vers le scanner
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None) # On efface la mémoire
    return redirect(url_for('home'))

# --- ROUTE API (SCANNER) ---

@app.route('/analyze', methods=['POST'])
def analyze_chart():
    # Sécurité : on vérifie aussi ici que l'utilisateur est connecté
    if 'user' not in session:
        return jsonify({'error': 'Non autorisé. Veuillez vous connecter.'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'Aucune image envoyée'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nom de fichier invalide'}), 400

    if not client:
         return jsonify({'error': 'Erreur de configuration de l\'API (Clé manquante)'}), 500

    try:
        image_bytes = file.read()
        mime_type = file.content_type if file.content_type else "image/jpeg"

        prompt = (
            "Tu es un expert en trading (SMC, ICT, Price Action). "
            "Analyse cette capture d'écran de graphique. "
            "Donne une analyse claire : Tendance, Zones (OB, FVG), Signal (Buy/Sell/Wait), SL, TP1, TP2, TP3."
        )

        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt
            ]
        )

        return jsonify({'analysis': response.text})

    except Exception as e:
        print(f"Erreur : {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
