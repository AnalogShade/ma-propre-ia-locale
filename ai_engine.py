import sys
import os
import subprocess
import ollama
from config import MODEL_NAME, SYSTEM_PROMPT, DEFAULT_NAME, log_diagnostic

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
        """Retourne une instance du client Ollama configurée avec le timeout."""
        from config import OLLAMA_REQUEST_TIMEOUT_SECONDS
        return ollama.Client(timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)

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
        known_vision_keywords = ['gemma4', 'llava', 'vision', 'paligemma', 'minicpm-v', 'bakllava', 'llama3.2-vision']
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

    def evaluate_request_risk(self, model_name, has_image):
        """
        Évalue le risque de lenteur ou d'échec pour la requête actuelle.
        Retourne un dictionnaire contenant le niveau de risque et les détails.
        """
        result = {
            "level": "low_risk",
            "reason": "La configuration matérielle et le modèle semblent adaptés pour un traitement rapide.",
            "model_size_gb": None,
            "gpu_vram_gb": None,
            "image_extra_estimate_gb": 1.5,
            "confidence": "high"
        }
        
        # 1. Si aucune image n'est envoyée, le risque est faible
        if not has_image:
            return result
            
        gpu_vram = self.get_gpu_vram()
        model_size = self.get_model_size(model_name)
        
        result["gpu_vram_gb"] = gpu_vram
        result["model_size_gb"] = model_size
        
        # 2. Si les infos ne peuvent pas être obtenues, on renvoie moderate_risk avec une confiance faible
        if gpu_vram is None or model_size is None:
            result["level"] = "moderate_risk"
            result["confidence"] = "low"
            result["reason"] = "Impossible de détecter précisément la VRAM ou la taille du modèle installé. Risque modéré par défaut."
            return result
            
        # 3. Calcul heuristique du risque avec les deux infos disponibles
        total_estimated_needed = model_size + result["image_extra_estimate_gb"]
        
        if total_estimated_needed > gpu_vram:
            result["level"] = "high_risk"
            result["reason"] = f"La taille estimée du modèle installé ({model_size:.1f} Go) avec la surcharge d'image ({result['image_extra_estimate_gb']:.1f} Go) est supérieure à la VRAM détectée ({gpu_vram:.1f} Go)."
        elif total_estimated_needed > gpu_vram * 0.75:
            result["level"] = "moderate_risk"
            result["reason"] = f"La taille estimée du modèle installé ({model_size:.1f} Go) approche de la limite de la VRAM totale détectée ({gpu_vram:.1f} Go). Un ralentissement modéré est possible."
        else:
            result["level"] = "low_risk"
            result["reason"] = f"La taille estimée du modèle installé ({model_size:.1f} Go) et la surcharge d'image tiennent dans la VRAM totale détectée ({gpu_vram:.1f} Go)."
            
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

    def get_response(self, context_messages, images=None, user_summary="", assistant_summary="", assistant_name=DEFAULT_NAME, files_context="", compressed_context="", model_name=None, chunk_callback=None, status_callback=None, on_start_callback=None):
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
            clean_context = []
            for m in context_messages:
                clean_msg = {"role": m["role"], "content": m["content"]}
                if "images" in m:
                    clean_msg["images"] = m["images"]
                clean_context.append(clean_msg)
                
            # Attacher les pièces jointes temporaires de la requête courante au tout dernier message utilisateur
            if images and clean_context:
                clean_context[-1]["images"] = images
                
            messages = [{'role': 'system', 'content': system_content}] + clean_context
            
            target_model = model_name if model_name else self.model
            _safe_print(f"\n[DIAGNOSTIC] FULL PAYLOAD TO OLLAMA (Model: {target_model}):\n{messages}\n")

            # 3. Appel Ollama (avec support streaming et fallback)
            if status_callback:
                status_callback("Envoi au modèle...")
                
            response_text = ""
            client = self._get_client()
            if chunk_callback:
                try:
                    if status_callback:
                        status_callback("Réflexion du modèle...")
                    stream = client.chat(model=target_model, messages=messages, stream=True)
                    
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
                            
                    # Clôture de sécurité
                    if sent_think_start and not sent_think_end:
                        chunk_callback("</think>")
                        response_text += "</think>"
                        
                except Exception as stream_err:
                    _safe_print(f"\n[DEBUG: Échec du streaming, repli en mode synchrone -> {stream_err}]")
                    # Si c'est un timeout, on le propage immédiatement
                    import httpx
                    if isinstance(stream_err, httpx.TimeoutException):
                        raise stream_err
                    if "timeout" in str(stream_err).lower():
                        raise stream_err
                        
                    if status_callback:
                        status_callback("Réflexion du modèle (Repli synchrone)...")
                    response = client.chat(model=target_model, messages=messages)
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
                response = client.chat(model=target_model, messages=messages)
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
            log_diagnostic(f"[DIAGNOSTIC ENGINE ERROR] Erreur lors de l'appel Ollama : {e}")
            try:
                import httpx
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
            response = self._get_client().generate(model=self.model, prompt=prompt)
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
