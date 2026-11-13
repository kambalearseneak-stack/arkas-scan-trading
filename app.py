import os
from flask import Flask, render_template, request, jsonify
from google import genai

app = Flask(__name__)

# Initialisation du client Gemini (la clé API est lue automatiquement depuis la variable d'environnement GEMINI_API_KEY sur Render)
client = genai.Client()

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
        # Lecture directe des octets de l'image (compatible avec Gemini sans Pillow)
        image_bytes = file.read()

        # Prompt expert SMC / ICT / OTE / POC basé sur tes stratégies de trading
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

        # Appel à Gemini avec le contenu binaire de l'image
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                {"mime_type": file.content_type, "data": image_bytes},
                prompt
            ]
        )

        return jsonify({'analysis': response.text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
