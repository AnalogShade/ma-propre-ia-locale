import sys
import os
import subprocess
import ollama
from config import (
    MODEL_NAME, SYSTEM_PROMPT, DEFAULT_NAME, log_diagnostic,
    VISION_IMAGE_LARGE_THRESHOLD_PX, VISION_MODEL_HEAVY_THRESHOLD_RATIO,
    VISION_HIGH_RISK_RATIO_THRESHOLD, VISION_LOW_VRAM_THRESHOLD_GB
)

def _safe_print(text):
    try:
        print(text)
    except Exception:
        try:
            encoding = sys.stdout.encoding or 'utf-8'
            print(text.encode(encoding, errors='replace').decode(encoding))
        except Exception:
            pass

class AIEngine:
    def __init__(self):
        self.model = MODEL_NAME
        self.system_prompt = SYSTEM_PROMPT

    def _get_client(self):
        """Retourne une instance du client Ollama configurée avec le timeout (configurable)."""
        from config import OLLAMA_REQUEST_TIMEOUT_SECONDS
        active_timeout = OLLAMA_REQUEST_TIMEOUT_SECONDS
        try:
            from settings_manager import SettingsManager
            settings = SettingsManager()
            active_timeout = settings.get_setting("ollama_request_timeout", OLLAMA_REQUEST_TIMEOUT_SECONDS)
        except Exception:
            pass
        return ollama.Client(timeout=active_timeout)

    def does_model_support_vision(self, model_name=None):
        """
        Vérifie si le modèle supporte les capacités de vision.
        Interroge Ollama localement ou utilise un repli sémantique si hors ligne.
        """
        if not model_name:
            model_name = self.model
        try:
            info = ollama.show(model=model_name)
            # 1. Vérification dans 'capabilities'
            capabilities = info.get('capabilities', [])
            if 'vision' in capabilities:
                # Vérification pour gemma4 : gemma4:latest n'a pas de projecteur CLIP (1 seul FROM),
                # alors que gemma4:12b en a un (2 FROM dans son modelfile).
                if 'gemma4' in model_name.lower():
                    modelfile = info.get('modelfile', '')
                    from_lines = [line for line in modelfile.splitlines() if line.strip().startswith('FROM') and not line.strip().startswith('#')]
                    if len(from_lines) < 2:
                        return False
                return True
            # 2. Vérification dans 'details' / 'families'
            details = info.get('details', {})
            families = details.get('families', [])
            if families and any('vision' in f.lower() for f in families):
                return True
            # Si Ollama répond et que le modèle n'a pas la vision, on retourne False directement
            return False
        except Exception:
            pass
            
        # Fallback sémantique UNIQUEMENT si l'appel Ollama échoue
        model_lower = model_name.lower()
        known_vision_keywords = ['gemma4:12b', 'llava', 'vision', 'paligemma', 'minicpm-v', 'bakllava', 'llama3.2-vision']
        return any(k in model_lower for k in known_vision_keywords)

    def get_gpu_vram(self):
        """
        Récupère la VRAM totale du GPU Nvidia en Go.
        Silencieux en cas d'échec ou d'absence de nvidia-smi (logué via log_diagnostic).
        """
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if res.returncode == 0:
                vram_mb = int(res.stdout.strip())
                return vram_mb / 1024.0
            else:
                err_msg = res.stderr.strip()
                log_diagnostic(f"[DIAGNOSTIC GPU WARNING] nvidia-smi a retourné le code {res.returncode} : {err_msg}")
        except Exception as e:
            log_diagnostic(f"[DIAGNOSTIC GPU DEBUG] Échec de la détection nvidia-smi : {e}")
        return None

    def get_model_size(self, model_name=None):
        """
        Retourne la taille estimée (installée) du modèle en Go.
        Retourne None si la taille ne peut pas être déterminée.
        """
        if not model_name:
            model_name = self.model
        try:
            models_info = ollama.list()
            models_list = []
            if hasattr(models_info, 'models'):
                models_list = models_info.models
            elif isinstance(models_info, dict):
                models_list = models_info.get('models', [])
            else:
                models_list = models_info
                
            for m in models_list:
                m_name = m.model if hasattr(m, 'model') else (m.get('model', m.get('name', '')) if isinstance(m, dict) else '')
                if m_name == model_name or m_name.split(':')[0] == model_name.split(':')[0]:
                    size_bytes = m.size if hasattr(m, 'size') else (m.get('size', 0) if isinstance(m, dict) else 0)
                    if size_bytes > 0:
                        return size_bytes / (1024**3)
        except Exception as e:
            log_diagnostic(f"[DIAGNOSTIC ENGINE WARNING] Impossible d'obtenir la taille du modèle {model_name} : {e}")
        return None

    def estimate_image_vision_cost_gb(self, width, height):
        """
        Calcule une pénalité indicative (coût VRAM en Go) pour une image donnée
        selon son nombre de pixels.
        """
        if not width or not height or width <= 0 or height <= 0:
            return 0.35 # Valeur moyenne par défaut en cas de dimensions invalides
            
        pixels = width * height
        if pixels <= 128 * 128:
            return 0.05
        elif pixels <= 384 * 384:
            return 0.15
        elif pixels <= 768 * 768:
            return 0.35
        else:
            return 0.75

    def evaluate_request_risk(self, model_name, image_infos=None, has_image=None):
        """
        Évalue le risque de lenteur ou d'échec pour la requête actuelle.
        Retourne un dictionnaire contenant le niveau de risque et les détails.
        """
        # Assurer la compatibilité ascendante avec has_image
        if has_image is not None and image_infos is None:
            if has_image:
                # 768x768 par défaut si on sait seulement qu'il y a une image
                image_infos = [{"width": 768, "height": 768, "file_size_kb": 100.0}]
            else:
                image_infos = []
                
        if isinstance(image_infos, bool):
            if image_infos:
                image_infos = [{"width": 768, "height": 768, "file_size_kb": 100.0}]
            else:
                image_infos = []

        result = {
            "level": "low_risk",
            "reason": "La configuration matérielle et le modèle semblent adaptés pour un traitement rapide.",
            "model_size_gb": None,
            "gpu_vram_gb": None,
            "image_cost_gb": 0.0,
            "image_extra_estimate_gb": 0.0, # Pour compatibilité descendante
            "ratio": 0.0,
            "confidence": "high"
        }
        
        image_count = len(image_infos) if image_infos else 0
        if image_count == 0:
            return result
            
        gpu_vram = self.get_gpu_vram()
        model_size = self.get_model_size(model_name)
        
        result["gpu_vram_gb"] = gpu_vram
        result["model_size_gb"] = model_size
        
        if gpu_vram is None or model_size is None:
            result["level"] = "moderate_risk"
            result["confidence"] = "low"
            result["reason"] = "Impossible de détecter précisément la VRAM ou la taille du modèle installé. Risque modéré par défaut."
            # Logs diagnostics même en cas d'incertitude
            log_diagnostic(
                f"Vision risk:\n"
                f"model_size_gb={model_size}\n"
                f"gpu_vram_gb={gpu_vram}\n"
                f"image_count={image_count}\n"
                f"level=moderate_risk\n"
                f"reason={result['reason']}"
            )
            return result
            
        # 1. Calcul du coût total estimé pour l'ensemble des images (somme simple)
        image_cost_gb = sum(self.estimate_image_vision_cost_gb(img.get("width"), img.get("height")) for img in image_infos)
        result["image_cost_gb"] = image_cost_gb
        result["image_extra_estimate_gb"] = image_cost_gb
        
        # 2. Calcul du ratio
        ratio = (model_size + image_cost_gb) / gpu_vram
        
        # Pénalité si VRAM très faible (augmente virtuellement le ratio)
        is_low_vram = gpu_vram <= VISION_LOW_VRAM_THRESHOLD_GB
        if is_low_vram:
            ratio += 0.15
            
        result["ratio"] = ratio
        
        # 3. Indicateurs de sévérité
        is_model_heavy = model_size >= gpu_vram * VISION_MODEL_HEAVY_THRESHOLD_RATIO
        
        has_large_image = False
        medium_large_images_count = 0
        for img in image_infos:
            w = img.get("width", 0) or 0
            h = img.get("height", 0) or 0
            if max(w, h) >= VISION_IMAGE_LARGE_THRESHOLD_PX:
                has_large_image = True
            if w * h > 128 * 128:
                medium_large_images_count += 1
                
        # 4. Évaluation du niveau de risque de base
        if ratio < 0.90:
            level = "low_risk"
        elif ratio < VISION_HIGH_RISK_RATIO_THRESHOLD:
            level = "moderate_risk"
        else:
            level = "high_risk"
            
        # 5. Escalades de sévérité vers high_risk
        escalated = False
        escalation_reason = ""
        
        if ratio >= VISION_HIGH_RISK_RATIO_THRESHOLD:
            escalated = True
            escalation_reason = f"Le ratio taille estimée/VRAM est critique ({ratio:.2f})."
        elif medium_large_images_count >= 2 and is_model_heavy:
            escalated = True
            escalation_reason = f"Plusieurs images moyennes/grandes ({medium_large_images_count}) envoyées avec un modèle déjà lourd."
        elif has_large_image and is_model_heavy:
            escalated = True
            escalation_reason = "Grande image (proche de 768x768) envoyée avec un modèle déjà lourd."
        elif is_low_vram and (is_model_heavy or medium_large_images_count >= 1):
            escalated = True
            escalation_reason = f"VRAM faible ({gpu_vram:.1f} Go) avec modèle lourd ou image moyenne/grande."
            
        if escalated:
            level = "high_risk"
            reason = escalation_reason
        else:
            if level == "moderate_risk":
                if is_model_heavy:
                    reason = "Modèle légèrement supérieur à la VRAM détectée, mais image très petite."
                else:
                    reason = f"La taille combinée du modèle ({model_size:.1f} Go) et de l'image ({image_cost_gb:.2f} Go) approche de la limite de la VRAM ({gpu_vram:.1f} Go)."
            else:
                reason = "La configuration matérielle et le modèle semblent adaptés pour un traitement rapide."
                
        result["level"] = level
        result["reason"] = reason
        
        # 6. Écriture des diagnostics dans les logs
        images_str = ", ".join([f"{img.get('width')}x{img.get('height')}" for img in image_infos])
        temp_sizes_str = ", ".join([f"{img.get('file_size_kb'):.1f} KB" if img.get('file_size_kb') is not None else "Inconnue" for img in image_infos])
        
        log_diagnostic(
            f"Vision risk:\n"
            f"model_size_gb={model_size:.2f}\n"
            f"gpu_vram_gb={gpu_vram:.2f}\n"
            f"image={images_str}\n"
            f"temp_file_size={temp_sizes_str}\n"
            f"image_cost_gb={image_cost_gb:.2f}\n"
            f"ratio={ratio:.2f}\n"
            f"level={level}\n"
            f"reason={reason}"
        )
        
        return result

    def get_installed_models(self):
        """
        Interroge Ollama localement pour obtenir la liste des modèles installés.
        Retourne une liste de chaînes (les noms des modèles).
        Retourne une liste vide si Ollama n'est pas démarré ou en cas d'erreur.
        """
        try:
            models_info = self._get_client().list()
            
            models_list = []
            if hasattr(models_info, 'models'):
                models_list = models_info.models
            elif isinstance(models_info, dict):
                models_list = models_info.get('models', [])
            else:
                models_list = models_info
                
            names = []
            for m in models_list:
                if hasattr(m, 'model'):
                    names.append(m.model)
                elif isinstance(m, dict) and 'model' in m:
                    names.append(m['model'])
                elif isinstance(m, dict) and 'name' in m:
                    names.append(m['name'])
                elif hasattr(m, 'name'):
                    names.append(m.name)
            return names
        except Exception as e:
            # On loggue l'erreur de manière non-bloquante sans faire planter l'application
            print(f"\n[DEBUG: Impossible de joindre Ollama pour lister les modèles -> {e}]")
            return []

    def get_response(self, context_messages, images=None, user_summary="", assistant_summary="", assistant_name=DEFAULT_NAME, files_context="", compressed_context="", model_name=None, chunk_callback=None, status_callback=None, on_start_callback=None, ollama_diagnostics=None):
        try:
            # 1. Construction du prompt système
            system_content = self.system_prompt.strip().format(name=assistant_name)
            
            if assistant_summary:
                system_content += f"\n{assistant_summary}"

            if user_summary:
                system_content += f"\nContexte utilisateur :\n{user_summary}"
            
            if files_context:
                system_content += f"\n{files_context}"

            if compressed_context:
                system_content += f"\n\n--- TAMPON DE CONTEXTE COMPRESSE (DISCUSSIONS PRECEDENTES) ---\n{compressed_context}\n--------------------------------------------------------------"

            _safe_print(f"\n[DIAGNOSTIC] EXACT SYSTEM PROMPT + INJECTED MEMORY:\n{system_content}\n")

            # 2. Nettoyage des messages (role, content et optionnellement images)
            def clean_history_content(text):
                if not text:
                    return ""
                import re
                # Enlever les blocs SEARCH/REPLACE
                text = re.sub(r"<<<<<<< SEARCH.*?>>>>>>> REPLACE", "[Bloc de modification de code]", text, flags=re.DOTALL)
                # Enlever les blocs CREATE
                text = re.sub(r"<<<<<<< CREATE.*?>>>>>>> CREATE", "[Bloc de création de fichier]", text, flags=re.DOTALL)
                # Enlever les blocs EXECUTE_COMMAND
                text = re.sub(r"<<<<<<< EXECUTE_COMMAND.*?>>>>>>> EXECUTE_COMMAND", "[Bloc d'exécution de commande]", text, flags=re.DOTALL)
                # Enlever les mentions FILE:
                text = re.sub(r"FILE:\s*\S+", "", text)
                return text

            clean_context = []
            for m in context_messages:
                cleaned_content = clean_history_content(m["content"])
                clean_msg = {"role": m["role"], "content": cleaned_content}
                if "images" in m:
                    clean_msg["images"] = m["images"]
                clean_context.append(clean_msg)
                
            # Attacher les pièces jointes temporaires de la requête courante au tout dernier message utilisateur
            if images and clean_context:
                clean_context[-1]["images"] = images
                
            messages = [{'role': 'system', 'content': system_content}] + clean_context
            
            target_model = model_name if model_name else self.model
            _safe_print(f"\n[DIAGNOSTIC] FULL PAYLOAD TO OLLAMA (Model: {target_model}):\n{messages}\n")

            # Charger la configuration globale du contexte
            from config import DEFAULT_MODEL_CONTEXT_SIZE
            active_ctx = DEFAULT_MODEL_CONTEXT_SIZE
            try:
                from settings_manager import SettingsManager
                settings = SettingsManager()
                active_ctx = settings.get_setting("model_context_size", DEFAULT_MODEL_CONTEXT_SIZE)
            except Exception:
                pass
            options = {"num_ctx": active_ctx}

            # Phase 1C : Récupération de la configuration effective du modèle (ctx natif et num_predict)
            model_ctx = None
            model_predict = None
            model_native_ctx = None
            model_parameters = None
            model_modelfile = ""
            try:
                show_info = ollama.show(model=target_model)
                model_modelfile = getattr(show_info, "modelfile", None) or (show_info.get("modelfile", "") if hasattr(show_info, "get") else "")
                
                # Chercher num_ctx et num_predict dans le modelfile
                import re
                ctx_match = re.search(r"PARAMETER\s+num_ctx\s+(\d+)", model_modelfile, re.IGNORECASE)
                if ctx_match:
                    model_ctx = int(ctx_match.group(1))
                
                predict_match = re.search(r"PARAMETER\s+num_predict\s+(-?\d+)", model_modelfile, re.IGNORECASE)
                if predict_match:
                    model_predict = int(predict_match.group(1))
                
                # Chercher dans les paramètres
                params_str = getattr(show_info, "parameters", None) or (show_info.get("parameters", "") if hasattr(show_info, "get") else "")
                if params_str:
                    model_parameters = params_str
                    if not model_ctx:
                        ctx_match = re.search(r"num_ctx\s+(\d+)", params_str, re.IGNORECASE)
                        if ctx_match:
                            model_ctx = int(ctx_match.group(1))
                    if not model_predict:
                        predict_match = re.search(r"num_predict\s+(-?\d+)", params_str, re.IGNORECASE)
                        if predict_match:
                            model_predict = int(predict_match.group(1))

                # Extraire le contexte natif du modèle
                model_info_dict = {}
                if hasattr(show_info, "modelinfo") and show_info.modelinfo:
                    model_info_dict = show_info.modelinfo
                elif isinstance(show_info, dict) and "modelinfo" in show_info:
                    model_info_dict = show_info["modelinfo"]
                elif isinstance(show_info, dict) and "model_info" in show_info:
                    model_info_dict = show_info["model_info"]

                for key, val in model_info_dict.items():
                    if key.endswith(".context_length"):
                        model_native_ctx = val
                        break
            except Exception as show_err:
                log_diagnostic(f"[DIAGNOSTIC ENGINE WARNING] Échec de l'interrogation de ollama.show : {show_err}")

            if isinstance(ollama_diagnostics, dict):
                ollama_diagnostics["done"] = False
                ollama_diagnostics["done_reason"] = "incomplete"
                ollama_diagnostics["prompt_eval_count"] = None
                ollama_diagnostics["eval_count"] = None
                ollama_diagnostics["model_ctx"] = model_ctx
                ollama_diagnostics["model_predict"] = model_predict
                ollama_diagnostics["model_native_ctx"] = model_native_ctx
                ollama_diagnostics["model_modelfile"] = model_modelfile
                ollama_diagnostics["model_parameters"] = model_parameters
                ollama_diagnostics["exception"] = None
                ollama_diagnostics["total_duration"] = None

            # 3. Appel Ollama (avec support streaming et fallback)
            if status_callback:
                status_callback("Envoi au modèle...")
                
            response_text = ""
            client = self._get_client()
            if chunk_callback:
                try:
                    if status_callback:
                        status_callback("Réflexion du modèle...")
                    stream = client.chat(model=target_model, messages=messages, stream=True, options=options)
                    
                    if on_start_callback:
                        try:
                            on_start_callback()
                        except Exception as cb_err:
                            print(f"[ENGINE WARNING] Error in on_start_callback: {cb_err}")
                    
                    first_chunk = True
                    sent_think_start = False
                    sent_think_end = False
                    
                    for chunk in stream:
                        if first_chunk:
                            if status_callback:
                                status_callback("Réception de la réponse...")
                            first_chunk = False
                        
                        message = chunk.get('message', {})
                        thinking_text = message.get('thinking', '')
                        content_text = message.get('content', '')
                        
                        # Si le modèle renvoie du raisonnement natif (ex: Gemma 4)
                        if thinking_text:
                            if not sent_think_start:
                                chunk_callback("<think>")
                                response_text += "<think>"
                                sent_think_start = True
                            chunk_callback(thinking_text)
                            response_text += thinking_text
                            
                        # Si le modèle renvoie du contenu final
                        if content_text:
                            if sent_think_start and not sent_think_end:
                                chunk_callback("</think>")
                                response_text += "</think>"
                                sent_think_end = True
                            chunk_callback(content_text)
                            response_text += content_text

                        # Phase 1B: Capture des métadonnées du dernier chunk
                        if chunk.get("done"):
                            if isinstance(ollama_diagnostics, dict):
                                ollama_diagnostics["done"] = True
                                ollama_diagnostics["done_reason"] = chunk.get("done_reason")
                                ollama_diagnostics["prompt_eval_count"] = chunk.get("prompt_eval_count")
                                ollama_diagnostics["eval_count"] = chunk.get("eval_count")
                                ollama_diagnostics["total_duration"] = chunk.get("total_duration")
                                ollama_diagnostics["load_duration"] = chunk.get("load_duration")
                                ollama_diagnostics["prompt_eval_duration"] = chunk.get("prompt_eval_duration")
                                ollama_diagnostics["eval_duration"] = chunk.get("eval_duration")
                            
                    # Clôture de sécurité
                    if sent_think_start and not sent_think_end:
                        chunk_callback("</think>")
                        response_text += "</think>"
                        
                except Exception as stream_err:
                    _safe_print(f"\n[DEBUG: Échec du streaming, repli en mode synchrone -> {stream_err}]")
                    if isinstance(ollama_diagnostics, dict):
                        ollama_diagnostics["exception"] = f"Streaming error: {type(stream_err).__name__}: {stream_err}"
                    # Si c'est un timeout, on le propage immédiatement
                    import httpx
                    if isinstance(stream_err, httpx.TimeoutException):
                        raise stream_err
                    if "timeout" in str(stream_err).lower():
                        raise stream_err
                        
                    if status_callback:
                        status_callback("Réflexion du modèle (Repli synchrone)...")
                    response = client.chat(model=target_model, messages=messages, options=options)
                    
                    if isinstance(ollama_diagnostics, dict):
                        ollama_diagnostics["done"] = response.get("done", True)
                        ollama_diagnostics["done_reason"] = response.get("done_reason")
                        ollama_diagnostics["prompt_eval_count"] = response.get("prompt_eval_count")
                        ollama_diagnostics["eval_count"] = response.get("eval_count")
                        ollama_diagnostics["total_duration"] = response.get("total_duration")
                        ollama_diagnostics["load_duration"] = response.get("load_duration")
                        ollama_diagnostics["prompt_eval_duration"] = response.get("prompt_eval_duration")
                        ollama_diagnostics["eval_duration"] = response.get("eval_duration")

                    if on_start_callback:
                        try:
                            on_start_callback()
                        except Exception as cb_err:
                            print(f"[ENGINE WARNING] Error in on_start_callback: {cb_err}")
                    resp_msg = response.get('message', {})
                    sync_thinking = resp_msg.get('thinking', '')
                    sync_content = resp_msg.get('content', '')
                    if sync_thinking:
                        response_text = f"<think>{sync_thinking}</think>{sync_content}"
                    else:
                        response_text = sync_content
                    if response_text and chunk_callback:
                        chunk_callback(response_text)
            else:
                if status_callback:
                    status_callback("Réflexion du modèle...")
                response = client.chat(model=target_model, messages=messages, options=options)
                
                if isinstance(ollama_diagnostics, dict):
                    ollama_diagnostics["done"] = response.get("done", True)
                    ollama_diagnostics["done_reason"] = response.get("done_reason")
                    ollama_diagnostics["prompt_eval_count"] = response.get("prompt_eval_count")
                    ollama_diagnostics["eval_count"] = response.get("eval_count")
                    ollama_diagnostics["total_duration"] = response.get("total_duration")
                    ollama_diagnostics["load_duration"] = response.get("load_duration")
                    ollama_diagnostics["prompt_eval_duration"] = response.get("prompt_eval_duration")
                    ollama_diagnostics["eval_duration"] = response.get("eval_duration")

                if on_start_callback:
                    try:
                        on_start_callback()
                    except Exception as cb_err:
                        print(f"[ENGINE WARNING] Error in on_start_callback: {cb_err}")
                resp_msg = response.get('message', {})
                sync_thinking = resp_msg.get('thinking', '')
                sync_content = resp_msg.get('content', '')
                if sync_thinking:
                    response_text = f"<think>{sync_thinking}</think>{sync_content}"
                else:
                    response_text = sync_content
            
            text = response_text.strip()
            _safe_print(f"\n[DIAGNOSTIC] RAW OLLAMA RESPONSE (Model: {target_model}):\n{text}\n")
            return text if text else None
            
        except Exception as e:
            _safe_print(f"\n[DEBUG: Erreur critique Ollama -> {e}]")
            
            import httpx
            is_timeout = isinstance(e, httpx.TimeoutException) or "timeout" in str(e).lower()
            if is_timeout:
                timeout_msg = (
                    "[DIAGNOSTIC ENGINE WARNING] La requête d'inférence vers Ollama a expiré (timeout).\n"
                    "Causes possibles :\n"
                    "  - Une autre application ou un autre agent de discussion utilise Ollama activement.\n"
                    "  - Un changement de modèle lourd est en cours dans le GPU (VRAM swapping).\n"
                    "  - La puissance de calcul de votre GPU/CPU est saturée.\n"
                    "Vous pouvez configurer 'ollama_request_timeout' dans settings.json pour augmenter ce délai."
                )
                log_diagnostic(timeout_msg)
                _safe_print(f"\n{timeout_msg}\n")
            else:
                log_diagnostic(f"[DIAGNOSTIC ENGINE ERROR] Erreur lors de l'appel Ollama : {e}")

            if isinstance(ollama_diagnostics, dict):
                err_type = "TimeoutError" if is_timeout else type(e).__name__
                ollama_diagnostics["exception"] = f"Critical error: {err_type}: {e}"

            try:
                if isinstance(e, httpx.TimeoutException):
                    raise e
            except ImportError:
                if "timeout" in str(e).lower():
                    raise e
            return None

    def extract_fact(self, last_user_message):
        """
        Demande à l'IA d'extraire une info durable et de la classer.
        Ignore les salutations et le bavardage inutile.
        """
        prompt = f"""
        MESSAGE \u00c0 ANALYSER : "{last_user_message}"
        
        INSTRUCTIONS :
        1. Analyse si le message contient une information DURABLE et IMPORTANTE (nom, pr\u00e9f\u00e9rence, fait, trait de personnalit\u00e9).
        2. IGNORE imp\u00e9rativement :
           - Les salutations, politesses, questions sur ton \u00e9tat.
           - Les commandes syst\u00e8me de fichiers (ex: "ouvre le fichier").
           - Les phrases purement conversationnelles sans fait nouveau.
        3. Si une info est trouv\u00e9e, CLASSE-LA STRICTEMENT :
           - "assistant_profile" : traits d'Anna (ex: "tu as les cheveux bleus").
           - "user_profile" : traits de l'utilisateur (ex: "je m'appelle Louis").
           - "long_term_facts" : faits g\u00e9n\u00e9raux (ex: "on travaille sur un projet IA").
        
        4. FORMAT DE R\u00c9PONSE (JSON UNIQUEMENT) :
        {{
            "categorie": "assistant_profile" | "user_profile" | "long_term_facts",
            "cle": "nom_de_la_cle",
            "valeur": "contenu"
        }}
        
        5. SI AUCUNE INFORMATION DURABLE OU EN CAS DE DOUTE : R\u00e9ponds "None" sans rien d'autre.
        """
        try:
            # Charger la configuration globale du contexte
            from config import DEFAULT_MODEL_CONTEXT_SIZE
            active_ctx = DEFAULT_MODEL_CONTEXT_SIZE
            try:
                from settings_manager import SettingsManager
                settings = SettingsManager()
                active_ctx = settings.get_setting("model_context_size", DEFAULT_MODEL_CONTEXT_SIZE)
            except Exception:
                pass
            options = {"num_ctx": active_ctx}
            response = self._get_client().generate(model=self.model, prompt=prompt, options=options)
            content = response['response'].strip()
            if "None" in content or "{" not in content:
                return None
            
            import json
            start = content.find("{")
            end = content.rfind("}") + 1
            data = json.loads(content[start:end])
            
            # Normalisation des clés pour gérer les hallucinations de l'IA (ex: "categori")
            normalized_data = {}
            for k, v in data.items():
                if k.startswith("cat"): normalized_data["categorie"] = v
                elif k == "cle": normalized_data["cle"] = v
                elif k == "valeur" or k == "val": normalized_data["valeur"] = v
            
            return normalized_data
        except:
            return None
