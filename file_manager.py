from pathlib import Path
import os
import time
import shutil

class FileManager:
    def __init__(self, max_mb=2.0):
        self.loaded_files = {} 
        self.max_mb = max_mb 
        self.working_dir = None 
        
        # État système strict
        self.current_file_path = None
        self.current_file_content = None
        self.current_file_numbered_content = None
        self.last_file_load_success = False
        self.last_file_error = None

    def set_working_dir(self, path):
        try:
            abs_path = Path(path).resolve()
            if not abs_path.exists() or not abs_path.is_dir():
                msg = f"Le répertoire '{path}' n'existe pas ou n'est pas un dossier."
                self.working_dir = None # On reset si le chemin est invalide
                print(f"  [DEBUG FILE_MANAGER] Échec set_working_dir : {msg}")
                return False, msg
            
            self.working_dir = abs_path
            print(f"  [DEBUG FILE_MANAGER] working_dir défini : {self.working_dir}")
            return True, f"Répertoire de travail défini sur : {self.working_dir}"
        except Exception as e:
            return False, f"Erreur : {str(e)}"

    def _resolve_path(self, file_path):
        path = Path(file_path)
        if not path.is_absolute() and self.working_dir:
            resolved_path = (self.working_dir / path).resolve()
        else:
            resolved_path = path.resolve()

        if self.working_dir:
            if not resolved_path.is_relative_to(self.working_dir):
                raise ValueError(f"Accès refusé : hors du répertoire de travail.")
        
        return resolved_path

    def load_file(self, path_str, user_input=None):
        print(f"  [DEBUG FILE_MANAGER] tentative ouverture : {path_str}")
        
        # R\u00e9solution intelligente si un message utilisateur est fourni
        if user_input:
            success, resolution = self.resolve_file_reference(path_str, user_input)
            if success:
                path_str = resolution # On utilise le nom r\u00e9solu
            else:
                if isinstance(resolution, list):
                    files_str = ", ".join(resolution)
                    if not path_str or str(path_str).strip().lower() in ["null", "none", ""]:
                        msg = f"Voici les fichiers disponibles. Lequel veux-tu ouvrir ? ({files_str})"
                    else:
                        msg = f"Je n'ai pas trouv\u00e9 '{path_str}'. Voici les fichiers disponibles : ({files_str})"
                else:
                    msg = resolution
                self._reset_current_file(msg)
                return False, msg

        print(f"  [DEBUG FILE_MANAGER] working_dir actuel : {self.working_dir}")
        try:
            abs_path = self._resolve_path(path_str)
            print(f"  [DEBUG FILE_MANAGER] chemin résolu : {abs_path}")
            
            if not abs_path.exists():
                self._reset_current_file(f"Le fichier '{path_str}' n'existe pas.")
                return False, self.last_file_error

            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.loaded_files.clear()
            self.current_file_path = str(abs_path)
            self.current_file_content = content
            self.current_file_numbered_content = self._add_line_numbers(content)
            self.last_file_load_success = True
            self.last_file_error = None
            
            print(f"  [DEBUG FILE_MANAGER] succès : True")
            return True, f"Fichier chargé."

        except Exception as e:
            self._reset_current_file(str(e))
            return False, str(e)

    def _add_line_numbers(self, content):
        lines = content.splitlines()
        return "\n".join([f"{i+1}: {line}" for i, line in enumerate(lines)])

    def _reset_current_file(self, error_msg):
        self.loaded_files.clear()
        self.current_file_path = None
        self.current_file_content = None
        self.current_file_numbered_content = None
        self.last_file_load_success = False
        self.last_file_error = error_msg
        print(f"  [DEBUG FILE_MANAGER] succès : False")
        print(f"  [DEBUG FILE_MANAGER] état reset : current_file_path=None")

    def get_status_summary(self):
        status_lines = []
        if self.working_dir:
            status_lines.append(f"R\u00e9pertoire actif: {self.working_dir}")
            
            # Injection de la liste des fichiers disponibles pour l'IA
            files = self.get_available_files()
            if files:
                status_lines.append(f"Fichiers disponibles: {', '.join(files)}")
            else:
                status_lines.append("Fichiers disponibles: Aucun")

        if self.current_file_path:
            status_lines.append(f"Fichier actif: {self.current_file_path}")
        
        if self.last_file_error and (self.working_dir or self.current_file_path):
            status_lines.append(f"Erreur r\u00e9cente: {self.last_file_error}")
            
        if not status_lines:
            return ""

        status = "\n[ÉTAT SYSTÈME]\n"
        status += "\n".join(status_lines) + "\n"
        status += "[/ÉTAT SYSTÈME]\n"
        return status

    def get_context_for_ai(self):
        if not self.working_dir and not self.current_file_path and not self.last_file_load_success:
            return ""

        context = self.get_status_summary()
        if self.last_file_load_success:
            context += f"\n--- CONTENU DE {Path(self.current_file_path).name} ---\n"
            context += self.current_file_numbered_content + "\n"
        return context

    def close_file(self, path_str=None):
        """Ferme le fichier actif ou le fichier sp\u00e9cifi\u00e9."""
        if not self.current_file_path:
            return False, "Aucun fichier n'est actuellement ouvert."
        
        # On pourrait v\u00e9rifier si path_str correspond, mais pour l'instant
        # on ferme simplement le fichier actif puisque c'est un agent mono-fichier.
        old_name = Path(self.current_file_path).name
        self._reset_current_file(None)
        return True, f"Fichier '{old_name}' ferm\u00e9."

    def list_files(self):
        if self.current_file_path:
            return f"Ouvert : {self.current_file_path}"
        
        files = self.get_available_files()
        if files:
            return f"Fichiers disponibles : {', '.join(files)}"
        return "Aucun fichier dans le r\u00e9pertoire."

    def get_available_files(self):
        """Liste les fichiers r\u00e9els du premier niveau dans le working_dir."""
        if not self.working_dir or not Path(self.working_dir).exists():
            return []
        
        try:
            # On ne prend que les fichiers (pas de dossiers) et on ignore les fichiers cach\u00e9s
            files = [f.name for f in Path(self.working_dir).iterdir() if f.is_file() and not f.name.startswith('.')]
            return sorted(files)
        except Exception as e:
            print(f"  [DEBUG FILE_MANAGER] Erreur list_files : {e}")
            return []

    def resolve_file_reference(self, raw_target, user_input):
        """
        Tente de r\u00e9soudre quel fichier l'utilisateur veut ouvrir sans nettoyage hard-cod\u00e9.
        Se base sur la r\u00e9alit\u00e9 du working_dir.
        """
        available_files = self.get_available_files()
        if not available_files:
            return False, "Aucun fichier disponible dans le r\u00e9pertoire actuel."

        # 1. Requ\u00eate g\u00e9n\u00e9rique (path_raw == None ou string vide)
        if not raw_target or str(raw_target).strip().lower() in ["null", "none", ""]:
            return False, available_files # D\u00e9clenche la liste de choix

        user_input_lower = user_input.lower()
        clean_target = str(raw_target).strip('"\'')
        
        # 2. Match Exact sur raw_target
        if clean_target in available_files:
            return True, clean_target
        
        # 3. Recherche par inclusion des noms de fichiers r\u00e9els dans le message utilisateur
        found_files = []
        for f in sorted(available_files, key=len, reverse=True):
            if f.lower() in user_input_lower:
                found_files.append(f)
        
        if len(found_files) == 1:
            return True, found_files[0]
        
        if len(found_files) > 1:
            return False, found_files # Ambigu\u00eft\u00e9

        # 4. Aucun fichier r\u00e9el trouv\u00e9
        return False, available_files
