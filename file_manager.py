from pathlib import Path
import os
import time
import shutil

class FileManager:
    def __init__(self, max_mb=2.0):
        self.loaded_files = {} # {path: {"content": str, "content_with_lines": str, "last_mod": float, "is_truncated": bool}}
        self.max_mb = max_mb 
        self.current_file_path = None # Chemin absolu du fichier actif (sous forme de chaîne)
        self.working_dir = None # Path object pour le répertoire de travail

    def set_working_dir(self, path):
        """Définit le répertoire de travail courant."""
        abs_path = Path(path).resolve()
        if not abs_path.exists() or not abs_path.is_dir():
            return False, f"Le répertoire '{path}' n'existe pas ou n'est pas un dossier."
        
        self.working_dir = abs_path
        return True, f"Répertoire de travail défini sur : {abs_path}"

    def _resolve_path(self, file_path):
        """Résout un chemin de fichier de manière sécurisée."""
        path = Path(file_path)
        
        # Si le chemin est relatif et qu'on a un working_dir, on le résout par rapport à lui
        if not path.is_absolute() and self.working_dir:
            resolved_path = (self.working_dir / path).resolve()
        else:
            resolved_path = path.resolve()

        # Sécurité : vérifier que le chemin est dans le working_dir (si défini)
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
        try:
            abs_path = self._resolve_path(path_str)
            
            if not abs_path.exists():
                return False, f"Le fichier '{path_str}' n'existe pas."

            # Vérification de la taille (en Mo)
            file_size_mb = abs_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_mb:
                return False, f"Le fichier est trop volumineux ({file_size_mb:.2f} Mo). Limite : {self.max_mb} Mo."

            last_mod = abs_path.stat().st_mtime

            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Pour la v1, on limite à un seul fichier actif
            self.loaded_files.clear()
            
            self.loaded_files[str(abs_path)] = {
                "content": content,
                "content_with_lines": self.add_line_numbers(content),
                "last_mod": last_mod,
                "name": abs_path.name
            }
            self.current_file_path = str(abs_path)

            return True, f"Fichier '{abs_path.name}' chargé ({len(content)} caractères)."

        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Erreur de lecture : {str(e)}"

    def close_file(self, path_str):
        """Retire un fichier de la mémoire active."""
        try:
            abs_path = self._resolve_path(path_str)
            path_key = str(abs_path)
            
            if path_key in self.loaded_files:
                del self.loaded_files[path_key]
                if self.current_file_path == path_key:
                    self.current_file_path = None
                return True, f"Fichier '{abs_path.name}' fermé."
            return False, "Fichier non trouvé dans les fichiers ouverts."
        except Exception:
            return False, "Erreur lors de la fermeture du fichier."

    def list_files(self):
        """Retourne la liste des fichiers chargés."""
        if not self.loaded_files:
            return "Aucun fichier chargé."
        
        lines = ["Fichiers ouverts :"]
        for p, data in self.loaded_files.items():
            lines.append(f"- {data['name']} : {p}")
        return "\n".join(lines)

    def get_context_for_ai(self):
        """Prépare le bloc de texte à injecter dans le prompt système."""
        if not self.loaded_files:
            return ""

        context = "\n--- DOCUMENT ACTIF (AVEC NUMÉROS DE LIGNES) ---\n"
        for path, data in self.loaded_files.items():
            context += f"FICHIER : {data['name']}\n"
            context += f"CHEMIN : {path}\n"
            context += f"CONTENU :\n{data['content_with_lines']}\n"
            context += "-----------------------------------------------\n"
        context += "Utilise les numéros de lignes pour proposer des modifications précises.\n"
        return context

    def apply_modification(self, mod):
        """
        Applique une modification structurée à un fichier.
        mod: dict contenant 'action', 'file', et les paramètres spécifiques.
        """
        try:
            file_path = mod.get("file")
            action = mod.get("action")
            reason = mod.get("reason", "Aucune raison fournie")

            if not file_path or not action:
                return False, "Format de modification invalide (champs manquants)."

            abs_path = self._resolve_path(file_path)
            if not abs_path.exists():
                return False, f"Le fichier '{file_path}' n'existe pas."

            # Lecture du contenu actuel
            with open(abs_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            original_content = "".join(lines)
            new_lines = list(lines)
            summary = ""

            if action == "replace_lines":
                start = mod.get("start_line")
                end = mod.get("end_line")
                new_content = mod.get("new_content")

                if start is None or end is None or new_content is None:
                    return False, "Paramètres manquants pour replace_lines."
                
                # Validation des lignes (1-indexed)
                if start < 1 or end > len(lines) or start > end:
                    return False, f"Numéros de lignes invalides : {start}-{end} (Total : {len(lines)} lines)."

                # Remplacement (start-1 pour 0-indexed, end est inclusif)
                new_content_lines = new_content.splitlines(keepends=True)
                # S'assurer que le nouveau contenu se termine par un saut de ligne si nécessaire
                if new_content and not new_content.endswith('\n'):
                    new_content_lines[-1] += '\n'
                
                new_lines[start-1:end] = new_content_lines
                summary = f"Remplacement des lignes {start} à {end}."

            elif action == "replace_text":
                target_text = mod.get("target_text")
                new_text = mod.get("new_text")

                if target_text is None or new_text is None:
                    return False, "Paramètres manquants pour replace_text."

                count = original_content.count(target_text)
                if count == 0:
                    return False, "Texte à remplacer introuvable."
                if count > 1:
                    return False, f"Texte trouvé {count} fois. Le remplacement doit être unique."

                new_content = original_content.replace(target_text, new_text)
                new_lines = new_content.splitlines(keepends=True)
                summary = "Remplacement d'un bloc de texte unique."

            elif action == "insert_after_line":
                line_num = mod.get("line")
                new_content = mod.get("new_content")

                if line_num is None or new_content is None:
                    return False, "Paramètres manquants pour insert_after_line."

                if line_num < 0 or line_num > len(lines):
                    return False, f"Numéro de ligne invalide : {line_num}."

                new_content_lines = new_content.splitlines(keepends=True)
                if new_content and not new_content.endswith('\n'):
                    new_content_lines[-1] += '\n'

                new_lines[line_num:line_num] = new_content_lines
                summary = f"Insertion après la ligne {line_num}."

            elif action == "insert_before_line":
                line_num = mod.get("line")
                new_content = mod.get("new_content")

                if line_num is None or new_content is None:
                    return False, "Paramètres manquants pour insert_before_line."

                if line_num < 1 or line_num > len(lines):
                    return False, f"Numéro de ligne invalide : {line_num}."

                new_content_lines = new_content.splitlines(keepends=True)
                if new_content and not new_content.endswith('\n'):
                    new_content_lines[-1] += '\n'

                new_lines[line_num-1:line_num-1] = new_content_lines
                summary = f"Insertion avant la ligne {line_num}."

            else:
                return False, f"Action inconnue : {action}"

            # Création du backup
            backup_path = abs_path.with_suffix(abs_path.suffix + ".bak")
            shutil.copy2(abs_path, backup_path)

            # Écriture du nouveau contenu
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            # Recharger le fichier dans la mémoire pour que l'IA ait la version à jour
            self.load_file(str(abs_path))

            result = {
                "success": True,
                "file": str(abs_path),
                "action": action,
                "summary": summary,
                "backup": str(backup_path),
                "reason": reason
            }
            return True, result

        except Exception as e:
            return False, f"Erreur lors de l'application : {str(e)}"
