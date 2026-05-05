import ollama
from config import MODEL_NAME, SYSTEM_PROMPT

class AIEngine:
    def __init__(self):
        self.model = MODEL_NAME
        self.system_prompt = SYSTEM_PROMPT

    def get_response(self, context_messages, user_summary=""):
        """
        Envoie les messages à Ollama et récupère la réponse texte.
        Injecte les infos utilisateur si présentes.
        """
        try:
            # On enrichit le prompt système avec ce qu'on sait de l'utilisateur
            dynamic_system_prompt = self.system_prompt
            if user_summary:
                dynamic_system_prompt += user_summary

            messages_to_send = [
                {'role': 'system', 'content': dynamic_system_prompt}
            ] + context_messages
            
            response = ollama.chat(
                model=self.model,
                messages=messages_to_send,
            )
            return response['message']['content']
        except Exception as e:
            return f"Erreur de communication avec Ollama : {str(e)}"

    def extract_fact(self, last_user_message):
        """
        Demande à l'IA d'extraire un fait unique du message utilisateur.
        Retourne un dictionnaire {clé: valeur} ou None.
        """
        prompt = f"""
        Analyse le message suivant de l'utilisateur : "{last_user_message}"
        Extraits-en une SEULE information importante (nom, projet, préférence, fait marquant).
        Réponds UNIQUEMENT sous la forme d'un JSON simple comme ceci : {{"cle_courte": "description du fait"}}
        Si aucune information importante n'est présente, réponds : None
        """
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            content = response['response'].strip()
            if "None" in content or "{" not in content:
                return None
            
            # On essaie d'extraire le JSON du texte
            import json
            start = content.find("{")
            end = content.rfind("}") + 1
            return json.loads(content[start:end])
        except:
            return None
