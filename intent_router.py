import json
import ollama
from config import MODEL_NAME

class IntentRouter:
    def __init__(self):
        self.model = MODEL_NAME

    def get_file_intent(self, user_input):
        """Demande à l'IA d'analyser l'intention de l'utilisateur concernant les fichiers."""
        prompt = f"""Analyse l'intention de l'utilisateur concernant la gestion de fichiers locaux.
Réponds UNIQUEMENT avec un objet JSON au format suivant :
{{
  "action": "open_file" | "close_file" | "reload_file" | "none",
  "path": "nom_ou_chemin_du_fichier" ou null
}}

Règles :
- "open_file" : l'utilisateur veut ouvrir, lire, charger ou regarder un fichier.
- "close_file" : l'utilisateur veut fermer, oublier ou retirer un fichier.
- "reload_file" : l'utilisateur veut recharger, relire ou actualiser un fichier.
- "none" : aucune action de fichier demandée (conversation normale).

Exemples :
"Ouvre config.py" -> {{"action": "open_file", "path": "config.py"}}
"Ferme-le" -> {{"action": "close_file", "path": null}}
"Hello !" -> {{"action": "none", "path": null}}

Message utilisateur : "{user_input}"
JSON :"""

        try:
            response = ollama.chat(model=self.model, messages=[
                {'role': 'user', 'content': prompt}
            ])
            
            raw_content = response['message']['content'].strip()
            
            # Nettoyage basique si l'IA ajoute des balises ```json
            if "```" in raw_content:
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:].strip()
            
            data = json.loads(raw_content)
            return data
        except Exception as e:
            # En cas d'erreur (JSON mal formé, timeout, etc.), on retourne "none"
            return {"action": "none", "path": None}
