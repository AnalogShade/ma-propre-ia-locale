import json
import ollama

SD_UPDATE_INTERPRETER_PROMPT = """Tu es un interprète d'intentions spécialisé dans l'ajustement de paramètres pour Stable Diffusion.
Ton rôle est d'analyser le message de l'utilisateur par rapport aux paramètres de génération actuels, et de déterminer l'action qu'il souhaite effectuer.

Tu dois classifier la demande de l'utilisateur parmi ces 4 actions et retourner UNIQUEMENT un objet JSON valide :

1. Action "update_image_params" :
   L'utilisateur exprime le souhait de modifier un ou plusieurs paramètres de l'image (ex: "mets le CFG à 6", "je veux un format portrait", "ajoute un style aquarelle", "change le checkpoint", "seed à 42").
   Tu dois extraire uniquement les modifications dans un objet "updates".
   Les clés autorisées dans "updates" sont :
     - "prompt" (string) : Si l'utilisateur ajoute un style, un détail ou modifie la description (traduire et enrichir en anglais, ex: "ajoute un style aquarelle" -> ajoute ", watercolor style" au prompt existant).
     - "negative_prompt" (string) : Si l'utilisateur veut ajouter ou retirer des éléments à éviter.
     - "width" (int) : Largeur en pixels (ex: "format paysage" -> 768 ou 832, "format portrait" -> 512, "format carré" -> 512).
     - "height" (int) : Hauteur en pixels (ex: "format paysage" -> 512, "format portrait" -> 768 ou 832, "format carré" -> 512).
     - "steps" (int) : Nombre d'étapes (ex: "mets 40 steps" -> 40).
     - "cfg_scale" (float) : Échelle de liberté (ex: "met le CFG à 6" -> 6.0).
     - "sampler" (string) : Méthode d'échantillonnage (ex: "utilise DPM++ 2M Karras").
     - "seed" (int) : Graine aléatoire (ex: "seed à 12345").
     - "checkpoint" (string) : Fichier de modèle (ex: "utilise realisticVision").
   Tu devez également rédiger un message de confirmation chaleureux et précis en français dans la clé "user_message" (ex: "D'accord, j'ai mis le CFG scale à 6.0 et j'ai configuré les dimensions en format paysage (768x512).").

2. Action "confirm_generation" :
   L'utilisateur confirme qu'il est satisfait et souhaite lancer la génération/simulation (ex: "génère", "lance la génération", "c'est parti", "ok !", "c'est parfait", "lance").

3. Action "cancel_generation" :
   L'utilisateur souhaite annuler la session de génération d'image ou quitter le mode image (ex: "annule", "quitte", "stop", "retour").

4. Action "normal_message" :
   Le message de l'utilisateur n'a aucun rapport avec la génération d'image ou ses paramètres (ex: "qui es-tu ?", "comment vas-tu ?").

Tu dois répondre UNIQUEMENT avec du JSON valide. Ne rajoute aucun commentaire, aucune phrase avant ou après le JSON.

FORMATS DE RÉPONSES STRICTS EN JSON :

- Si modification de paramètres :
{
    "action": "update_image_params",
    "updates": {
        "cfg_scale": 6.0,
        "steps": 40
    },
    "user_message": "Parfait ! J'ai ajusté le CFG à 6.0 et configuré le nombre d'étapes à 40."
}

- Si confirmation :
{
    "action": "confirm_generation"
}

- Si annulation :
{
    "action": "cancel_generation"
}

- Si message hors-sujet :
{
    "action": "normal_message"
}
"""

class ImageParamUpdateInterpreter:
    def __init__(self, ai_engine):
        """
        Initialise l'interprète de correction avec l'instance de AIEngine active.
        """
        self.engine = ai_engine

    def interpret_correction(self, current_params, user_message):
        """
        Interroge Ollama pour déterminer si le message de l'utilisateur modifie les paramètres existants,
        confirme la génération, annule la session ou est un message hors-sujet.
        Retourne un dictionnaire contenant l'action et ses paramètres associés.
        """
        system_prompt = SD_UPDATE_INTERPRETER_PROMPT
        payload = f"""PARAMÈTRES ACTUELS :
{json.dumps(current_params, indent=2, ensure_ascii=False)}

MESSAGE DE L'UTILISATEUR :
"{user_message}"
"""

        try:
            # Appel d'Ollama avec le modèle actif configuré dans l'AIEngine
            response = ollama.chat(
                model=self.engine.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': payload}
                ]
            )
            
            raw_content = response['message']['content'].strip()
            
            # Extraction robuste du bloc JSON
            start = raw_content.find("{")
            end = raw_content.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("Aucun JSON trouvé dans la réponse du modèle d'interprétation")
                
            json_str = raw_content[start:end]
            parsed_data = json.loads(json_str)
            
            # Normalisation basique de la réponse
            action = parsed_data.get("action", "normal_message")
            result = {"action": action}
            
            if action == "update_image_params":
                result["updates"] = parsed_data.get("updates", {})
                result["user_message"] = parsed_data.get("user_message", "J'ai pris en compte vos modifications.")
                
            return result
            
        except Exception as e:
            print(f"[IMAGE INTERPRETER WARNING] Échec de l'interprétation du message : {e}")
            # Fallback sûr et robuste : traiter comme un message normal pour éviter tout plantage
            return {
                "action": "normal_message"
            }
