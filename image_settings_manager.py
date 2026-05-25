import os
import json
from settings_manager import SettingsManager
from config import SETTINGS_FILE

class ImageSettingsManager:
    def __init__(self, settings_file=SETTINGS_FILE):
        """
        Initialise le gestionnaire de configuration pour la génération d'images.
        Reçoit le chemin du fichier settings pour la persistance des préférences.
        """
        self.settings_manager = SettingsManager(settings_file)
        self.init_defaults()

    def init_defaults(self):
        """
        Garantit que les paramètres par défaut pour Stable Diffusion sont présents.
        """
        if self.settings_manager.get_setting("sd_api_url") is None:
            self.settings_manager.set_setting("sd_api_url", "http://127.0.0.1:7860")
        
        if self.settings_manager.get_setting("sd_install_dir") is None:
            self.settings_manager.set_setting("sd_install_dir", "")
            
        if self.settings_manager.get_setting("sd_checkpoints_dir") is None:
            self.settings_manager.set_setting("sd_checkpoints_dir", "")
            
        if self.settings_manager.get_setting("sd_selected_checkpoint") is None:
            self.settings_manager.set_setting("sd_selected_checkpoint", "")

    # Getters
    @property
    def api_url(self):
        return self.settings_manager.get_setting("sd_api_url", "http://127.0.0.1:7860")

    @property
    def install_dir(self):
        return self.settings_manager.get_setting("sd_install_dir", "")

    @property
    def checkpoints_dir(self):
        return self.settings_manager.get_setting("sd_checkpoints_dir", "")

    @property
    def selected_checkpoint(self):
        return self.settings_manager.get_setting("sd_selected_checkpoint", "")

    # Setters
    def set_api_url(self, url):
        self.settings_manager.set_setting("sd_api_url", url.strip())

    def set_install_dir(self, path):
        self.settings_manager.set_setting("sd_install_dir", path.strip())
        # Si le dossier checkpoints n'est pas encore configuré et que le chemin install_dir est valide,
        # on peut tenter une auto-détection standard du dossier des modèles
        if path.strip() and not self.checkpoints_dir:
            potential_dir = os.path.join(path.strip(), "models", "Stable-diffusion")
            if os.path.exists(potential_dir):
                self.set_checkpoints_dir(potential_dir)

    def set_checkpoints_dir(self, path):
        self.settings_manager.set_setting("sd_checkpoints_dir", path.strip())

    def set_selected_checkpoint(self, checkpoint_name):
        self.settings_manager.set_setting("sd_selected_checkpoint", checkpoint_name.strip())

    def scan_checkpoints(self):
        """
        Scanne le dossier physique configuré pour lister les checkpoints disponibles.
        Si aucun dossier n'est configuré ou valide, retourne une liste de repli simulée.
        """
        checkpoints_path = self.checkpoints_dir
        
        # Validation physique du chemin
        if checkpoints_path and os.path.exists(checkpoints_path) and os.path.isdir(checkpoints_path):
            try:
                files = os.listdir(checkpoints_path)
                valid_extensions = ('.safetensors', '.ckpt')
                checkpoints = [f for f in files if f.lower().endswith(valid_extensions)]
                checkpoints.sort()
                
                # Si le dossier est valide mais vide, on ajoute quand même une simulation ou une liste vide
                if checkpoints:
                    return checkpoints
            except Exception as e:
                print(f"[IMAGE SETTINGS WARNING] Impossible de scanner le dossier local : {e}")

        # Liste de repli (fallback simulation / V0)
        return [
            "v1-5-pruned-emaonly.safetensors",
            "sd_xl_base_1.0.safetensors",
            "dreamshaper_8.safetensors",
            "realisticVisionV51.safetensors"
        ]
