import json
import ollama
from config import MODEL_NAME

class IntentRouter:
    def __init__(self):
        self.model = MODEL_NAME

    def get_file_intent(self, user_input):
        prompt = f"""Analyse l'intention concernant les fichiers ou le projet.
Réponds UNIQUEMENT avec un objet JSON valide. 

Actions possibles : "set_working_dir", "open_file", "close_file", "reload_file", "none".
Si l'action nécessite un chemin ou nom de fichier, inclus-le dans la clé "path_raw".
IMPORTANT: Le chemin doit correspondre exactement à ce que l'utilisateur a écrit, sans normalisation volontaire. Échappe les anti-slashs Windows uniquement si c'est requis pour que le JSON soit valide.

Message : "{user_input}"
JSON :"""

        raw_content = ""
        try:
            response = ollama.chat(model=self.model, messages=[{'role': 'user', 'content': prompt}])
            raw_content = response['message']['content'].strip()
            
            # Extraction basique du bloc JSON si le modèle bavarde
            start = raw_content.find("{")
            end = raw_content.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("Aucun JSON trouvé")
                
            json_str = raw_content[start:end]
            
            data = json.loads(json_str)
            
            # Validation 1: doit être un dictionnaire
            if not isinstance(data, dict):
                raise ValueError("Le JSON root n'est pas un dictionnaire")
                
            # Validation 2: action autorisée
            action = data.get('action')
            valid_actions = ["set_working_dir", "open_file", "close_file", "reload_file", "none"]
            if action not in valid_actions:
                print(f"  [DEBUG ROUTER] Action non reconnue : {action}")
                return {"action": "none", "path_raw": None}
                
            # Validation 3: path_raw type
            path_raw = data.get('path_raw')
            if path_raw is not None and not isinstance(path_raw, str):
                print(f"  [DEBUG ROUTER] path_raw invalide : {path_raw}")
                return {"action": "none", "path_raw": None}
                
            print(f"  [DEBUG ROUTER] Intent détecté : {action}")
            print(f"  [DEBUG ROUTER] Chemin extrait brut : {path_raw}")
            return data
            
        except json.JSONDecodeError as e:
            print(f"  [DEBUG ROUTER] Erreur de parsing JSON stricte. Réponse brute : {raw_content}")
            return {"action": "none", "path_raw": None}
        except Exception as e:
            print(f"  [DEBUG ROUTER] Erreur inattendue : {e}")
            return {"action": "none", "path_raw": None}

    def process_intent(self, user_input, file_manager):
        """
        Analyse l'intention via LLM et exécute l'action appropriée via le file_manager.
        Retourne un dictionnaire structuré et standardisé pour l'interface appelante.
        """
        intent = self.get_file_intent(user_input)
        action = intent.get("action", "none")
        path_raw = intent.get("path_raw")

        result = {
            "handled": False,
            "action": action,
            "message": "",
            "system_context": ""
        }

        if action == "none":
            return result

        success = False
        msg = ""

        if action == "set_working_dir" and path_raw:
            success, msg = file_manager.set_working_dir(path_raw)
        elif action == "open_file" and path_raw:
            success, msg = file_manager.load_file(path_raw)
        elif action == "close_file":
            # Gère la fermeture avec ou sans path spécifique
            target_path = path_raw if path_raw else file_manager.current_file_path
            if target_path:
                success, msg = file_manager.close_file(target_path)
            else:
                msg = "Aucun fichier à fermer."
        elif action == "reload_file":
            target_path = path_raw if path_raw else file_manager.current_file_path
            if target_path:
                success, msg = file_manager.load_file(target_path)
                if success:
                    msg += " (Rechargé)"
            else:
                msg = "Aucun fichier à recharger."
        
        result["handled"] = True
        result["message"] = msg if msg else f"Action {action} non supportée ou incomplète."
        result["system_context"] = f"[{'SUCCÈS' if success else 'ERREUR'}] {result['message']}"

        return result
