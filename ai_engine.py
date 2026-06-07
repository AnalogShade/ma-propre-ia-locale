import sys
import ollama
from config import MODEL_NAME, SYSTEM_PROMPT, DEFAULT_NAME

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
        except Exception:
            pass
            
        # Fallback sémantique sur le nom du modèle
        model_lower = model_name.lower()
        known_vision_keywords = ['gemma4', 'llava', 'vision', 'paligemma', 'minicpm-v', 'bakllava', 'llama3.2-vision']
        return any(k in model_lower for k in known_vision_keywords)

    def get_installed_models(self):
        """
        Interroge Ollama localement pour obtenir la liste des modèles installés.
        Retourne une liste de chaînes (les noms des modèles).
        Retourne une liste vide si Ollama n'est pas démarré ou en cas d'erreur.
        """
        try:
            models_info = ollama.list()
            
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

    def get_response(self, context_messages, images=None, user_summary="", assistant_summary="", assistant_name=DEFAULT_NAME, files_context="", model_name=None, chunk_callback=None, status_callback=None):
        try:
            # 1. Construction du prompt système
            system_content = self.system_prompt.strip().format(name=assistant_name)
            
            if assistant_summary:
                system_content += f"\n{assistant_summary}"

            if user_summary:
                system_content += f"\nContexte utilisateur :\n{user_summary}"
            
            if files_context:
                system_content += f"\n{files_context}"

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
            if chunk_callback:
                try:
                    if status_callback:
                        status_callback("Réflexion du modèle...")
                    stream = ollama.chat(model=target_model, messages=messages, stream=True)
                    
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
                    if status_callback:
                        status_callback("Réflexion du modèle (Repli synchrone)...")
                    response = ollama.chat(model=target_model, messages=messages)
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
                response = ollama.chat(model=target_model, messages=messages)
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
            response = ollama.generate(model=self.model, prompt=prompt)
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
