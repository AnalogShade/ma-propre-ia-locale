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
        Demande à l'IA d'extraire une info et de la classer.
        """
        prompt = f"""
        Analyse le message : "{last_user_message}"
        Extraits-en une information importante si elle existe.
        Réponds UNIQUEMENT en JSON sous ce format :
        {{
            "categorie": "profil", "assistant" ou "fait",
            "cle": "nom_de_la_cle",
            "valeur": "description de l'info"
        }}
        Note : "profil" est pour l'utilisateur, "assistant" pour l'IA elle-même.
        Si rien d'important, réponds : None
        """
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            content = response['response'].strip()
            if "None" in content or "{" not in content:
                return None
            
            import json
            start = content.find("{")
            end = content.rfind("}") + 1
            return json.loads(content[start:end])
        except:
            return None
