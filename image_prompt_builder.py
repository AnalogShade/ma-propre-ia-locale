import json
import ollama

SD_REFORMULATION_PROMPT = """Tu es un expert en ingénierie de prompt pour Stable Diffusion.
Ton rôle est de prendre la description en langage naturel d'un utilisateur et de la convertir en un objet JSON contenant les paramètres parfaits pour Stable Diffusion.

Tu dois impérativement respecter les règles suivantes :
1. Traduis tous les concepts en anglais (Stable Diffusion fonctionne beaucoup mieux en anglais).
2. Enrichis le prompt avec des modificateurs de style et de qualité adaptés (ex: "masterpiece", "highly detailed", "sharp focus", "studio lighting", "8k resolution").
3. Identifie le format demandé (portrait, paysage, carré) et définis des dimensions (width/height) compatibles :
   - Paysage (landscape) -> 768x512 ou 832x512
   - Portrait -> 512x768 ou 512x832
   - Carré (square) -> 512x512
   Si aucun format n'est spécifié, utilise par défaut 512x512.
4. Fournis un "negative_prompt" solide et standardisé (ex: "blurry, low quality, distorted, bad anatomy, deformed, watermark, signature, bad hands").
5. Suggère le style artistique détecté (ex: "cyberpunk", "watercolor", "photorealistic", "digital art", etc.).
6. Propose des valeurs par défaut intelligentes : steps = 25, cfg_scale = 7.5, sampler = "Euler a", seed = -1.

Tu dois répondre UNIQUEMENT avec un objet JSON valide. Ne rajoute aucune explication, aucune phrase d'introduction ou de conclusion.

FORMAT DE RÉPONSE REQUIS (JSON STRICT) :
{
    "description_originale": "La description originale en français",
    "prompt": "Le prompt enrichi et traduit en anglais",
    "negative_prompt": "Le negative prompt en anglais",
    "style": "Le style détecté",
    "width": 512,
    "height": 512,
    "steps": 25,
    "cfg_scale": 7.5,
    "sampler": "Euler a",
    "seed": -1,
    "checkpoint": "sd_xl_base_1.0.safetensors"
}
"""

class ImagePromptBuilder:
    def __init__(self, ai_engine):
        """
        Initialise le générateur de prompt avec l'instance de AIEngine active.
        """
        self.engine = ai_engine

    def build_initial_proposal(self, user_description):
        """
        Interroge Ollama pour traduire et enrichir la description de l'utilisateur,
        puis retourne un dictionnaire de paramètres Stable Diffusion structuré.
        """
        system_prompt = SD_REFORMULATION_PROMPT
        user_message = f"Description de l'image : \"{user_description}\""
        
        try:
            # Appel direct à Ollama en utilisant le modèle actif configuré dans l'AIEngine
            response = ollama.chat(
                model=self.engine.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message}
                ]
            )
            
            raw_content = response['message']['content'].strip()
            
            # Extraction robuste du bloc JSON (évite les bavardages ou les balises markdown ```json)
            start = raw_content.find("{")
            end = raw_content.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("Aucun JSON trouvé dans la réponse du modèle")
                
            json_str = raw_content[start:end]
            parsed_data = json.loads(json_str)
            
            # Validation des types et valeurs par défaut en cas de clés manquantes
            proposal = {
                "description_originale": parsed_data.get("description_originale", user_description),
                "prompt": parsed_data.get("prompt", user_description),
                "negative_prompt": parsed_data.get("negative_prompt", "blurry, low quality, distorted, watermark, signature"),
                "style": parsed_data.get("style", "digital art"),
                "width": int(parsed_data.get("width", 512)),
                "height": int(parsed_data.get("height", 512)),
                "steps": int(parsed_data.get("steps", 25)),
                "cfg_scale": float(parsed_data.get("cfg_scale", 7.5)),
                "sampler": parsed_data.get("sampler", "Euler a"),
                "seed": int(parsed_data.get("seed", -1)),
                "checkpoint": parsed_data.get("checkpoint", "")
            }
            return proposal
            
        except Exception as e:
            print(f"[IMAGE PROMPT BUILDER WARNING] Échec de la génération du prompt : {e}")
            # Fallback sécurisé en cas d'erreur de parsing, d'exception ou d'Ollama hors-ligne
            return {
                "description_originale": user_description,
                "prompt": user_description,
                "negative_prompt": "blurry, low quality, distorted, watermark, signature",
                "style": "Non détecté",
                "width": 512,
                "height": 512,
                "steps": 25,
                "cfg_scale": 7.5,
                "sampler": "Euler a",
                "seed": -1,
                "checkpoint": ""
            }
