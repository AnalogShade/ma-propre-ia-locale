from pathlib import Path
import os
import time
import shutil

class FileManager:
    def __init__(self, max_mb=2.0):
        self.loaded_files = {} # {path: {"content": str, "content_with_lines": str, ...}}
        self.max_mb = max_mb 
        self.working_dir = None # Path object
        
        # État système strict
        self.current_file_path = None
        self.current_file_content = None
        self.current_file_numbered_content = None
        self.last_file_load_success = False
        self.last_file_error = None

    def set_working_dir(self, path):
        """Définit le répertoire de travail courant."""
        try:
            abs_path = Path(path).resolve()
            if not abs_path.exists() or not abs_path.is_dir():
                msg = f"Le répertoire '{path}' n'existe pas ou n'est pas un dossier."
                print(f"  [DEBUG FILE_MANAGER] Échec set_working_dir : {msg}")
                return False, msg
            
            self.working_dir = abs_path
            print(f"  [DEBUG FILE_MANAGER] working_dir défini : {abs_path}")
            return True, f"Répertoire de travail défini sur : {abs_path}"
        except Exception as e:
            return False, f"Erreur lors de la définition du répertoire : {str(e)}"

    def _resolve_path(self, file_path):
        """Résout un chemin de fichier de manière sécurisée."""
        path = Path(file_path)
        
        if not path.is_absolute() and self.working_dir:
            resolved_path = (self.working_dir / path).resolve()
        else:
            resolved_path = path.resolve()

        if self.working_dir:
            if not resolved_path.is_relative_to(self.working_dir):
                raise ValueError(f"Accès refusé : le fichier '{file_path}' est hors du répertoire de travail.")
        
        return resolved_path

    def add_line_numbers(self, content):
        """Ajoute des numéros de lignes au contenu."""
        lines = content.splitlines()
        numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
        return "\n".join(numbered_lines)

    def load_file(self, path_str):
        """Charge un fichier texte et le définit comme fichier actif."""
        print(f"  [DEBUG FILE_MANAGER] tentative ouverture : {path_str}")
        try:
            abs_path = self._resolve_path(path_str)
            print(f"  [DEBUG FILE_MANAGER] chemin résolu : {abs_path}")
            
            if not abs_path.exists():
                self._reset_current_file(f"Le fichier '{path_str}' n'existe pas.")
                return False, self.last_file_error

            file_size_mb = abs_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_mb:
                self._reset_current_file(f"Fichier trop volumineux ({file_size_mb:.2f} Mo).")
                return False, self.last_file_error

            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Mise à jour de l'état
            self.loaded_files.clear()
            self.current_file_path = str(abs_path)
            self.current_file_content = content
            self.current_file_numbered_content = self.add_line_numbers(content)
            self.last_file_load_success = True
            self.last_file_error = None
            
            self.loaded_files[self.current_file_path] = {
                "content": self.current_file_content,
                "content_with_lines": self.current_file_numbered_content,
                "name": abs_path.name
            }

            print(f"  [DEBUG FILE_MANAGER] succès : True")
            print(f"  [DEBUG FILE_MANAGER] current_file_path : {self.current_file_path}")
            return True, f"Fichier '{abs_path.name}' chargé."

        except ValueError as ve:
            self._reset_current_file(str(ve))
            return False, str(ve)
        except Exception as e:
            self._reset_current_file(f"Erreur de lecture : {str(e)}")
            return False, self.last_file_error

    def _reset_current_file(self, error_msg):
        """Réinitialise l'état du fichier actif en cas d'erreur ou fermeture."""
        self.loaded_files.clear()
        self.current_file_path = None
        self.current_file_content = None
        self.current_file_numbered_content = None
        self.last_file_load_success = False
        self.last_file_error = error_msg
        print(f"  [DEBUG FILE_MANAGER] succès : False")
        print(f"  [DEBUG FILE_MANAGER] erreur : {error_msg}")

    def close_file(self, path_str):
        """Retire un fichier de la mémoire active."""
        self._reset_current_file(None)
        return True, "Fichier fermé."

    def get_status_summary(self):
        """Retourne un bloc d'état structuré pour le prompt de l'IA."""
        status = "\n[ÉTAT SYSTÈME]\n"
        status += f"working_dir: {self.working_dir if self.working_dir else 'Aucun'}\n"
        status += f"current_file_path: {self.current_file_path if self.current_file_path else 'Aucun'}\n"
        status += f"file_loaded: {self.last_file_load_success}\n"
        status += f"last_file_error: {self.last_file_error if self.last_file_error else 'Aucun'}\n"
        status += "[/ÉTAT SYSTÈME]\n"
        return status

    def list_files(self):
        if not self.loaded_files:
            return "Aucun fichier chargé."
        return f"Fichier ouvert : {self.current_file_path}"

    def get_context_for_ai(self):
        """Prépare le bloc de texte à injecter dans le prompt système."""
        # On inclut toujours l'état système
        context = self.get_status_summary()
        
        if self.last_file_load_success and self.current_file_numbered_content:
            context += "\n--- CONTENU DU DOCUMENT ACTIF ---\n"
            context += f"FICHIER : {Path(self.current_file_path).name}\n"
            context += f"CONTENU :\n{self.current_file_numbered_content}\n"
            context += "---------------------------------\n"
        
        return context

    def apply_modification(self, mod):
        """Applique une modification structurée à un fichier."""
        try:
            file_path = mod.get("file")
            action = mod.get("action")
            reason = mod.get("reason", "Aucune raison fournie")

            if not file_path or not action:
                return False, "Format de modification invalide."

            abs_path = self._resolve_path(file_path)
            if not abs_path.exists():
                return False, f"Le fichier '{file_path}' n'existe pas."

            with open(abs_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            original_content = "".join(lines)
            new_lines = list(lines)
            summary = ""

            if action == "replace_lines":
                start, end, new_content = mod.get("start_line"), mod.get("end_line"), mod.get("new_content")
                if start is None or end is None or new_content is None:
                    return False, "Paramètres manquants."
                if start < 1 or end > len(lines) or start > end:
                    return False, f"Lignes invalides (Total: {len(lines)})."
                new_content_lines = new_content.splitlines(keepends=True)
                if new_content and not new_content.endswith('\n'): new_content_lines[-1] += '\n'
                new_lines[start-1:end] = new_content_lines
                summary = f"Remplacement des lignes {start} à {end}."

            elif action == "replace_text":
                target, new = mod.get("target_text"), mod.get("new_text")
                if target is None or new is None: return False, "Paramètres manquants."
                count = original_content.count(target)
                if count != 1: return False, f"Texte trouvé {count} fois (doit être unique)."
                new_content = original_content.replace(target, new)
                new_lines = new_content.splitlines(keepends=True)
                summary = "Remplacement de texte unique."

            elif action == "insert_after_line":
                line_num, new_content = mod.get("line"), mod.get("new_content")
                if line_num is None or new_content is None: return False, "Paramètres manquants."
                new_content_lines = new_content.splitlines(keepends=True)
                if new_content and not new_content.endswith('\n'): new_content_lines[-1] += '\n'
                new_lines[line_num:line_num] = new_content_lines
                summary = f"Insertion après ligne {line_num}."

            elif action == "insert_before_line":
                line_num, new_content = mod.get("line"), mod.get("new_content")
                if line_num is None or new_content is None: return False, "Paramètres manquants."
                new_content_lines = new_content.splitlines(keepends=True)
                if new_content and not new_content.endswith('\n'): new_content_lines[-1] += '\n'
                new_lines[line_num-1:line_num-1] = new_content_lines
                summary = f"Insertion avant ligne {line_num}."
            else:
                return False, f"Action inconnue : {action}"

            # Backup
            backup_path = abs_path.with_suffix(abs_path.suffix + ".bak")
            shutil.copy2(abs_path, backup_path)

            # Écriture
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            self.load_file(str(abs_path))
            return True, {"success": True, "file": str(abs_path), "action": action, "summary": summary, "backup": str(backup_path), "reason": reason}

        except Exception as e:
            return False, f"Erreur lors de l'application : {str(e)}"
