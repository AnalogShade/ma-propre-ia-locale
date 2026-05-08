import json
import ollama
from config import MODEL_NAME

class IntentRouter:
    def __init__(self):
        self.model = MODEL_NAME

    def get_file_intent(self, user_input):
        prompt = f"""Analyse l'intention de l'utilisateur concernant les fichiers ou le projet.
Réponds UNIQUEMENT avec un objet JSON strict.

Règles d'extraction du chemin (path) :
- Extraire le chemin COMPLET, y compris les espaces.
- Convertir les doubles anti-slash en simples si nécessaire, ou préserver le format brut.
- Ne pas s'arrêter au premier espace.

Actions :
- "set_working_dir" : l'utilisateur définit son dossier de travail, son répertoire ou son projet.
- "open_file" : l'utilisateur veut lire ou ouvrir un fichier.
- "none" : conversation normale.

Exemples :
"voici mon répertoire de travail C:\\Users\\Louis\\Desktop\\mon projet" -> {{"action": "set_working_dir", "path": "C:\\Users\\Louis\\Desktop\\mon projet"}}
"Ouvre le fichier main.py" -> {{"action": "open_file", "path": "main.py"}}

Message : "{user_input}"
JSON :"""

        try:
            response = ollama.chat(model=self.model, messages=[{'role': 'user', 'content': prompt}])
            raw_content = response['message']['content'].strip()
            
            # Nettoyage JSON
            if "```" in raw_content:
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"): raw_content = raw_content[4:].strip()
            
            start = raw_content.find("{")
            end = raw_content.rfind("}") + 1
            data = json.loads(raw_content[start:end])
            
            # DEBUG
            print(f"  [DEBUG ROUTER] Intent détecté : {data.get('action')}")
            print(f"  [DEBUG ROUTER] Chemin extrait : {data.get('path')}")
            
            return data
        except Exception as e:
            print(f"  [DEBUG ROUTER] Erreur : {e}")
            return {"action": "none", "path": None}
