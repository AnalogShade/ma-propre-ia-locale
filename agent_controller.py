import threading
import os
import time
import ollama
from config import (
    SETTINGS_FILE, DEFAULT_MODEL_NAME, 
    SELECTIVE_MEMORY_OBSERVATION, ENABLE_SELECTIVE_MEMORY,
    DEFAULT_HISTORY_CONTEXT_SIZE, DEFAULT_ENABLE_COMPRESSED_CONTEXT,
    COMPRESSED_CONTEXT_FILE, CONTEXT_WINDOW
)
from settings_manager import SettingsManager
from ai_engine import AIEngine
from memory_manager import MemoryManager
from file_manager import FileManager
from intent_router import IntentRouter
from code_editor import CodeEditor
from image_generation_manager import ImageGenerationManager
from memory_retriever import MemoryRetriever
from command_runner import CommandRunner

class AgentController:
    def __init__(self):
        """
        Initialise le contrôleur central d'Anna.
        Ce contrôleur regroupe et coordonne tous les services métiers :
        - Réglages techniques (SettingsManager)
        - Moteur IA local (AIEngine)
        - Mémoire long terme et court terme (MemoryManager)
        - Gestion de fichiers et contexte (FileManager)
        - Routeur d'intentions sémantiques (IntentRouter)
        - Éditeur de code sécurisé (CodeEditor)
        - Exécuteur de commandes (CommandRunner)
        """
        # 1. Chargement et configuration des réglages
        self.settings = SettingsManager(SETTINGS_FILE)
        saved_model = self.settings.get_setting("selected_model", DEFAULT_MODEL_NAME)
        
        # 2. Initialisation des gestionnaires métiers
        self.engine = AIEngine()
        self.engine.model = saved_model
        
        self.memory = MemoryManager()
        self.files = FileManager()
        
        self.router = IntentRouter()
        self.router.model = saved_model
        
        self.editor = CodeEditor()
        self.retriever = MemoryRetriever()
        self.command_runner = CommandRunner(self)
        
        # 3. Initialisation du gestionnaire de génération d'images (MVC)
        self.image_manager = ImageGenerationManager(self.engine)

    def detect_working_mode(self, user_input, intent_action):
        """
        Détermine dynamiquement le mode de travail (CHAT ou CODE)
        et fournit la raison de cette classification.
        """
        # 1. Règle absolue : si un ou plusieurs fichiers sont ouverts dans le workspace
        if self.files.loaded_files:
            return "CODE", "Fichier(s) ouvert(s) dans le workspace."
            
        # 2. Règle sémantique : si l'action du routeur concerne le contexte de fichiers ou la recherche
        if intent_action in ["load_context", "open_file", "reload_file", "search"]:
            return "CODE", f"Intention technique détectée par le routeur ({intent_action})."
            
        # 3. Règle heuristique : mots-clés techniques
        import re
        technical_keywords = {
            "code", "python", "classe", "class", "fonction", "def", "import", "bug", "erreur", 
            "error", "corriger", "corrige", "modifier", "script", "programme", "développer", 
            "compil", "fichiers", "git", "main.py", "tic-tac-toe", "tic tac toe", "jeu", "boucle"
        }
        # Normalisation simple du texte
        words = set(re.sub(r"[^\w\s]", " ", user_input.lower()).split())
        matched = words.intersection(technical_keywords)
        if matched:
            return "CODE", f"Mots-clés techniques détectés dans le message : {', '.join(matched)}."
            
        return "CHAT", "Aucun fichier ouvert, intention neutre et absence de termes techniques."

    def start_image_session(self):
        """
        Démarre une nouvelle session interactive de génération d'images.
        """
        self.image_manager.start_session()

    def change_model(self, model_name):
        """
        Permet de commuter intelligemment le modèle Ollama actif.
        Vérifie la présence locale du modèle et met à jour les réglages de manière persistante.
        """
        models = self.engine.get_installed_models()
        matched_model = None
        if models:
            if model_name in models:
                matched_model = model_name
            else:
                # Match intelligent (ex: "llama3" correspond à "llama3:latest")
                for m in models:
                    if m.split(':')[0] == model_name.split(':')[0]:
                        matched_model = m
                        break
        
        target_model = matched_model if matched_model else model_name
        self.engine.model = target_model
        self.router.model = target_model
        self.settings.set_setting("selected_model", target_model)
        return target_model

    def clear_history(self):
        """Efface l'historique court terme en mémoire."""
        self.memory.clear()
        if os.path.exists(COMPRESSED_CONTEXT_FILE):
            try:
                os.remove(COMPRESSED_CONTEXT_FILE)
            except Exception:
                pass
        self.settings.set_setting("last_consolidated_count", 0)

    def _trigger_context_consolidation(self, older_count):
        """Lance une consolidation asynchrone en arrière-plan."""
        def task():
            try:
                last_consolidated = self.settings.get_setting("last_consolidated_count", 0)
                new_messages_slice = self.memory.history[last_consolidated:older_count]
                
                # Lire l'ancien tampon
                old_buffer = ""
                if os.path.exists(COMPRESSED_CONTEXT_FILE):
                    try:
                        with open(COMPRESSED_CONTEXT_FILE, "r", encoding="utf-8") as f:
                            old_buffer = f.read().strip()
                    except Exception:
                        pass
                
                # Formater les nouveaux messages
                new_messages_text = ""
                for msg in new_messages_slice:
                    role_display = "Vous" if msg["role"] == "user" else "Anna"
                    timestamp = msg.get("timestamp", "")
                    ts_display = f" [{timestamp}]" if timestamp else ""
                    new_messages_text += f"{ts_display} {role_display} : {msg['content']}\n"
                
                # Construire le prompt de consolidation
                prompt = f"""Tu es un outil d'archivage et de compression de contexte. 
Voici le tampon de contexte compressé précédent : 
[ANCIEN TAMPON]
{old_buffer if old_buffer else "(Aucun ancien tampon)"}

Voici les nouveaux messages échangés depuis la dernière mise à jour :
[NOUVEAUX MESSAGES]
{new_messages_text}

Met à jour et remplace le tampon en fusionnant ces informations. Le nouveau tampon doit conserver :
- Les décisions importantes prises durant la conversation.
- Les projets en cours et conclusions techniques.
- Les préférences de l'utilisateur découvertes.
- L'état général de la discussion.

Règles strictes :
1. Reste extrêmement factuel et concis (budget de 100 à 300 mots maximum).
2. Renvoie UNIQUEMENT le nouveau tampon sous forme de liste de points clés (bullet points), sans formules de politesse ni bavardage.
"""
                target_model = self.engine.model
                print(f"[CONSOLIDATION] Consolidation en cours de {len(new_messages_slice)} messages...")
                
                response = ollama.chat(
                    model=target_model,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                new_buffer = response.get("message", {}).get("content", "").strip()
                
                # Nettoyer d'éventuels blocs de réflexion générés par le modèle lors de la consolidation
                if "<think>" in new_buffer:
                    parts = new_buffer.split("<think>", 1)
                    before = parts[0]
                    rest = parts[1]
                    if "</think>" in rest:
                        new_buffer = before + rest.split("</think>", 1)[1]
                    else:
                        new_buffer = before
                    new_buffer = new_buffer.strip()
                
                if new_buffer:
                    # Sauvegarder
                    os.makedirs(os.path.dirname(COMPRESSED_CONTEXT_FILE), exist_ok=True)
                    with open(COMPRESSED_CONTEXT_FILE, "w", encoding="utf-8") as f:
                        f.write(new_buffer)
                    
                    # Mettre à jour l'index de consolidation
                    self.settings.set_setting("last_consolidated_count", older_count)
                    print(f"[CONSOLIDATION SUCCÈS] Tampon mis à jour. Index consolidé : {older_count}")
                else:
                    print("[CONSOLIDATION WARNING] Le modèle a renvoyé un tampon vide, annulation.")
                    
            except Exception as e:
                print(f"[CONSOLIDATION ERROR] Échec de la consolidation du contexte : {e}")

        threading.Thread(target=task, daemon=True).start()

    def _trigger_background_memory_task(self, user_msg, sys_trace_callback=None):
        """Lance une tâche asynchrone en tâche de fond pour l'extraction de faits en mémoire."""
        def task():
            if sys_trace_callback:
                sys_trace_callback(f"[Appel LLM] Lancement : extraction de faits (Arrière-plan)\n  - Modèle : {self.engine.model}\n  - Rôle : extract_fact")
            start_time = time.time()
            try:
                fact = self.engine.extract_fact(user_msg)
                duration = time.time() - start_time
                if sys_trace_callback:
                    fact_str = str(fact)
                    display_fact = fact_str if len(fact_str) <= 500 else fact_str[:500] + "\n[... TRONQUÉ ...]"
                    sys_trace_callback(f"[Appel LLM] Terminé : extraction de faits (Durée : {duration:.2f}s)\n  - Fait extrait : {display_fact}")
                if fact:
                    self.memory.process_extracted_fact(fact)
            except Exception as e:
                duration = time.time() - start_time
                if sys_trace_callback:
                    sys_trace_callback(f"[Appel LLM] Échec : extraction de faits (Durée : {duration:.2f}s) - Erreur : {e}")
                print(f"[CONTROLLER WARNING] Échec de l'extraction de faits en arrière-plan : {e}")
                
        threading.Thread(target=task, daemon=True).start()

    def process_slash_command(self, msg):
        """
        Détecte et traite une commande slash.
        Retourne un dictionnaire unifié contenant les informations de résultat si c'est une commande slash,
        ou None s'il s'agit d'un message en langage naturel normal.
        """
        clean_msg = msg.strip()
        if not clean_msg.startswith('/'):
            return None
            
        parts = clean_msg.split(' ')
        cmd = parts[0].lower()
        
        if cmd == '/model':
            if len(parts) > 1:
                model_name = parts[1].strip()
                target_model = self.change_model(model_name)
                return {"handled": True, "action": "change_model", "message": f"Modèle commuté vers : {target_model}"}
            else:
                return {"handled": True, "action": "get_model", "message": f"Modèle actuellement actif : {self.engine.model}. Pour changer, tape : /model <nom>"}
                
        elif cmd == '/clear':
            self.clear_history()
            return {"handled": True, "action": "clear_history", "message": "Historique de discussion effacé."}
            
        elif cmd == '/openfile' and len(parts) > 1:
            success, response = self.files.load_file(parts[1])
            return {"handled": True, "action": "open_file", "success": success, "message": response}
            
        elif cmd == '/listfiles':
            return {"handled": True, "action": "list_files", "message": self.files.list_files()}
            
        elif cmd == '/closefile':
            target = parts[1] if len(parts) > 1 else None
            success, response = self.files.close_file(target)
            return {"handled": True, "action": "close_file", "success": success, "message": response}
            
        elif cmd == '/closeall':
            success, response = self.files.close_all_files()
            return {"handled": True, "action": "close_all", "success": success, "message": response}
            
        elif (cmd == '/search' or cmd == '/grep') and len(parts) > 1:
            query = " ".join(parts[1:]).strip()
            success, results, truncated = self.files.search_text(query)
            if not success:
                return {"handled": True, "action": "search", "success": False, "message": results}
                
            if not results:
                return {"handled": True, "action": "search", "success": True, "message": f"Aucun résultat trouvé pour '{query}'."}
                
            msg_lines = [f"Résultats de recherche pour '{query}' :"]
            for r in results:
                msg_lines.append(f"- {r['file']}:{r['line_num']}: {r['content']}")
            if truncated:
                msg_lines.append("\n[Attention: Résultats tronqués (limite de 5 correspondances par fichier ou 50 correspondances globales atteinte)]")
            return {"handled": True, "action": "search", "success": True, "message": "\n".join(msg_lines)}
            
        elif cmd == '/reloadfile' and len(parts) > 1:
            success, response = self.files.load_file(parts[1])
            return {"handled": True, "action": "reload_file", "success": success, "message": f"{response} (Rechargé)"}
            
        elif cmd == '/help':
            help_text = """COMMANDES DISPONIBLES :
/model <nom>       : Changer le modèle Ollama
/clear             : Effacer l'historique de discussion court terme
/openfile <chemin> : Charger un fichier texte dans le contexte
/listfiles         : Voir l'arborescence des fichiers (ouvert/disponible)
/closefile [nom]   : Fermer le fichier actif ou un fichier spécifique
/closeall          : Fermer tous les fichiers chargés en contexte
/search <terme>    : Rechercher du texte (grep) dans les fichiers du projet
/reloadfile <nom>  : Recharger le fichier modifié
/help              : Afficher cette aide
/quit              : Quitter l'application (en mode console)"""
            return {"handled": True, "action": "help", "message": help_text}
            
        elif cmd == '/quit':
            return {"handled": True, "action": "quit", "message": "Au revoir !"}
            
        return {"handled": True, "action": "unknown", "message": f"Commande slash inconnue : {cmd}"}

    def process_user_message_sync(self, user_input, images=None, chunk_callback=None, status_callback=None, on_start_callback=None, sys_trace_callback=None):
        """
        Traite un message utilisateur en langage naturel de manière synchrone.
        Retourne un dictionnaire unifié contenant les résultats IA et système.
        """
        # 0. Interception sémantique si le mode génération d'images est actif (LLM-First)
        if hasattr(self, 'image_manager') and self.image_manager.is_active():
            return self.image_manager.process_user_message(user_input, self.engine)

        original_system_prompt = self.engine.system_prompt

        if sys_trace_callback:
            sys_trace_callback("=== DÉBUT PRÉPARATION DU CONTEXTE ===")
            sys_trace_callback(f"[Système] Modèle actif : {self.engine.model}")
        
        start_context_prep = time.time()

        if status_callback:
            status_callback("Préparation du contexte...")

        # 1. Lancement de l'extraction de faits en tâche de fond
        if sys_trace_callback:
            sys_trace_callback("[Mémoire] Lancement de l'extraction de faits en tâche de fond...")
        self._trigger_background_memory_task(user_input, sys_trace_callback=sys_trace_callback)
        
        # 2. Détection d'intention sémantique via IntentRouter (LLM-First)
        if sys_trace_callback:
            sys_trace_callback("[Routage] Analyse de l'intention sémantique via IntentRouter...")
        intent_result = self.router.process_intent(user_input, self.files, sys_trace_callback=sys_trace_callback)
        if sys_trace_callback:
            sys_trace_callback(f"[Routage] Action d'intention : {intent_result.get('action')}")
            
        if intent_result.get("handled"):
            # Enregistrement système dans la mémoire pour préserver l'historique court terme
            self.memory.add_message("user", user_input)
            self.memory.add_message("assistant", intent_result.get("system_context"))
            prep_duration = time.time() - start_context_prep
            if sys_trace_callback:
                sys_trace_callback(f"=== FIN PRÉPARATION (Intention traitée - Durée : {prep_duration:.2f}s) ===")
            return {
                "type": "intent_handled",
                "action": intent_result.get("action"),
                "message": intent_result.get("message"),
                "system_context": intent_result.get("system_context")
            }

        # Couche de sécurité additive (fallback) pour la résolution de fichiers implicites
        if intent_result.get("action") == "none" and self.files.working_dir:
            if sys_trace_callback:
                sys_trace_callback("[Sécurité] Scan récursif des fichiers disponibles du projet...")
            available_files = self.files.get_available_files()
            if sys_trace_callback:
                sys_trace_callback(f"[Sécurité] {len(available_files)} fichier(s) disponible(s) dans le répertoire")
            if available_files:
                if status_callback:
                    status_callback("Analyse de sécurité du contexte...")
                resolution = self.router.resolve_context_required(user_input, available_files, sys_trace_callback=sys_trace_callback)
                if sys_trace_callback:
                    sys_trace_callback(f"[Sécurité] Résultat résolution contexte : action={resolution.get('action')} | confiance={resolution.get('confidence'):.2f} | raison='{resolution.get('reason')}'")
                if resolution.get("action") == "load_context":
                    confidence = resolution.get("confidence", 0.0)
                    targets = resolution.get("targets", [])
                    reason = resolution.get("reason", "")
                    if confidence >= 0.70 and targets:
                        print(f"  [SAFETY PIPELINE] Résolution de contexte réussie (confiance: {confidence}, raison: {reason}). Chargement automatique de : {targets}")
                        if sys_trace_callback:
                            sys_trace_callback(f"[Sécurité] Confiance ({confidence:.2f} >= 0.70) validée. Chargement automatique de : {targets}")
                        loaded_list = []
                        for target in targets:
                            success, msg = self.files.load_file(target, user_input=user_input)
                            if success:
                                loaded_list.append(target)
                                if sys_trace_callback:
                                    sys_trace_callback(f"  - [Fichier] '{target}' chargé avec succès")
                            else:
                                if sys_trace_callback:
                                    sys_trace_callback(f"  - [Fichier] Échec chargement '{target}' : {msg}")
                        
                        if loaded_list:
                            loaded_msg = f"Contexte de sécurité chargé automatiquement : {', '.join(loaded_list)}"
                            intent_result["action"] = "load_context"
                            intent_result["message"] = loaded_msg
                            intent_result["system_context"] = f"[SUCCÈS] {loaded_msg}"
                            print(f"  [SAFETY PIPELINE] {loaded_msg}")
                        else:
                            print(f"  [SAFETY PIPELINE] Aucun fichier n'a pu être chargé parmi les cibles : {targets}")
                    else:
                        print(f"  [SAFETY PIPELINE] Pas de chargement automatique (action: load_context, confiance insuffisante: {confidence:.2f}, raison: {reason})")
                else:
                    print(f"  [SAFETY PIPELINE] Pas de chargement automatique (action: none, raison: {resolution.get('reason', 'Aucune')})")
            
        # 3. Vérification garde-fou : besoin d'un répertoire de travail actif ou d'un fichier pour certaines requêtes sémantiques détectées
        file_actions_requiring_workspace = ["load_context", "close_file", "reload_file", "open_file"]
        if not self.files.working_dir and not self.files.last_file_load_success:
            if intent_result.get("action") in file_actions_requiring_workspace:
                msg = "Aucun répertoire de travail ni fichier n'est défini. Spécifie d'abord ton dossier (ex: 'Voici mon dossier C:\\Projet')."
                prep_duration = time.time() - start_context_prep
                if sys_trace_callback:
                    sys_trace_callback(f"[Erreur] Action '{intent_result.get('action')}' impossible sans espace de travail.")
                    sys_trace_callback(f"=== FIN PRÉPARATION (Abandon - Durée : {prep_duration:.2f}s) ===")
                return {
                    "type": "error",
                    "message": msg
                }
            
        # Récupération sélective de la mémoire (mode observation)
        if sys_trace_callback:
            sys_trace_callback("[Mémoire] Récupération sélective dans la mémoire à court et long terme...")
        memory_sources = {
            "user_profile": self.memory.user_profile,
            "assistant_profile": self.memory.assistant_profile,
            "facts": self.memory.facts
        }
        retrieved = self.retriever.retrieve(user_input, memory_sources)
        
        if SELECTIVE_MEMORY_OBSERVATION:
            from config import CORE_MEMORY_IDS
            dynamic_selected_count = len([f for f in retrieved.injected_facts if f["id"] not in CORE_MEMORY_IDS])
            core_selected_count = len(retrieved.injected_facts) - dynamic_selected_count
            print("\n[DEBUG MEMORY RETRIEVER]")
            print(f"- Mots-clés détectés : {', '.join(retrieved.keywords_detected) if retrieved.keywords_detected else 'Aucun'}")
            print(f"- Faits sélectionnés : {dynamic_selected_count}")
            print(f"- Faits ignorés : {retrieved.ignored_count}")
            print("- Faits retenus :")
            if retrieved.debug_details:
                for item in retrieved.debug_details:
                    print(f"  - {item['id']} | score {item['score']} | raison : {', '.join(item['reasons'])}")
            else:
                print("  - Aucun")
            print()
            
            if sys_trace_callback:
                sys_trace_callback(f"[Mémoire] Résultats MemoryRetriever :\n  - Mots-clés détectés : {', '.join(retrieved.keywords_detected) if retrieved.keywords_detected else 'aucun'}\n  - Faits permanents injectés : {core_selected_count}\n  - Faits dynamiques sélectionnés : {dynamic_selected_count}\n  - Faits ignorés : {retrieved.ignored_count}")
                if retrieved.debug_details:
                    details_list = []
                    for item in retrieved.debug_details:
                        details_list.append(f"    • {item['id']} | score {item['score']} | raisons : {', '.join(item['reasons'])}")
                    sys_trace_callback("[Mémoire] Détails des faits dynamiques sélectionnés :\n" + "\n".join(details_list))

        # 4. Appel de l'IA principal
        if ENABLE_SELECTIVE_MEMORY:
            # Construire des résumés à partir des fiches sélectionnées par le retriever
            user_facts = [f for f in retrieved.injected_facts if f["category"] in ("user_profile", "long_term_facts")]
            if user_facts:
                user_summary = "\n--- CE QUE TU SAIS SUR L'HUMAIN (Louis) ---\n"
                profile_facts = [f for f in user_facts if f["category"] == "user_profile"]
                long_facts = [f for f in user_facts if f["category"] == "long_term_facts"]
                for f in profile_facts:
                    user_summary += f"- {f['text']}\n"
                if long_facts:
                    user_summary += "\nFaits marquants et préférences :\n"
                    for f in long_facts:
                        user_summary += f"- {f['text']}\n"
                user_summary += "--- FIN DES CONNAISSANCES ---\n"
            else:
                user_summary = ""
                
            assistant_facts = [f for f in retrieved.injected_facts if f["category"] == "assistant_profile"]
            if assistant_facts:
                assistant_summary = "\n--- TON IDENTITÉ ET TES TRAITS ---\n"
                for f in assistant_facts:
                    assistant_summary += f"- {f['text']}\n"
                assistant_summary += "--- FIN DE TON IDENTITÉ ---\n"
            else:
                assistant_summary = ""
        else:
            # Comportement d'origine préservé
            user_summary = self.memory.get_user_info_summary()
            assistant_summary = self.memory.get_assistant_info_summary()

        files_context = self.files.get_context_for_ai()
        assistant_name = self.memory.assistant_profile.get("nom", "Anna")
        
        # Récupération de la configuration dynamique du contexte
        context_size = self.settings.get_setting("history_context_size", DEFAULT_HISTORY_CONTEXT_SIZE)
        enable_compressed = self.settings.get_setting("enable_compressed_context", DEFAULT_ENABLE_COMPRESSED_CONTEXT)
        
        compressed_context = ""
        if enable_compressed and os.path.exists(COMPRESSED_CONTEXT_FILE):
            try:
                with open(COMPRESSED_CONTEXT_FILE, "r", encoding="utf-8") as f:
                    compressed_context = f.read().strip()
            except Exception as e:
                print(f"[CONTROLLER WARNING] Impossible de lire le tampon de contexte : {e}")
        
        self.memory.add_message("user", user_input)
        context = self.memory.get_context(context_size)
        
        # === ÉTAPE 1 : DÉTECTION ADAPTATIVE DU CONTEXTE (SQUELETTE DE LA PHASE 1) ===
        intent_action = intent_result.get("action") if isinstance(intent_result, dict) else None
        active_mode, mode_reason = self.detect_working_mode(user_input, intent_action)
        
        # Enregistrement et log diagnostique
        mode_diag_report = (
            f"\n[DIAGNOSTIC ADAPTATIF - PHASE 1]\n"
            f"  - Mode détecté : {active_mode}\n"
            f"  - Raison : {mode_reason}\n"
            f"  - Action active du routeur : {intent_action}\n"
            f"  - Fichiers ouverts dans le workspace : {list(self.files.loaded_files.keys())}\n"
        )
        print(mode_diag_report)
        from config import log_diagnostic
        log_diagnostic(mode_diag_report)
        if sys_trace_callback:
            sys_trace_callback(mode_diag_report)

        # === ÉTAPE 2 : ÉLAGAGE DU CONTEXTE (PHASE 2) ===
        pruned_user_facts_count = 0
        original_history_count = len(context)
        
        if active_mode == "CODE":
            # 1. Chargement du code brut (sans numéros de ligne)
            files_context = self.files.get_context_for_ai(numbered=False)
            
            # 2. Retrait de la personnalité d'Anna
            assistant_summary = ""
            
            # 3. Masquage du contexte compressé conversationnel
            compressed_context = ""
            
            # 4. Filtrage de la mémoire utilisateur / faits du projet
            if ENABLE_SELECTIVE_MEMORY:
                technical_keywords = {"projet", "code", "python", "jeu", "tic-tac-toe", "tic tac toe", "main.py", "boucle", "développer"}
                pruned_user_facts = []
                for f in retrieved.injected_facts:
                    if f["category"] in ("user_profile", "long_term_facts"):
                        text_lower = f["text"].lower()
                        if any(kw in text_lower for kw in technical_keywords) or any(kw in f["id"].lower() for kw in technical_keywords):
                            pruned_user_facts.append(f)
                pruned_user_facts_count = len(pruned_user_facts)
                if pruned_user_facts:
                    user_summary = "\n--- CE QUE TU SAIS SUR LE PROJET (Technique) ---\n"
                    for f in pruned_user_facts:
                        user_summary += f"- {f['text']}\n"
                    user_summary += "--- FIN DES CONNAISSANCES ---\n"
                else:
                    user_summary = ""
            else:
                lines = user_summary.splitlines()
                technical_keywords = {"projet", "code", "python", "jeu", "tic-tac-toe", "tic tac toe", "main.py", "boucle", "développer"}
                pruned_lines = []
                for line in lines:
                    if any(kw in line.lower() for kw in technical_keywords):
                        pruned_lines.append(line)
                pruned_user_facts_count = len(pruned_lines)
                if pruned_lines:
                    user_summary = "\n--- CE QUE TU SAIS SUR LE PROJET (Technique) ---\n" + "\n".join(pruned_lines) + "\n--- FIN DES CONNAISSANCES ---\n"
                else:
                    user_summary = ""
            
            # 5. Élagage et réduction de l'historique de discussion
            recent_history = self.memory.get_context(5)
            pruned_history = []
            technical_keywords_hist = {
                "code", "python", "classe", "class", "fonction", "def", "import", "bug", "erreur", 
                "error", "corriger", "corrige", "modifier", "script", "programme", "développer", 
                "compil", "fichiers", "git", "main.py", "tic-tac-toe", "tic tac toe", "jeu", "boucle"
            }
            for idx, msg in enumerate(recent_history):
                content = msg.get("content", "")
                if idx == len(recent_history) - 1:
                    pruned_history.append(msg)
                    continue
                if "```" in content:
                    pruned_history.append(msg)
                    continue
                if msg.get("role") == "system" or content.startswith("[SYSTÈME]"):
                    pruned_history.append(msg)
                    continue
                import re
                words = set(re.sub(r"[^\w\s]", " ", content.lower()).split())
                if words.intersection(technical_keywords_hist):
                    pruned_history.append(msg)
                    continue
            context = pruned_history

        # Enregistrement et log diagnostique de la réduction (Phase 2)
        if active_mode == "CODE":
            pruned_history_count = len(context)
            pruning_report = (
                f"\n[DIAGNOSTIC ADAPTATIF - PHASE 2 - RÉDUCTION DU CONTEXTE (Mode CODE)]\n"
                f"  - Instructions système : Épurées (SYSTEM_PROMPT_CODE utilisé, sans règles d'avatar ni de numéros de ligne).\n"
                f"  - Personnalité d'Anna (assistant_profile) : RETIRÉE de l'injection sémantique.\n"
                f"  - Contexte compressé : MASQUÉ.\n"
                f"  - Fichiers projet chargés : Transmis BRUTS (sans numéros de ligne).\n"
                f"  - Mémoire (profil utilisateur) : Filtrée ({pruned_user_facts_count} faits techniques conservés).\n"
                f"  - Historique de discussion : Pruné ({pruned_history_count} conservés sur {original_history_count} messages dans la fenêtre).\n"
            )
        else:
            pruning_report = (
                f"\n[DIAGNOSTIC ADAPTATIF - PHASE 2 - CONSERVATION DU CONTEXTE (Mode CHAT)]\n"
                f"  - Instructions système : Complètes (SYSTEM_PROMPT standard avec avatar).\n"
                f"  - Personnalité d'Anna (assistant_profile) : CONSERVÉE.\n"
                f"  - Contexte compressé : CONSERVÉ ({len(compressed_context)} caractères).\n"
                f"  - Fichiers projet chargés : Transmis NUMÉROTÉS.\n"
                f"  - Mémoire (profil utilisateur) : Complète.\n"
                f"  - Historique de discussion : Complet ({len(context)} messages).\n"
            )
        print(pruning_report)
        log_diagnostic(pruning_report)
        if sys_trace_callback:
            sys_trace_callback(pruning_report)

        # Configurer le prompt système à utiliser temporairement pour le moteur LLM
        from config import SYSTEM_PROMPT_CODE
        if active_mode == "CODE":
            self.engine.system_prompt = SYSTEM_PROMPT_CODE

        # Dimensionnement et diagnostic du prompt final
        sys_prompt_base = self.engine.system_prompt.strip().format(name=assistant_name)
        sys_chars = len(sys_prompt_base)
        user_summary_chars = len(user_summary)
        assistant_summary_chars = len(assistant_summary)
        files_chars = len(files_context)
        compressed_chars = len(compressed_context)
        history_chars = sum(len(m.get("content", "")) for m in context)
        history_msg_count = len(context)
        open_files_count = len(self.files.loaded_files)
        
        total_chars = sys_chars + user_summary_chars + assistant_summary_chars + files_chars + compressed_chars + history_chars
        approx_tokens = int(total_chars / 4)
        
        if sys_trace_callback:
            sys_trace_callback("[Prompt] Composition et dimensionnement du prompt final :")
            sys_trace_callback(f"  - Instructions système de base : {sys_chars} caractères")
            sys_trace_callback(f"  - Profil utilisateur (Louis)  : {user_summary_chars} caractères")
            sys_trace_callback(f"  - Profil assistant (Anna)      : {assistant_summary_chars} caractères")
            sys_trace_callback(f"  - Fichiers projet chargés      : {files_chars} caractères ({open_files_count} fichier(s) ouvert(s))")
            sys_trace_callback(f"  - Historique de discussion     : {history_chars} caractères ({history_msg_count} messages)")
            sys_trace_callback(f"  - Tampon de contexte compressé : {compressed_chars} caractères")
            sys_trace_callback(f"  => Taille estimée globale : {total_chars} caractères (~{approx_tokens} tokens)")
            
            prep_duration = time.time() - start_context_prep
            sys_trace_callback(f"=== FIN PRÉPARATION DU CONTEXTE (Durée totale : {prep_duration:.2f}s) ===")
            sys_trace_callback(f"[Appel LLM] Lancement : génération de la réponse (Modèle : {self.engine.model})...")

        first_ollama_diag = {}
        response = self.engine.get_response(
            context,
            images=images,
            user_summary=user_summary,
            assistant_summary=assistant_summary,
            assistant_name=assistant_name,
            files_context=files_context,
            compressed_context=compressed_context,
            chunk_callback=chunk_callback,
            status_callback=status_callback,
            on_start_callback=on_start_callback,
            ollama_diagnostics=first_ollama_diag
        )
        
        if status_callback:
            status_callback("Finalisation...")
            
        # Déclencheur du tampon de contexte compressé
        older_messages = self.memory.history[:-context_size]
        older_count = len(older_messages)
        last_consolidated = self.settings.get_setting("last_consolidated_count", 0)
        
        if enable_compressed and older_count >= 5 and (older_count - last_consolidated) >= 5:
            self._trigger_context_consolidation(older_count)
        
        if not response:
            self.engine.system_prompt = original_system_prompt
            user_name = self.memory.user_profile.get("prénom", "Louis")
            response = f"Salut {user_name}, je suis là. (Ollama n'a pas renvoyé de texte)"
            return {
                "type": "text",
                "content": response,
                "system_notification": intent_result.get("message") if intent_result.get("action") == "load_context" else None
            }
            
        # Nettoyage des balises de trace <think>...</think> pour l'historique, le TTS et les diffs
        clean_response = response
        if "<think>" in response:
            import re
            clean_response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
            if "<think>" in clean_response:
                clean_response = clean_response.split("<think>", 1)[0]
                
        # Protection contre les réponses vides (coupure pendant la réflexion)
        if not clean_response.strip():
            clean_response = "[La réponse a été interrompue durant la réflexion]"

        # Collecte de diagnostics (Phase 1)
        raw_len = len(response) if response else 0
        clean_len = len(clean_response) if clean_response else 0
        
        diag_data = {
            "raw_length": raw_len,
            "clean_length": clean_len,
            "raw_markers_file": 0,
            "raw_markers_search": 0,
            "raw_markers_sep": 0,
            "raw_markers_replace": 0,
            "raw_markers_create": 0,
            "raw_markers_create_end": 0,
            "incomplete_blocks": [],
            "rejected_blocks": [],
            "first_pass_create_blocks": 0,
            "first_pass_edit_blocks": 0,
            "retry_triggered": False,
            "retry_raw_length": 0,
            "retry_clean_length": 0,
            "retry_create_blocks": 0,
            "retry_edit_blocks": 0,
            "retry_diagnostics": None,
            "first_ollama_diagnostics": first_ollama_diag,
            "retry_ollama_diagnostics": None
        }

        # Première analyse des propositions de modifications de fichiers
        first_diag = {
            "raw_markers_file": 0,
            "raw_markers_search": 0,
            "raw_markers_sep": 0,
            "raw_markers_replace": 0,
            "raw_markers_create": 0,
            "raw_markers_create_end": 0,
            "incomplete_blocks": [],
            "rejected_blocks": []
        }
        create_blocks = self.editor.parse_create_blocks(clean_response, diagnostics=first_diag)
        edit_blocks = self.editor.parse_search_replace_blocks(clean_response, working_dir=self.files.working_dir, diagnostics=first_diag)
        
        diag_data["raw_markers_file"] = first_diag["raw_markers_file"]
        diag_data["raw_markers_search"] = first_diag["raw_markers_search"]
        diag_data["raw_markers_sep"] = first_diag["raw_markers_sep"]
        diag_data["raw_markers_replace"] = first_diag["raw_markers_replace"]
        diag_data["raw_markers_create"] = first_diag["raw_markers_create"]
        diag_data["raw_markers_create_end"] = first_diag["raw_markers_create_end"]
        diag_data["incomplete_blocks"] = list(first_diag["incomplete_blocks"])
        diag_data["rejected_blocks"] = list(first_diag["rejected_blocks"])
        diag_data["first_pass_create_blocks"] = len(create_blocks)
        diag_data["first_pass_edit_blocks"] = len(edit_blocks)

        print(f"  [PATCH DETECTION] Blocs détectés dans la réponse : {len(create_blocks)} création(s), {len(edit_blocks)} modification(s)")
        for block in edit_blocks:
            status = "INVALID" if block.get("invalid") else "VALID"
            print(f"  [PATCH VALIDATION] Bloc modification pour '{block['file_path']}' - Statut : {status}")

        # Boucle de correction automatique (max 1 tentative)
        has_invalid = any(block.get("invalid") for block in edit_blocks)
        if has_invalid:
            print("  [SAFETY PATCH] Détection de blocs de modification invalides (omissions/placeholders). Lancement de la boucle de correction automatique (max 1 tentative)...")
            diag_data["retry_triggered"] = True
            
            correction_user_msg = (
                "Attention, une ou plusieurs des modifications proposées ont été rejetées car un bloc SEARCH contient des ellipses, "
                "des résumés ou des commentaires d'omission (comme '...', 'inchangé', 'autres sections').\n"
                "Le bloc SEARCH doit correspondre EXACTEMENT et en continu (caractère pour caractère) au code présent dans le fichier chargé.\n"
                "Règle de correction :\n"
                "1. Ne mets jamais d'ellipses ou de placeholders dans SEARCH.\n"
                "2. Si tu dois faire plusieurs changements séparés, écris plusieurs petits blocs SEARCH/REPLACE ciblés au lieu d'un seul bloc approximatif.\n"
                "3. Régénère uniquement le(s) patch(s) de modification corrigé(s) au format FILE/SEARCH/REPLACE exact."
            )
            
            # Construire un contexte temporaire
            temp_context = list(context)
            temp_context.append({"role": "assistant", "content": clean_response})
            temp_context.append({"role": "user", "content": correction_user_msg})
            
            if status_callback:
                status_callback("Correction du patch en cours...")
                
            retry_ollama_diag = {}
            retry_response = self.engine.get_response(
                temp_context,
                images=images,
                user_summary=user_summary,
                assistant_summary=assistant_summary,
                assistant_name=assistant_name,
                files_context=files_context,
                compressed_context=compressed_context,
                chunk_callback=None,  # Pas de streaming pour la correction automatique
                status_callback=status_callback,
                on_start_callback=on_start_callback,
                ollama_diagnostics=retry_ollama_diag
            )
            
            if retry_response:
                clean_retry = retry_response
                if "<think>" in retry_response:
                    import re
                    clean_retry = re.sub(r"<think>.*?</think>", "", retry_response, flags=re.DOTALL)
                    if "<think>" in clean_retry:
                        clean_retry = clean_retry.split("<think>", 1)[0]
                
                if not clean_retry.strip():
                    clean_retry = "[La réponse a été interrompue durant la réflexion]"
                
                clean_response = clean_retry
                
                # Ré-analyser les blocs à partir de la réponse corrigée
                retry_diag = {
                    "raw_markers_file": 0,
                    "raw_markers_search": 0,
                    "raw_markers_sep": 0,
                    "raw_markers_replace": 0,
                    "raw_markers_create": 0,
                    "raw_markers_create_end": 0,
                    "incomplete_blocks": [],
                    "rejected_blocks": []
                }
                diag_data["retry_raw_length"] = len(retry_response)
                diag_data["retry_clean_length"] = len(clean_retry)
                
                create_blocks = self.editor.parse_create_blocks(clean_response, diagnostics=retry_diag)
                edit_blocks = self.editor.parse_search_replace_blocks(clean_response, working_dir=self.files.working_dir, diagnostics=retry_diag)
                
                diag_data["retry_create_blocks"] = len(create_blocks)
                diag_data["retry_edit_blocks"] = len(edit_blocks)
                diag_data["retry_diagnostics"] = retry_diag
                diag_data["retry_ollama_diagnostics"] = retry_ollama_diag
                
                print(f"  [PATCH DETECTION] Blocs après correction automatique : {len(create_blocks)} création(s), {len(edit_blocks)} modification(s)")
                for block in edit_blocks:
                    status = "INVALID" if block.get("invalid") else "VALID"
                    print(f"  [PATCH VALIDATION] Bloc modification pour '{block['file_path']}' - Statut : {status}")

        # Construction du rapport d'instrumentation (Phase 1 & 1C)
        first_ctx = first_ollama_diag.get("model_ctx")
        first_predict = first_ollama_diag.get("model_predict")
        first_native_ctx = first_ollama_diag.get("model_native_ctx")
        first_input_tokens = first_ollama_diag.get("prompt_eval_count")
        first_generated_tokens = first_ollama_diag.get("eval_count")
        
        total_tokens = None
        if first_input_tokens is not None and first_generated_tokens is not None:
            total_tokens = first_input_tokens + first_generated_tokens

        ratio_str = "Inconnu"
        active_limit = first_ctx if first_ctx else 4096
        if total_tokens and active_limit:
            ratio_str = f"{(total_tokens / active_limit) * 100:.1f}% ({total_tokens} / {active_limit} tokens)"
        elif first_input_tokens:
            ratio_str = f"Inconnu (contexte non défini par défaut dans le modèle, prompt: {first_input_tokens} tokens)"

        saturation_alert = ""
        done_reason = first_ollama_diag.get('done_reason')
        if done_reason == "length" or (total_tokens and total_tokens >= active_limit):
            saturation_alert = f"\n      * [ATTENTION: SATURATION DU CONTEXTE] La limite active de contexte ({active_limit} tokens) a été atteinte (Total: {total_tokens} tokens)."

        report_lines = [
            "\n[INSTRUMENTATION MINIMALE - PHASE 1 & 1C]",
            f"  - Longueur de réponse brute Ollama : {diag_data['raw_length']} caractères",
            f"  - Longueur après nettoyage <think> : {diag_data['clean_length']} caractères",
            f"  - Métadonnées de génération Ollama (1ère passe) :",
            f"      * done : {first_ollama_diag.get('done')}",
            f"      * done_reason : {done_reason}{saturation_alert}",
            f"      * tokens d'entrée (prompt_eval_count) : {first_input_tokens}",
            f"      * tokens générés (eval_count) : {first_generated_tokens}",
            f"      * total des tokens (prompt + générés) : {total_tokens if total_tokens is not None else 'N/A'}",
            f"      * exception éventuelle : {first_ollama_diag.get('exception')}",
            f"      * num_ctx effectif du modèle : {first_ctx if first_ctx else 'Non spécifié (4096 ou 2048 par défaut)'}",
            f"      * num_predict effectif du modèle : {first_predict if first_predict is not None else 'Non spécifié (génération illimitée / EOS)'}",
            f"      * capacité de contexte native du modèle : {first_native_ctx if first_native_ctx else 'Inconnue'}",
            f"      * ratio d'utilisation du contexte : {ratio_str}",
            f"      * durée totale de génération (s) : {first_ollama_diag.get('total_duration') / 1e9 if first_ollama_diag.get('total_duration') else 'N/A'}",
            f"  - Compte de marqueurs détectés :",
            f"      * FILE: {diag_data['raw_markers_file']}",
            f"      * <<<<<<< SEARCH: {diag_data['raw_markers_search']}",
            f"      * =======: {diag_data['raw_markers_sep']}",
            f"      * >>>>>>> REPLACE: {diag_data['raw_markers_replace']}",
            f"      * <<<<<<< CREATE: {diag_data['raw_markers_create']}",
            f"      * >>>>>>> CREATE: {diag_data['raw_markers_create_end']}",
            f"  - Blocs d'édition complets (1ère passe) : {diag_data['first_pass_edit_blocks']}",
            f"  - Blocs de création complets (1ère passe) : {diag_data['first_pass_create_blocks']}",
            f"  - Blocs incomplets détectés : {len(diag_data['incomplete_blocks'])}"
        ]
        
        for idx, inc in enumerate(diag_data["incomplete_blocks"], 1):
            report_lines.append(
                f"      * Bloc #{idx} : État final '{inc['state']}' pour le fichier '{inc['file_path']}' à la ligne {inc['line_num']}"
            )
            if "search_preview" in inc and inc["search_preview"]:
                preview = repr(inc["search_preview"][:50])
                report_lines.append(f"        Aperçu SEARCH: {preview}")
            if "replace_preview" in inc and inc["replace_preview"]:
                preview = repr(inc["replace_preview"][:50])
                report_lines.append(f"        Aperçu REPLACE: {preview}")
            if "preview" in inc and inc["preview"]:
                preview = repr(inc["preview"][:50])
                report_lines.append(f"        Aperçu CREATE: {preview}")
 
        report_lines.append(f"  - Blocs rejetés pour placeholders/erreurs : {len(diag_data['rejected_blocks'])}")
        for idx, rej in enumerate(diag_data["rejected_blocks"], 1):
            report_lines.append(
                f"      * Bloc #{idx} : Rejeté pour '{rej['reason']}' dans '{rej['file_path']}' à la ligne {rej['line_num']}"
            )
 
        report_lines.append(f"  - Boucle d'auto-correction déclenchée : {'OUI' if diag_data['retry_triggered'] else 'NON'}")
        if diag_data["retry_triggered"]:
            retry_diag_info = diag_data["retry_ollama_diagnostics"]
            retry_ratio = "Inconnu"
            retry_total_tokens = None
            if retry_diag_info:
                ret_ctx = retry_diag_info.get("model_ctx")
                ret_in_tokens = retry_diag_info.get("prompt_eval_count")
                ret_gen_tokens = retry_diag_info.get("eval_count")
                if ret_in_tokens is not None and ret_gen_tokens is not None:
                    retry_total_tokens = ret_in_tokens + ret_gen_tokens
                ret_active_limit = ret_ctx if ret_ctx else 4096
                if retry_total_tokens and ret_active_limit:
                    retry_ratio = f"{(retry_total_tokens / ret_active_limit) * 100:.1f}% ({retry_total_tokens} / {ret_active_limit} tokens)"
            
            report_lines.extend([
                f"      * Longueur de réponse brute (retry) : {diag_data['retry_raw_length']} caractères",
                f"      * Longueur après nettoyage (retry) : {diag_data['retry_clean_length']} caractères",
                f"      * Métadonnées de génération (retry) :",
                f"          + done : {retry_diag_info.get('done') if retry_diag_info else 'N/A'}",
                f"          + done_reason : {retry_diag_info.get('done_reason') if retry_diag_info else 'N/A'}",
                f"          + tokens d'entrée (prompt_eval_count) : {retry_diag_info.get('prompt_eval_count') if retry_diag_info else 'N/A'}",
                f"          + tokens générés (eval_count) : {retry_diag_info.get('eval_count') if retry_diag_info else 'N/A'}",
                f"          + total des tokens (retry) : {retry_total_tokens if retry_total_tokens is not None else 'N/A'}",
                f"          + ratio d'utilisation du contexte : {retry_ratio}",
                f"          + exception éventuelle : {retry_diag_info.get('exception') if retry_diag_info else 'N/A'}",
                f"      * Blocs d'édition complets (retry) : {diag_data['retry_edit_blocks']}",
                f"      * Blocs de création complets (retry) : {diag_data['retry_create_blocks']}",
                "      * Remplacement de la réponse originale par le correctif : OUI"
            ])
            if diag_data["retry_diagnostics"]:
                rd = diag_data["retry_diagnostics"]
                report_lines.extend([
                    f"      * Incomplets (retry) : {len(rd['incomplete_blocks'])}",
                    f"      * Rejetés (retry) : {len(rd['rejected_blocks'])}"
                ])
        
        report_lines.append("[FIN INSTRUMENTATION]\n")
        report_str = "\n".join(report_lines)
        
        # Envoi aux logs et traces
        from config import log_diagnostic
        log_diagnostic(report_str)
        if sys_trace_callback:
            sys_trace_callback(report_str)

        # Détection des propositions de commandes système
        command_blocks = self.command_runner.parse_command_blocks(clean_response)
        for block in command_blocks:
            is_valid, err_msg = self.command_runner.validate_command(block["command"], self.files.working_dir)
            block["invalid"] = not is_valid
            block["error_message"] = err_msg
            
        print(f"  [COMMAND DETECTION] Blocs commande détectés : {len(command_blocks)}")
        for block in command_blocks:
            status = "INVALID" if block.get("invalid") else "VALID"
            print(f"  [COMMAND VALIDATION] Commande '{block['command']}' - Statut : {status}")

        # Enregistrement de la réponse propre (et corrigée le cas échéant) dans l'historique
        self.memory.add_message("assistant", clean_response)
        
        # Détection d'émotion associée sur la réponse propre
        emotion = "neutral"
        try:
            import emotion_manager
            emotion = emotion_manager.detect_emotion(clean_response)
        except Exception as e:
            print(f"[CONTROLLER WARNING] Échec de la détection d'émotion : {e}")
            
        self.engine.system_prompt = original_system_prompt
        return {
            "type": "ai_response",
            "content": clean_response,
            "emotion": emotion,
            "create_blocks": create_blocks,
            "edit_blocks": edit_blocks,
            "command_blocks": command_blocks,
            "system_notification": intent_result.get("message") if intent_result.get("action") == "load_context" else None
        }

    def inject_execution_result_to_history(self, command, return_code, stdout_excerpt, stderr_excerpt, is_cancelled):
        """
        Injecte le résultat formaté de l'exécution d'une commande système dans l'historique de conversation (mémoire).
        """
        if is_cancelled:
            msg = (
                f"[SYSTÈME] Commande exécutée : {command}\n"
                f"Statut : arrêtée par l'utilisateur\n"
            )
            if stdout_excerpt:
                msg += f"Sortie stdout :\n{stdout_excerpt}\n"
            if stderr_excerpt:
                msg += f"Sortie stderr :\n{stderr_excerpt}\n"
        elif return_code == 0:
            msg = (
                f"[SYSTÈME] Commande exécutée : {command}\n"
                f"Code de retour : {return_code}\n"
                f"Statut : succès\n"
            )
            if stdout_excerpt:
                msg += f"Sortie stdout :\n{stdout_excerpt}\n"
        else:
            msg = (
                f"[SYSTÈME] Commande exécutée : {command}\n"
                f"Code de retour : {return_code}\n"
                f"Statut : échec\n"
            )
            if stderr_excerpt:
                msg += f"Erreur stderr :\n{stderr_excerpt}\n"
            elif stdout_excerpt:
                # Au cas où stdout et stderr ont été combinés par le runner
                msg += f"Sortie console :\n{stdout_excerpt}\n"

        self.memory.add_message("system", msg)
        print(f"  [SYSTEM MEMORY INJECTION] Résultat d'exécution enregistré pour '{command}' (Code: {return_code})")
