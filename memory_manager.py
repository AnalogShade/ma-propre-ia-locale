import json
import os
from config import MEMORY_FILE, CONTEXT_WINDOW

class MemoryManager:
    def __init__(self):
        self.history = []
        self.load_from_disk()

    def load_from_disk(self):
        """Charge l'historique JSON s'il existe."""
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []

    def save_to_disk(self):
        """Sauvegarde l'historique complet sur le disque."""
        # Créer le dossier data s'il n'existe pas
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        
        try:
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erreur de sauvegarde : {e}")

    def add_message(self, role, content):
        """Ajoute un message (user ou assistant) et sauvegarde."""
        self.history.append({"role": role, "content": content})
        self.save_to_disk()

    def get_context(self):
        """Retourne uniquement les derniers messages (limite définie en config)."""
        return self.history[-CONTEXT_WINDOW:]

    def clear(self):
        """Efface tout."""
        self.history = []
        if os.path.exists(MEMORY_FILE):
            os.remove(MEMORY_FILE)
