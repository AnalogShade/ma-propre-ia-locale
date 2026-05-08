import json
import ollama
from config import MODEL_NAME

class IntentRouter:
    def __init__(self):
        self.model = MODEL_NAME

    def get_file_intent(self, user_input):
        """Demande à l'IA d'analyser l'intention de l'utilisateur concernant les fichiers ou le projet."""
        prompt = f"""Analyse l'intention de l'utilisateur concernant la gestion de fichiers locaux ou du répertoire de travail.
Réponds UNIQUEMENT avec un objet JSON au format suivant :
{{
  "action": "open_file" | "close_file" | "reload_file" | "set_working_dir" | "none",
  "path": "nom_ou_chemin_du_fichier_ou_du_dossier" ou null
}}

Règles :
- "open_file" : l'utilisateur veut ouvrir, lire ou regarder un fichier précis.
- "close_file" : l'utilisateur veut fermer ou oublier un fichier.
- "reload_file" : l'utilisateur veut recharger ou actualiser un fichier.
- "set_working_dir" : l'utilisateur indique le dossier dans lequel il travaille, son dossier de projet, ou la racine de son travail.
- "none" : aucune action de fichier demandée (conversation normale).

Exemples :
"Ouvre config.py" -> {{"action": "open_file", "path": "config.py"}}
"Je travaille dans C:\MesProjets\Anna" -> {{"action": "set_working_dir", "path": "C:\\MesProjets\\Anna"}}
"Voici mon dossier de projet : ./src" -> {{"action": "set_working_dir", "path": "./src"}}
"Ferme le fichier" -> {{"action": "close_file", "path": null}}
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
                elif raw_content.startswith("{"):
                    pass # Déjà du JSON
                else:
                    raw_content = raw_content.strip()
            
            # On cherche le premier { et le dernier } pour isoler le JSON
            start = raw_content.find("{")
            end = raw_content.rfind("}") + 1
            if start != -1 and end != 0:
                data = json.loads(raw_content[start:end])
                return data
            return {"action": "none", "path": None}
        except Exception:
            return {"action": "none", "path": None}
