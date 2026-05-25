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

    def generate_image(self, params):
        """
        Simule la génération d'une image pour la V0 en attendant 1.5 seconde.
        Prépare l'architecture pour envoyer la requête de génération réelle en V1.
        """
        # Simulation d'un temps de génération court
        time.sleep(1.5)
        
        # Génération d'une seed si non fournie (-1)
        import random
        final_seed = params.get("seed", -1)
        if final_seed == -1:
            final_seed = random.randint(100000000, 999999999)

        # On renvoie un dictionnaire structuré contenant les détails de la simulation
        return {
            "status": "simulation",
            "message": "Génération simulée avec succès (V0).",
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
            "image_path": None  # Sera géré par la GUI sous forme de placeholder ou canvas
        }
