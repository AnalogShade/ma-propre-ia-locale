import urllib.request
import urllib.error
import json
import time

class StableDiffusionService:
    def __init__(self, api_url="http://127.0.0.1:7860"):
        """
        Initialise le service de communication avec Stable Diffusion.
        """
        self.api_url = api_url.rstrip('/')

    def update_api_url(self, new_url):
        """
        Permet de mettre à jour dynamiquement l'URL de l'API.
        """
        self.api_url = new_url.rstrip('/')

    def is_api_available(self):
        """
        Effectue un ping HTTP rapide (timeout de 1.0s) pour vérifier
        si l'API locale d'AUTOMATIC1111 est en ligne.
        """
        try:
            url = f"{self.api_url}/sdapi/v1/sd-models"
            req = urllib.request.Request(url, method="GET")
            # Un timeout très court garantit que l'appel ne bloque pas l'interface
            with urllib.request.urlopen(req, timeout=1.0) as response:
                return response.status == 200
        except Exception:
            return False

    def get_online_checkpoints(self):
        """
        Interroge l'API AUTOMATIC1111 pour récupérer les checkpoints installés localement.
        Retourne une liste vide si l'API est inaccessible.
        """
        if not self.is_api_available():
            return []
            
        try:
            url = f"{self.api_url}/sdapi/v1/sd-models"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                # L'API retourne une liste d'objets contenant 'title' (ex: 'v1-5-pruned.safetensors')
                checkpoints = []
                for model in data:
                    if isinstance(model, dict):
                        if 'title' in model:
                            checkpoints.append(model['title'])
                        elif 'model_name' in model:
                            checkpoints.append(model['model_name'])
                return checkpoints
        except Exception as e:
            print(f"[SD SERVICE WARNING] Échec de la récupération des checkpoints en ligne : {e}")
            return []

    def get_online_samplers(self):
        """
        Interroge l'API AUTOMATIC1111 pour récupérer les samplers disponibles.
        Retourne une liste vide si l'API est inaccessible.
        """
        if not self.is_api_available():
            return []
            
        try:
            url = f"{self.api_url}/sdapi/v1/samplers"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                samplers = []
                for sampler in data:
                    if isinstance(sampler, dict) and 'name' in sampler:
                        samplers.append(sampler['name'])
                return samplers
        except Exception as e:
            print(f"[SD SERVICE WARNING] Échec de la récupération des samplers en ligne : {e}")
            return []

    def get_generation_progress(self):
        """
        Interroge l'API de progression de Stable Diffusion.
        Retourne un dictionnaire avec le pourcentage de progression (0 à 100) et l'ETA en secondes.
        Renvoie {"progress": 0.0, "eta": 0.0} en cas d'erreur ou si indisponible.
        """
        if not self.is_api_available():
            return {"progress": 0.0, "eta": 0.0}
            
        try:
            url = f"{self.api_url}/sdapi/v1/progress"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=0.5) as response:
                data = json.loads(response.read().decode('utf-8'))
                progress = data.get("progress", 0.0)
                eta = data.get("eta_relative", 0.0)
                return {
                    "progress": round(progress * 100.0, 1),
                    "eta": round(eta, 1)
                }
        except Exception:
            return {"progress": 0.0, "eta": 0.0}

    def generate_image(self, params):
        """
        Génère une image réelle via l'API de Stable Diffusion (txt2img) de façon sécurisée.
        """
        import random
        final_seed = params.get("seed", -1)
        if final_seed == -1:
            final_seed = random.randint(100000000, 999999999)

        try:
            # 0. Changement dynamique de checkpoint si nécessaire
            checkpoint = params.get("checkpoint", "")
            if checkpoint:
                try:
                    opt_url = f"{self.api_url}/sdapi/v1/options"
                    opt_req = urllib.request.Request(opt_url, method="GET")
                    with urllib.request.urlopen(opt_req, timeout=2.0) as opt_res:
                        options = json.loads(opt_res.read().decode('utf-8'))
                        current_checkpoint = options.get("sd_model_checkpoint", "")
                    
                    # Si le checkpoint demandé diffère de l'actif (comparaison robuste à double sens)
                    if current_checkpoint and checkpoint not in current_checkpoint and current_checkpoint not in checkpoint:
                        opt_payload = {"sd_model_checkpoint": checkpoint}
                        opt_data = json.dumps(opt_payload).encode("utf-8")
                        opt_post_req = urllib.request.Request(opt_url, data=opt_data, method="POST")
                        opt_post_req.add_header("Content-Type", "application/json")
                        with urllib.request.urlopen(opt_post_req, timeout=30.0) as opt_post_res:
                            pass
                except Exception as e:
                    print(f"[SD SERVICE WARNING] Échec du changement dynamique de checkpoint : {e}")

            # 1. Construction du payload de paramètres
            payload = {
                "prompt": params.get("prompt", ""),
                "negative_prompt": params.get("negative_prompt", ""),
                "steps": params.get("steps", 25),
                "cfg_scale": params.get("cfg_scale", 7.5),
                "width": params.get("width", 512),
                "height": params.get("height", 512),
                "sampler_name": params.get("sampler", "Euler a"),
                "seed": final_seed
            }

            # 2. Envoi de la requête réelle txt2img
            url = f"{self.api_url}/sdapi/v1/txt2img"
            data_json = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data_json, method="POST")
            req.add_header("Content-Type", "application/json")
            
            # Envoi synchrone (timeout réaliste de 120s pour la génération)
            with urllib.request.urlopen(req, timeout=120.0) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            # 3. Décodage Base64 et sauvegarde physique
            import base64
            import os
            
            image_path = None
            if "images" in data and len(data["images"]) > 0:
                image_base64 = data["images"][0]
                # Retrait d'un éventuel préambule base64
                if "," in image_base64:
                    image_base64 = image_base64.split(",")[1]
                image_bytes = base64.b64decode(image_base64)
                
                # Nom de fichier unique basé sur le timestamp et la seed
                timestamp = int(time.time())
                filename = f"image_{timestamp}_{final_seed}.png"
                output_dir = os.path.join("data", "output_images")
                
                # Sécurité de création du répertoire de sortie
                os.makedirs(output_dir, exist_ok=True)
                
                image_path = os.path.abspath(os.path.join(output_dir, filename))
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
            
            return {
                "status": "success",
                "message": "Génération réelle et sauvegarde physique effectuées avec succès.",
                "params": {
                    "prompt": params.get("prompt", ""),
                    "negative_prompt": params.get("negative_prompt", ""),
                    "width": params.get("width", 512),
                    "height": params.get("height", 512),
                    "steps": params.get("steps", 25),
                    "cfg_scale": params.get("cfg_scale", 7.5),
                    "sampler": params.get("sampler", "Euler a"),
                    "checkpoint": params.get("checkpoint", ""),
                    "seed": final_seed,
                    "style": params.get("style", "Non spécifié")
                },
                "image_path": image_path
            }
        except Exception as e:
            # En cas de problème (timeout, déconnexion, manque de VRAM, etc.), retourner un dictionnaire d'échec structuré
            print(f"[SD SERVICE ERROR] Échec de la génération d'image : {e}")
            return {
                "status": "error",
                "message": f"Stable Diffusion a rencontré une erreur ou manque de mémoire VRAM. Détails : {str(e)}",
                "params": {
                    "prompt": params.get("prompt", ""),
                    "negative_prompt": params.get("negative_prompt", ""),
                    "width": params.get("width", 512),
                    "height": params.get("height", 512),
                    "steps": params.get("steps", 25),
                    "cfg_scale": params.get("cfg_scale", 7.5),
                    "sampler": params.get("sampler", "Euler a"),
                    "checkpoint": params.get("checkpoint", ""),
                    "seed": final_seed,
                    "style": params.get("style", "Non spécifié")
                },
                "image_path": None
            }
