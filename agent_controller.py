import threading
import os
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
        
        # 3. Initialisation du gestionnaire de génération d'images (MVC)
        self.image_manager = ImageGenerationManager(self.engine)

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

    def _trigger_background_memory_task(self, user_msg):
        """Lance une tâche asynchrone en tâche de fond pour l'extraction de faits en mémoire."""
        def task():
            try:
                fact = self.engine.extract_fact(user_msg)
                if fact:
                    self.memory.process_extracted_fact(fact)
            except Exception as e:
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

    def process_user_message_sync(self, user_input, images=None, chunk_callback=None, status_callback=None, on_start_callback=None):
        """
        Traite un message utilisateur en langage naturel de manière synchrone.
        Retourne un dictionnaire unifié contenant les résultats IA et système.
        """
        # 0. Interception sémantique si le mode génération d'images est actif (LLM-First)
        if hasattr(self, 'image_manager') and self.image_manager.is_active():
            return self.image_manager.process_user_message(user_input, self.engine)

        if status_callback:
            status_callback("Préparation du contexte...")

        # 1. Lancement de l'extraction de faits en tâche de fond
        self._trigger_background_memory_task(user_input)
        
        # 2. Détection d'intention sémantique via IntentRouter (LLM-First)
        intent_result = self.router.process_intent(user_input, self.files)
        if intent_result.get("handled"):
            # Enregistrement système dans la mémoire pour préserver l'historique court terme
            self.memory.add_message("user", user_input)
            self.memory.add_message("assistant", intent_result.get("system_context"))
            return {
                "type": "intent_handled",
                "action": intent_result.get("action"),
                "message": intent_result.get("message"),
                "system_context": intent_result.get("system_context")
            }

        # Couche de sécurité additive (fallback) pour la résolution de fichiers implicites
        if intent_result.get("action") == "none" and self.files.working_dir:
            available_files = self.files.get_available_files()
            if available_files:
                if status_callback:
                    status_callback("Analyse de sécurité du contexte...")
                resolution = self.router.resolve_context_required(user_input, available_files)
                if resolution.get("action") == "load_context":
                    confidence = resolution.get("confidence", 0.0)
                    targets = resolution.get("targets", [])
                    reason = resolution.get("reason", "")
                    if confidence >= 0.70 and targets:
                        print(f"  [SAFETY PIPELINE] Résolution de contexte réussie (confiance: {confidence}, raison: {reason}). Chargement automatique de : {targets}")
                        loaded_list = []
                        for target in targets:
                            success, msg = self.files.load_file(target, user_input=user_input)
                            if success:
                                loaded_list.append(target)
                        
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
                return {
                    "type": "error",
                    "message": msg
                }
            
        # Récupération sélective de la mémoire (mode observation)
        memory_sources = {
            "user_profile": self.memory.user_profile,
            "assistant_profile": self.memory.assistant_profile,
            "facts": self.memory.facts
        }
        retrieved = self.retriever.retrieve(user_input, memory_sources)
        
        if SELECTIVE_MEMORY_OBSERVATION:
            from config import CORE_MEMORY_IDS
            dynamic_selected_count = len([f for f in retrieved.injected_facts if f["id"] not in CORE_MEMORY_IDS])
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
            on_start_callback=on_start_callback
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
            parts = response.split("<think>", 1)
            before_think = parts[0]
            rest = parts[1]
            if "</think>" in rest:
                clean_response = before_think + rest.split("</think>", 1)[1]
            else:
                clean_response = before_think
                
        # Protection contre les réponses vides (coupure pendant la réflexion)
        if not clean_response.strip():
            clean_response = "[La réponse a été interrompue durant la réflexion]"

        # Première analyse des propositions de modifications de fichiers
        create_blocks = self.editor.parse_create_blocks(clean_response)
        edit_blocks = self.editor.parse_search_replace_blocks(clean_response)
        print(f"  [PATCH DETECTION] Blocs détectés dans la réponse : {len(create_blocks)} création(s), {len(edit_blocks)} modification(s)")
        for block in edit_blocks:
            status = "INVALID" if block.get("invalid") else "VALID"
            print(f"  [PATCH VALIDATION] Bloc modification pour '{block['file_path']}' - Statut : {status}")

        # Boucle de correction automatique (max 1 tentative)
        has_invalid = any(block.get("invalid") for block in edit_blocks)
        if has_invalid:
            print("  [SAFETY PATCH] Détection de blocs de modification invalides (omissions/placeholders). Lancement de la boucle de correction automatique (max 1 tentative)...")
            
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
                status_callback("Correction automatique du patch...")
                
            retry_response = self.engine.get_response(
                temp_context,
                images=images,
                user_summary=user_summary,
                assistant_summary=assistant_summary,
                assistant_name=assistant_name,
                files_context=files_context,
                compressed_context=compressed_context,
                chunk_callback=chunk_callback,
                status_callback=status_callback,
                on_start_callback=on_start_callback
            )
            
            if retry_response:
                clean_retry = retry_response
                if "<think>" in retry_response:
                    parts = retry_response.split("<think>", 1)
                    before_think = parts[0]
                    rest = parts[1]
                    if "</think>" in rest:
                        clean_retry = before_think + rest.split("</think>", 1)[1]
                    else:
                        clean_retry = before_think
                
                if not clean_retry.strip():
                    clean_retry = "[La réponse a été interrompue durant la réflexion]"
                
                clean_response = clean_retry
                # Ré-analyser les blocs à partir de la réponse corrigée
                create_blocks = self.editor.parse_create_blocks(clean_response)
                edit_blocks = self.editor.parse_search_replace_blocks(clean_response)
                print(f"  [PATCH DETECTION] Blocs après correction automatique : {len(create_blocks)} création(s), {len(edit_blocks)} modification(s)")
                for block in edit_blocks:
                    status = "INVALID" if block.get("invalid") else "VALID"
                    print(f"  [PATCH VALIDATION] Bloc modification pour '{block['file_path']}' - Statut : {status}")

        # Enregistrement de la réponse propre (et corrigée le cas échéant) dans l'historique
        self.memory.add_message("assistant", clean_response)
        
        # Détection d'émotion associée sur la réponse propre
        emotion = "neutral"
        try:
            import emotion_manager
            emotion = emotion_manager.detect_emotion(clean_response)
        except Exception as e:
            print(f"[CONTROLLER WARNING] Échec de la détection d'émotion : {e}")
            
        return {
            "type": "ai_response",
            "content": clean_response,
            "emotion": emotion,
            "create_blocks": create_blocks,
            "edit_blocks": edit_blocks,
            "system_notification": intent_result.get("message") if intent_result.get("action") == "load_context" else None
        }
