import json
import ollama
from config import DEFAULT_MODEL_NAME

class IntentRouter:
    def __init__(self):
        self.model = DEFAULT_MODEL_NAME

    def get_file_intent(self, user_input):
        prompt = f"""Analyse UNIQUEMENT si le message utilisateur contient une commande EXPLICITE li\u00e9e aux fichiers ou aux r\u00e9pertoires.
R\u00e9ponds UNIQUEMENT avec un objet JSON valide. 

R\u00c8GLES CRITIQUES :
1. L'action "open_file" est r\u00e9serv\u00e9e \u00e0 l'ouverture d'un NOUVEAU document.
2. Si l'utilisateur demande de MODIFIER le contenu (ex: "ajoute", "remplace", "ecris"), retourne action: "none".
3. Une conversation normale NE doit PAS d\u00e9clencher d'action.
4. Si l'utilisateur demande d'ouvrir un fichier de mani\u00e8re g\u00e9n\u00e9rique SANS nommer de fichier (ex: "open the file", "ouvre un fichier"), retourne action: "open_file" et path_raw: null.

EXEMPLES N\u00c9GATIFS (action: "none") :
- "Ajoute du code dans le fichier"
- "Modifie la ligne 2"
- "Comment vas-tu ?"
- "?"

EXEMPLES POSITIFS :
- "Ouvre main.py" -> open_file, path_raw: "main.py"
- "Voici mon dossier C:\\Projet" -> set_working_dir, path_raw: "C:\\Projet"
- "Reload le fichier" -> reload_file, path_raw: null
- "Open the file" -> open_file, path_raw: null

Actions possibles : "set_working_dir", "open_file", "close_file", "reload_file", "none".
Si l'action n\u00e9cessite un chemin ou nom de fichier, inclus-le dans la cl\u00e9 "path_raw".

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
        # Garde-fou 0 : Messages courts et conversationnels évidents (pour éviter l'appel LLM)
        clean_input = user_input.lower().strip()
        blacklist = ["?", "??", "ca va?", "\u00e7a va?", "salut", "bonjour", "allo", "ok", "d'accord"]
        if clean_input in blacklist:
            return {"handled": False, "action": "none", "message": "", "system_context": ""}

        intent = self.get_file_intent(user_input)
        action = intent.get("action", "none")
        path_raw = intent.get("path_raw")

        # Garde-fou backend : rejeter les actions qui n'ont pas de chemin valide
        if action == "set_working_dir":
            if not path_raw or path_raw.strip() in ["?", ".", ""] or len(path_raw.strip()) < 2:
                print(f"  [DEBUG ROUTER] Garde-fou : action {action} rejet\u00e9e car path_raw '{path_raw}' est invalide.")
                action = "none"
                path_raw = None
        elif action == "open_file":
            # On accepte path_raw == None (qui devient None ici) pour les requ\u00eates g\u00e9n\u00e9riques
            if path_raw is not None and (path_raw.strip() in ["?", "."] or len(path_raw.strip()) < 2):
                print(f"  [DEBUG ROUTER] Garde-fou : action {action} rejet\u00e9e car path_raw '{path_raw}' est invalide.")
                action = "none"
                path_raw = None

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
            # On passe user_input pour permettre la r\u00e9solution intelligente
            success, msg = file_manager.load_file(path_raw, user_input=user_input)
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
