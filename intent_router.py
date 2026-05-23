import json
import ollama
from config import DEFAULT_MODEL_NAME

class IntentRouter:
    def __init__(self):
        self.model = DEFAULT_MODEL_NAME

    def get_file_intent(self, user_input):
        prompt = f"""Analyse le message de l'utilisateur pour détecter s'il demande une opération sur un répertoire ou fait référence à un ou plusieurs fichiers (pour les lire, les analyser, les ouvrir ou les modifier).
Réponds UNIQUEMENT avec un objet JSON valide.

Actions possibles :
1. "set_working_dir" : Définit un nouveau répertoire de travail (ex: "Voici mon dossier C:\\Projet").
   Requiert la clé "path_raw" contenant le chemin absolu.
2. "load_context" : L'utilisateur fait référence à un ou plusieurs fichiers (ex: "ouvre main.py", "dans gui.py ajoute...", "regarde le code").
   Requiert la clé "targets" contenant la liste des noms de fichiers (ex: ["main.py"]).
3. "close_file" : Ferme le fichier actif (ex: "ferme le fichier").
4. "reload_file" : Recharge le fichier actif (ex: "recharge le fichier").
5. "none" : Conversation courante, salutations ou questions générales sans mention de fichier ou de dossier.

RÈGLES CRITIQUES :
1. Si l'utilisateur parle d'un fichier (même pour demander d'y ajouter ou modifier du code), retourne l'action "load_context" avec le ou les fichiers dans la liste "targets".
2. Ne fais aucune supposition : si aucun fichier ou dossier n'est mentionné, retourne l'action "none".

EXEMPLES :
- "Voici mon dossier C:\\Dev" -> {{"action": "set_working_dir", "path_raw": "C:\\\\Dev"}}
- "Ouvre le fichier main.py" -> {{"action": "load_context", "targets": ["main.py"]}}
- "Ajoute un bouton dans gui.py" -> {{"action": "load_context", "targets": ["gui.py"]}}
- "Compare main.py et gui.py" -> {{"action": "load_context", "targets": ["main.py", "gui.py"]}}
- "Comment vas-tu ?" -> {{"action": "none"}}

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
            valid_actions = ["set_working_dir", "open_file", "close_file", "reload_file", "load_context", "none"]
            if action not in valid_actions:
                print(f"  [DEBUG ROUTER] Action non reconnue : {action}")
                return {"action": "none", "path_raw": None, "targets": []}
                
            # Validation 3: path_raw type
            path_raw = data.get('path_raw')
            if path_raw is not None and not isinstance(path_raw, str):
                print(f"  [DEBUG ROUTER] path_raw invalide : {path_raw}")
                path_raw = None
                
            # Validation 4: targets type (pour load_context)
            targets = data.get('targets', [])
            if isinstance(targets, str):
                targets = [targets]
            elif not isinstance(targets, list):
                targets = []
            
            # Nettoyer les cibles
            targets = [str(t).strip() for t in targets if t]
            data['targets'] = targets
            data['path_raw'] = path_raw
                
            print(f"  [DEBUG ROUTER] Intent détecté : {action}")
            if path_raw:
                print(f"  [DEBUG ROUTER] Chemin extrait brut : {path_raw}")
            if targets:
                print(f"  [DEBUG ROUTER] Cibles de contexte : {targets}")
            return data
            
        except json.JSONDecodeError as e:
            print(f"  [DEBUG ROUTER] Erreur de parsing JSON stricte. Réponse brute : {raw_content}")
            return {"action": "none", "path_raw": None, "targets": []}
        except Exception as e:
            print(f"  [DEBUG ROUTER] Erreur inattendue : {e}")
            return {"action": "none", "path_raw": None, "targets": []}

    def process_intent(self, user_input, file_manager):
        """
        Analyse l'intention via LLM et exécute l'action appropriée via le file_manager.
        Retourne un dictionnaire structuré et standardisé pour l'interface appelante.
        """
        # Garde-fou 0 : Messages courts et conversationnels évidents (pour éviter l'appel LLM)
        clean_input = user_input.lower().strip()
        blacklist = ["?", "??", "ca va?", "ça va?", "salut", "bonjour", "allo", "ok", "d'accord"]
        if clean_input in blacklist:
            return {"handled": False, "action": "none", "message": "", "system_context": ""}

        intent = self.get_file_intent(user_input)
        action = intent.get("action", "none")
        path_raw = intent.get("path_raw")
        targets = intent.get("targets", [])

        # Garde-fou backend : rejeter les actions qui n'ont pas de chemin valide
        if action == "set_working_dir":
            if not path_raw or path_raw.strip() in ["?", ".", ""] or len(path_raw.strip()) < 2:
                print(f"  [DEBUG ROUTER] Garde-fou : action {action} rejetée car path_raw '{path_raw}' est invalide.")
                action = "none"
                path_raw = None
        elif action == "open_file":
            if path_raw is not None and (path_raw.strip() in ["?", "."] or len(path_raw.strip()) < 2):
                print(f"  [DEBUG ROUTER] Garde-fou : action {action} rejetée car path_raw '{path_raw}' est invalide.")
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
            result["handled"] = True
            result["message"] = msg
            result["system_context"] = f"[{'SUCCÈS' if success else 'ERREUR'}] {msg}"
        elif action == "load_context" and targets:
            loaded_list = []
            for target in targets:
                # Utiliser la méthode load_file existante de file_manager
                success, msg = file_manager.load_file(target, user_input=user_input)
                if success:
                    loaded_list.append(target)
            
            if loaded_list:
                result["handled"] = False # CRITIQUE : non-bloquant pour continuer vers l'IA principale !
                result["message"] = f"Contexte chargé : {', '.join(loaded_list)}"
                result["system_context"] = f"[SUCCÈS] {result['message']}"
                print(f"  [DEBUG ROUTER] Chargement sémantique réussi pour : {loaded_list}")
            else:
                result["handled"] = False
                result["message"] = "Aucun fichier correspondant n'a été trouvé dans le répertoire."
                result["system_context"] = f"[ERREUR] {result['message']}"
        elif action == "open_file" and path_raw:
            success, msg = file_manager.load_file(path_raw, user_input=user_input)
            result["handled"] = True
            result["message"] = msg
            result["system_context"] = f"[{'SUCCÈS' if success else 'ERREUR'}] {msg}"
        elif action == "close_file":
            target_path = path_raw if path_raw else file_manager.current_file_path
            if target_path:
                success, msg = file_manager.close_file(target_path)
            else:
                msg = "Aucun fichier à fermer."
            result["handled"] = True
            result["message"] = msg
            result["system_context"] = f"[{'SUCCÈS' if success else 'ERREUR'}] {msg}"
        elif action == "reload_file":
            target_path = path_raw if path_raw else file_manager.current_file_path
            if target_path:
                success, msg = file_manager.load_file(target_path)
                if success:
                    msg += " (Rechargé)"
            else:
                msg = "Aucun fichier à recharger."
            result["handled"] = True
            result["message"] = msg
            result["system_context"] = f"[{'SUCCÈS' if success else 'ERREUR'}] {msg}"

        return result
