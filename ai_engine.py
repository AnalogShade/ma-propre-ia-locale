import ollama
from config import MODEL_NAME, SYSTEM_PROMPT, DEFAULT_NAME

class AIEngine:
    def __init__(self):
        self.model = MODEL_NAME
        self.system_prompt = SYSTEM_PROMPT

    def get_response(self, context_messages, user_summary="", assistant_name=DEFAULT_NAME):
        try:
            # 1. Construction du prompt système
            system_content = self.system_prompt.strip().format(name=assistant_name)
            if user_summary:
                system_content += f"\nContexte utilisateur :\n{user_summary}"

            # 2. Nettoyage des messages (Strict: role et content uniquement)
            clean_context = [{"role": m["role"], "content": m["content"]} for m in context_messages]
            messages = [{'role': 'system', 'content': system_content}] + clean_context
            
            # 3. Appel Ollama
            response = ollama.chat(model=self.model, messages=messages)
            
            text = response['message']['content'].strip()
            return text if text else None
            
        except Exception as e:
            print(f"\n[DEBUG: Erreur critique Ollama -> {e}]")
            return None

    def extract_fact(self, last_user_message):
        """
        Demande à l'IA d'extraire une info durable et de la classer.
        Ignore les salutations et le bavardage inutile.
        """
        prompt = f"""
        MESSAGE À ANALYSER : "{last_user_message}"
        
        INSTRUCTIONS :
        1. Analyse si le message contient une information DURABLE (nom, préférence, fait important, projet).
        2. IGNORE impérativement :
           - Les salutations ("Salut", "Bonjour", "Coucou", etc.)
           - Les questions de politesse ("Ça va ?", "Comment vas-tu ?")
           - Les mentions simples du nom de l'IA ("Salut Anna")
        3. Si une information durable est trouvée, CLASSE-LA :
           - Information sur l'IA (nom, personnalité) -> categorie: "assistant_profile"
           - Information sur l'humain (nom, goûts, job) -> categorie: "user_profile"
           - Information générale ou fait marquant -> categorie: "long_term_facts"
        
        4. FORMAT DE RÉPONSE (JSON UNIQUEMENT) :
        {{
            "categorie": "nom_categorie",
            "cle": "nom_de_la_cle",
            "valeur": "contenu"
        }}
        
        5. SI AUCUNE INFORMATION DURABLE : Réponds "None" (sans JSON).
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
