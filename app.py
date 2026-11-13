import os
from flask import Flask, render_template, request, jsonify
from google import genai
from PIL import Image

app = Flask(__name__)

# Initialisation du client Gemini
# Assure-toi que ta clé API GEMINI_API_KEY est bien configurée dans ton environnement
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
        # Ouvrir l'image avec PIL
        image = Image.open(file.stream)

        # Prompt expert SMC / ICT / OTE / POC basé sur tes notes
        prompt = (
            "Analyse cette capture d'écran de trading MT5 en utilisant les concepts SMC (Smart Money Concepts), "
            "ICT, Price Action, ainsi que la logique de Fibonacci (zones OTE) et le Volume Profile (POC). "
            "Donne-moi une analyse structurée sous format JSON ou clair avec :\n"
            "1. Tendance actuelle\n"
            "2. Zones d'intérêt (Order Blocks, FVG, liquidité, POC, zones OTE)\n"
            "3. Signal précis (Buy Now, Sell Now, Buy Limit, Sell Limit)\n"
            "4. Niveaux de Stop Loss (SL) et Take Profit (TP1, TP2, TP3)\n"
            "5. Indice de confiance en pourcent."
        )

        # Appel à Gemini avec le modèle multimodal
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt]
        )

        return jsonify({'analysis': response.text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
