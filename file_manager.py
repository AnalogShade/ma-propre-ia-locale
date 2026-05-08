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

    def load_file(self, path_str):
        print(f"  [DEBUG FILE_MANAGER] tentative ouverture : {path_str}")
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
        status = "\n[ÉTAT SYSTÈME]\n"
        status += f"working_dir: {self.working_dir if self.working_dir else 'Aucun'}\n"
        status += f"current_file_path: {self.current_file_path if self.current_file_path else 'Aucun'}\n"
        status += f"file_loaded: {self.last_file_load_success}\n"
        status += f"last_file_error: {self.last_file_error if self.last_file_error else 'Aucun'}\n"
        status += "[/ÉTAT SYSTÈME]\n"
        return status

    def get_context_for_ai(self):
        context = self.get_status_summary()
        if self.last_file_load_success:
            context += f"\n--- CONTENU DE {Path(self.current_file_path).name} ---\n"
            context += self.current_file_numbered_content + "\n"
        return context

    def list_files(self):
        return f"Ouvert : {self.current_file_path}" if self.current_file_path else "Aucun fichier."
