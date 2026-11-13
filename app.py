import os
from flask import Flask, render_template, request, jsonify
from google import genai

app = Flask(__name__)

# 1. Récupération de la clé API depuis la variable d'environnement GOOGLE_API_KEY
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("Erreur : La variable d'environnement GOOGLE_API_KEY est manquante sur Render.")

# 2. Initialisation explicite du client Gemini avec la clé
client = genai.Client(api_key=api_key)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_chart():
    if 'file' not in request.files:
        return jsonify({'error': 'Aucune image envoyée'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nom de fichier invalide'}), 400

    try:
        # Lecture directe des octets de l'image
        image_bytes = file.read()

        # Sécurité pour le type MIME (au cas où le navigateur ne l'envoie pas correctement)
        mime_type = file.content_type if file.content_type else "image/jpeg"

        # Prompt expert SMC / ICT / OTE / POC
        prompt = (
            "Tu es un expert en trading institutionnel (SMC, ICT, Price Action, Fibonacci OTE, Volume Profile POC). "
            "Analyse cette capture d'écran MT5 (Timeframe M15 ou H1) et fournis une analyse claire structurée ainsi :\n\n"
            "1. **Tendance Actuelle :** (Haussière / Baissière / Neutre)\n"
            "2. **Zones Clés & Liquidité :** (Identification des Order Blocks (OB), Fair Value Gaps (FVG), zones de liquidité, niveaux OTE et POC)\n"
            "3. **Signal Proposé :** (Buy Now, Sell Now, Buy Limit ou Sell Limit)\n"
            "4. **Niveaux de Gestion du Risque :**\n"
            "   - Stop Loss (SL) :\n"
            "   - Take Profit 1 (TP1) :\n"
            "   - Take Profit 2 (TP2) :\n"
            "   - Take Profit 3 (TP3) :\n"
            "5. **Indice de Confiance :** (ex: 85%)\n\n"
            "Sois précis, professionnel et direct dans tes recommandations."
        )

        # Appel à Gemini 
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                {"mime_type": mime_type, "data": image_bytes},
                prompt
            ]
        )

        return jsonify({'analysis': response.text})

    except Exception as e:
        # Affiche l'erreur dans les logs Render pour faciliter le débogage
        print(f"Erreur lors de l'appel à Gemini : {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 3. Configuration OBLIGATOIRE pour Render
    # Render fournit un port dynamique via la variable d'environnement PORT
    port = int(os.environ.get("PORT", 10000))
    # On écoute sur 0.0.0.0 pour être accessible de l'extérieur
    app.run(host="0.0.0.0", port=port, debug=False)
