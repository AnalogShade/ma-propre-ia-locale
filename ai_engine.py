import ollama
from config import MODEL_NAME, SYSTEM_PROMPT

class AIEngine:
    def __init__(self):
        self.model = MODEL_NAME
        self.system_prompt = SYSTEM_PROMPT

    def get_response(self, context_messages, user_summary=""):
        try:
            # On construit un prompt système clair
            system_content = self.system_prompt
            if user_summary:
                system_content += f"\nVoici ce que tu sais sur l'utilisateur :\n{user_summary}"

            messages = [{'role': 'system', 'content': system_content}] + context_messages
            
            response = ollama.chat(model=self.model, messages=messages)
            text = response['message']['content']
            
            return text if text.strip() else "(L'IA n'a pas renvoyé de texte)"
        except Exception as e:
            return f"Erreur : {str(e)}"

    def extract_fact(self, last_user_message):
        """
        Demande à l'IA d'extraire une info et de la classer.
        """
        prompt = f"""
        MESSAGE À ANALYSER : "{last_user_message}"
        
        INSTRUCTION : Extraits un fait et CLASSE-LE impérativement selon ces règles de grammaire :
        
        - Si le message dit "TU", "TON", "TA" ou parle de l'IA -> categorie: "assistant_profile"
        - Si le message dit "JE", "MON", "MA" ou parle de l'humain -> categorie: "user_profile"
        - Si c'est une info générale ou une préférence sans sujet précis -> categorie: "long_term_facts"
        
        FORMAT DE RÉPONSE (JSON UNIQUEMENT) :
        {{
            "categorie": "user_profile", "assistant_profile" ou "long_term_facts",
            "cle": "nom_de_la_cle",
            "valeur": "contenu"
        }}
        
        EXEMPLES :
        - "Ton nom est Anna" -> {{"categorie": "assistant_profile", "cle": "nom", "valeur": "Anna"}}
        - "Je suis Louis" -> {{"categorie": "user_profile", "cle": "nom", "valeur": "Louis"}}
        
        SI AUCUNE INFO : Réponds "None"
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
