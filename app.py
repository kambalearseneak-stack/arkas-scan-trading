import os
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("Erreur : La variable d'environnement GOOGLE_API_KEY est manquante.")

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

    # Récupérer le mode (signal ou verify)
    mode = request.form.get('mode', 'signal')

    try:
        image_bytes = file.read()
        mime_type = file.content_type if file.content_type else "image/jpeg"

        # Prompt de base (extraction d'informations)
        base_prompt = (
            "Tu es un analyste expert en trading institutionnel (SMC, ICT, Price Action). "
            "Analyse cette capture d'écran de graphique financier (provenant de MT5, TradingView, etc.).\n\n"
            "**ÉTAPE 1 : LECTURE DU GRAPHIQUE**\n"
            "Extrais toutes les informations textuelles visibles : nom de l'actif (paire, indice), Timeframe, prix actuel, et tout indicateur présent.\n\n"
        )

        # Prompt spécifique selon le mode
        if mode == 'verify':
            specific_prompt = (
                "**ÉTAPE 2 : VÉRIFICATION D'ANALYSE**\n"
                "L'utilisateur a déjà une idée de trade ou une analyse. Vérifie si le graphique valide ou invalide une entrée en position. "
                "Identifie les pièges potentiels (faux départs, zones de liquidité non prises).\n"
                "Donne un avis clair : **VALIDÉ**, **À SURVEILLER**, ou **REJETÉ** avec les raisons SMC/ICT/Price Action.\n\n"
                "Structure ta réponse ainsi :\n"
                "1. Contexte du Graphique\n"
                "2. Vérification de la Structure (BOS, CHoCH)\n"
                "3. Zones de Confluence (OB, FVG, OTE, POC)\n"
                "4. Verdict de l'Analyse (Validé/Rejeté)\n"
                "5. Niveaux d'Invalidation (Stop Loss)"
            )
        else:
            specific_prompt = (
                "**ÉTAPE 2 : GÉNÉRATION DE SIGNAL**\n"
                "Fournis une analyse structurée pour trader :\n"
                "1. **Tendance Actuelle :** (Haussière / Baissière / Neutre)\n"
                "2. **Zones Clés & Liquidité :** (Order Blocks, FVG, BOS, zones de liquidité, OTE et POC)\n"
                "3. **Signal Proposé :** (Buy Now, Sell Now, Buy Limit, Sell Limit ou Attente)\n"
                "4. **Niveaux de Gestion du Risque :**\n"
                "   - Entrée :\n"
                "   - Stop Loss (SL) :\n"
                "   - Take Profit 1 (TP1) :\n"
                "   - Take Profit 2 (TP2) :\n"
                "   - Take Profit 3 (TP3) :\n"
                "5. **Indice de Confiance :** (ex: 85%)"
            )

        prompt_final = base_prompt + specific_prompt

        # Appel à Gemini
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt_final
            ]
        )

        return jsonify({'analysis': response.text})

    except Exception as e:
        print(f"Erreur : {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
