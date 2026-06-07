import os
import uuid
from PIL import Image

class Attachment:
    """
    Classe de base abstraite représentant une pièce jointe temporaire dans Anna.
    Conçue pour être étendue à d'autres types à l'avenir (PDF, Audio, etc.).
    """
    def __init__(self, id_=None):
        self.id = id_ or str(uuid.uuid4())
        
    def get_type(self) -> str:
        """Retourne le type de la pièce jointe (ex: 'image', 'pdf', 'audio')."""
        raise NotImplementedError
        
    def get_display_name(self) -> str:
        """Retourne un nom d'affichage convivial pour l'interface graphique."""
        raise NotImplementedError
        
    def clean(self):
        """Nettoie les ressources physiques (fichiers temporaires) associées."""
        pass


class ImageAttachment(Attachment):
    """
    Pièce jointe de type Image, contenant une image PIL issue du presse-papiers ou d'un fichier.
    """
    def __init__(self, image: Image.Image, file_path: str = None, id_=None):
        super().__init__(id_)
        self.image = image
        self.file_path = file_path # Chemin original si chargé depuis un fichier
        self.temp_path = None      # Chemin temporaire créé pour Ollama

    def get_type(self) -> str:
        return "image"

    def get_display_name(self) -> str:
        if self.file_path:
            return os.path.basename(self.file_path)
        return f"Image_presse_papiers_{self.id[:8]}.png"

    def prepare_for_api(self, target_dir: str) -> str:
        """
        Sauvegarde temporairement l'image dans target_dir sous forme de fichier PNG 
        pour qu'elle puisse être transmise à l'API Ollama via un chemin absolu.
        """
        if self.temp_path and os.path.exists(self.temp_path):
            return self.temp_path

        os.makedirs(target_dir, exist_ok=True)
        self.temp_path = os.path.abspath(os.path.join(target_dir, f"temp_{self.id}.png"))
        
        # Sauvegarder l'image PIL en PNG
        self.image.save(self.temp_path, "PNG")
        return self.temp_path

    def clean(self):
        """
        Supprime le fichier temporaire du disque s'il existe.
        """
        if self.temp_path and os.path.exists(self.temp_path):
            try:
                os.remove(self.temp_path)
            except Exception as e:
                print(f"[ATTACHMENT WARNING] Impossible de supprimer le fichier temporaire {self.temp_path} : {e}")
            self.temp_path = None
