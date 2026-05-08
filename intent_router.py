import json
import ollama
import re
from config import MODEL_NAME

class IntentRouter:
    def __init__(self):
        self.model = MODEL_NAME

    def get_file_intent(self, user_input):
        prompt = f"""Analyse l'intention concernant les fichiers ou le projet.
Réponds UNIQUEMENT avec un objet JSON. 
IMPORTANT : Échappe les anti-slashs Windows dans les chemins (ex: "C:\\\\Users").

Actions : "set_working_dir", "open_file", "none".
Message : "{user_input}"
JSON :"""

        try:
            response = ollama.chat(model=self.model, messages=[{'role': 'user', 'content': prompt}])
            raw_content = response['message']['content'].strip()
            
            # Nettoyage JSON
            start = raw_content.find("{")
            end = raw_content.rfind("}") + 1
            json_str = raw_content[start:end]
            
            # Correction manuelle des anti-slashs non échappés avant le parse
            # On cherche les backslashes qui ne sont pas déjà suivis d'un autre backslash ou d'un caractère d'échappement valide
            corrected_json = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', json_str)
            
            data = json.loads(corrected_json)
            print(f"  [DEBUG ROUTER] Intent détecté : {data.get('action')}")
            print(f"  [DEBUG ROUTER] Chemin extrait : {data.get('path')}")
            return data
        except Exception as e:
            print(f"  [DEBUG ROUTER] Erreur JSON : {e}")
            return {"action": "none", "path": None}
