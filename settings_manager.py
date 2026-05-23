import json
import os

class SettingsManager:
    def __init__(self, file_path="data/settings.json"):
        """
        Initialise le gestionnaire de réglages avec le chemin du fichier JSON.
        Le fichier n'est PAS créé au démarrage. Il est lu s'il existe.
        """
        self.file_path = file_path
        self.settings = {}
        self.load_settings()

    def load_settings(self):
        """
        Charge les réglages depuis le fichier JSON s'il existe.
        Gère gracieusement les fichiers absents ou corrompus.
        """
        if not os.path.exists(self.file_path):
            self.settings = {}
            return

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    # Fichier vide
                    self.settings = {}
                    return
                
                self.settings = json.loads(content)
                if not isinstance(self.settings, dict):
                    print(f"[SETTINGS WARNING] Le fichier {self.file_path} ne contient pas un dictionnaire JSON valide. Réinitialisation.")
                    self.settings = {}
        except json.JSONDecodeError as e:
            print(f"[SETTINGS WARNING] Le fichier {self.file_path} est corrompu (JSON invalide) : {e}. Réinitialisation en mémoire.")
            self.settings = {}
        except Exception as e:
            print(f"[SETTINGS WARNING] Erreur lors de la lecture de {self.file_path} : {e}. Utilisation des réglages en mémoire.")
            self.settings = {}

    def get_setting(self, key, default=None):
        """
        Récupère la valeur d'une préférence.
        Retourne la valeur par défaut si la clé n'existe pas.
        """
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        """
        Définit ou met à jour une préférence, et persiste immédiatement le fichier.
        Le fichier data/settings.json sera créé à cet instant précis s'il n'existait pas.
        """
        self.settings[key] = value
        self.save_settings()

    def save_settings(self):
        """
        Persiste les réglages en mémoire dans data/settings.json.
        Crée les répertoires parents s'ils n'existent pas.
        """
        dir_name = os.path.dirname(self.file_path)
        if dir_name:
            try:
                os.makedirs(dir_name, exist_ok=True)
            except Exception as e:
                print(f"[SETTINGS ERROR] Impossible de créer le répertoire {dir_name} : {e}")
                return

        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[SETTINGS ERROR] Échec de la sauvegarde physique dans {self.file_path} : {e}")
