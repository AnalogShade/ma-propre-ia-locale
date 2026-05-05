import ollama
from config import MODEL_NAME, SYSTEM_PROMPT

class AIEngine:
    def __init__(self):
        self.model = MODEL_NAME
        self.system_prompt = SYSTEM_PROMPT

    def get_response(self, context_messages):
        """
        Envoie les messages à Ollama et récupère la réponse texte.
        """
        try:
            # On prépare la liste des messages en commençant par le prompt système
            messages_to_send = [
                {'role': 'system', 'content': self.system_prompt}
            ] + context_messages
            
            # Appel à l'API locale d'Ollama
            response = ollama.chat(
                model=self.model,
                messages=messages_to_send,
            )
            
            # On retourne uniquement le contenu du message de réponse
            return response['message']['content']
            
        except Exception as e:
            return f"Erreur de communication avec Ollama : {str(e)}"
