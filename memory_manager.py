import json
import os
from datetime import datetime
from config import (
    HISTORY_FILE, USER_PROFILE_FILE, 
    ASSISTANT_PROFILE_FILE, FACTS_FILE, 
    MAX_HISTORY, CONTEXT_WINDOW
)

class MemoryManager:
    def __init__(self):
        # Initialisation des structures de données
        self.history = []
        self.user_profile = {}
        self.assistant_profile = {}
        self.facts = {}
        
        # Chargement de tous les fichiers
        self.load_all()

    def _load_file(self, file_path, default_value):
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erreur chargement {file_path}: {e}")
        return default_value

    def _save_file(self, file_path, data):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erreur sauvegarde {file_path}: {e}")

    def load_all(self):
        self.history = self._load_file(HISTORY_FILE, [])
        self.user_profile = self._load_file(USER_PROFILE_FILE, {})
        self.assistant_profile = self._load_file(ASSISTANT_PROFILE_FILE, {})
        self.facts = self._load_file(FACTS_FILE, {})

    def add_message(self, role, content):
        """Ajoute un message à l'historique court terme."""
        self.history.append({"role": role, "content": content, "timestamp": str(datetime.now())})
        
        # Limite la taille de l'historique brut
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
            
        self._save_file(HISTORY_FILE, self.history)

    def update_user_profile(self, key, value):
        self.user_profile[key] = value
        self._save_file(USER_PROFILE_FILE, self.user_profile)

    def update_assistant_profile(self, key, value):
        self.assistant_profile[key] = value
        self._save_file(ASSISTANT_PROFILE_FILE, self.assistant_profile)

    def add_fact(self, key, value):
        """Ajoute un fait ou incrémente son compteur s'il existe déjà."""
        if key in self.facts:
            self.facts[key]["count"] += 1
            self.facts[key]["last_seen"] = str(datetime.now())
        else:
            self.facts[key] = {
                "value": value,
                "count": 1,
                "first_seen": str(datetime.now()),
                "last_seen": str(datetime.now())
            }
        self._save_file(FACTS_FILE, self.facts)

    def process_extracted_fact(self, fact_dict):
        """Re\u00e7oit un dictionnaire (categorie, cle, valeur) et l'aiguille vers le bon stockage."""
        if not fact_dict or not isinstance(fact_dict, dict):
            return
        
        cat = fact_dict.get("categorie")
        cle = fact_dict.get("cle")
        val = fact_dict.get("valeur")
        
        if not cat or not cle or not val:
            return

        if cat == "user_profile":
            self.update_user_profile(cle, val)
        elif cat == "assistant_profile":
            self.update_assistant_profile(cle, val)
        elif cat == "long_term_facts":
            self.add_fact(cle, val)

    def get_context(self, context_size=None):
        """Retourne les derniers messages pour Ollama."""
        if context_size is None:
            context_size = CONTEXT_WINDOW
        return self.history[-context_size:]

    def get_user_info_summary(self):
        """Crée un résumé naturel des connaissances sur l'utilisateur."""
        if not self.user_profile and not self.facts:
            return ""
        
        summary = "\n--- CE QUE TU SAIS SUR L'HUMAIN (Louis) ---\n"
        
        # Profil de base
        for k, v in self.user_profile.items():
            summary += f"- Son {k} est {v}\n"
        
        # Faits extraits
        if self.facts:
            summary += "\nFaits marquants et préférences :\n"
            for k, v in self.facts.items():
                # On ne montre que les faits confirmés (count > 1) ou importants
                if v["count"] > 1:
                    summary += f"- {v['value']}\n"
        
        summary += "--- FIN DES CONNAISSANCES ---\n"
        return summary

    def get_assistant_info_summary(self):
        """Cr\u00e9e un r\u00e9sum\u00e9 naturel de ta propre identit\u00e9."""
        if not self.assistant_profile:
            return ""
        
        summary = "\n--- TON IDENTIT\u00c9 ET TES TRAITS ---\n"
        for k, v in self.assistant_profile.items():
            summary += f"- Ton/Ta {k} : {v}\n"
        summary += "--- FIN DE TON IDENTIT\u00c9 ---\n"
        return summary

    def clear(self):
        """Efface tout l'historique court terme mais garde les profils et faits."""
        self.history = []
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        print("Historique court terme effacé.")
