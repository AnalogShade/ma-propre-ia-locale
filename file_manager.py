from pathlib import Path
import os
import time
import shutil

class FileManager:
    def __init__(self, max_mb=2.0):
        self.loaded_files = {} 
        self.max_mb = max_mb 
        self.working_dir = None 
        
        # Limitations de contexte pour l'IA
        self.max_file_chars = 12000
        self.max_global_chars = 35000
        
        # État système strict (compatibilité mono-fichier)
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
        if not self.working_dir:
            raise ValueError("Aucun répertoire de travail défini.")
            
        path = Path(file_path)
        if not path.is_absolute():
            resolved_path = (self.working_dir / path).resolve()
        else:
            resolved_path = path.resolve()

        working_dir_path = Path(self.working_dir).resolve()
        
        # Vérification stricte de la sécurité des chemins
        try:
            if not resolved_path.is_relative_to(working_dir_path):
                raise PermissionError("Accès refusé : hors du répertoire de travail.")
        except AttributeError:
            # Rétrocompatibilité Python < 3.9
            try:
                resolved_path.relative_to(working_dir_path)
            except ValueError:
                raise PermissionError("Accès refusé : hors du répertoire de travail.")
        
        return resolved_path

    def load_file(self, path_str, user_input=None):
        print(f"  [DEBUG FILE_MANAGER] tentative ouverture : {path_str}")
        
        # Résolution intelligente si un message utilisateur est fourni
        if user_input:
            success, resolution = self.resolve_file_reference(path_str, user_input)
            if success:
                path_str = resolution # On utilise le nom résolu
            else:
                if isinstance(resolution, list):
                    files_str = ", ".join(resolution)
                    if not path_str or str(path_str).strip().lower() in ["null", "none", ""]:
                        msg = f"Voici les fichiers disponibles. Lequel veux-tu ouvrir ? ({files_str})"
                    else:
                        msg = f"Je n'ai pas trouvé '{path_str}'. Voici les fichiers disponibles : ({files_str})"
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

            # Sécurité 1: Vérification de la taille maximale (2 Mo)
            file_size_mb = abs_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_mb:
                err_msg = f"Le fichier '{path_str}' dépasse la taille maximale autorisée ({self.max_mb} Mo)."
                self._reset_current_file(err_msg)
                return False, err_msg

            # Sécurité 2: Limite globale du nombre de fichiers (max 5)
            rel_path_str = str(abs_path.relative_to(self.working_dir.resolve())).replace('\\', '/')
            if rel_path_str not in self.loaded_files and len(self.loaded_files) >= 5:
                err_msg = "Le nombre maximum de fichiers chargés (5) a été atteint. Ferme un fichier avant d'en ouvrir un nouveau."
                self.last_file_error = err_msg
                return False, err_msg

            # Lire le contenu
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Ajouter au multi-fichiers
            self.loaded_files[rel_path_str] = {
                "content": content,
                "numbered": self._add_line_numbers(content)
            }

            # Mettre à jour les attributs de compatibilité mono-fichier
            self.current_file_path = str(abs_path)
            self.current_file_content = content
            self.current_file_numbered_content = self.loaded_files[rel_path_str]["numbered"]
            self.last_file_load_success = True
            self.last_file_error = None
            
            filename = abs_path.name
            num_lines = len(content.splitlines())
            msg = (
                f"Fichier chargé : {filename}\n"
                f"Nombre de lignes : {num_lines}"
            )
            
            print(f"  [DEBUG FILE_MANAGER] succès : True")
            return True, msg

        except PermissionError as pe:
            err_msg = str(pe)
            self._reset_current_file(err_msg)
            return False, err_msg
        except Exception as e:
            err_msg = f"Erreur : {str(e)}"
            self._reset_current_file(err_msg)
            return False, err_msg

    def _add_line_numbers(self, content):
        lines = content.splitlines()
        return "\n".join([f"{i+1}: {line}" for i, line in enumerate(lines)])

    def _reset_current_file(self, error_msg):
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
            status_lines.append(f"Répertoire actif: {self.working_dir}")
            
            # Injection de la liste des fichiers disponibles pour l'IA
            files = self.get_available_files()
            if files:
                status_lines.append(f"Fichiers disponibles: {', '.join(files)}")
            else:
                status_lines.append("Fichiers disponibles: Aucun")

        if self.loaded_files:
            loaded_names = list(self.loaded_files.keys())
            status_lines.append(f"Fichiers ouverts: {', '.join(loaded_names)}")

        if self.current_file_path:
            status_lines.append(f"Fichier actif: {self.current_file_path}")
        
        if self.last_file_error and (self.working_dir or self.current_file_path):
            status_lines.append(f"Erreur récente: {self.last_file_error}")
            
        if not status_lines:
            return ""

        status = "\n[ÉTAT SYSTÈME]\n"
        status += "\n".join(status_lines) + "\n"
        status += "[/ÉTAT SYSTÈME]\n"
        return status

    def get_context_for_ai(self, numbered=True):
        if not self.working_dir and not self.loaded_files:
            return ""

        context = self.get_status_summary()
        
        if not self.loaded_files:
            return context

        combined_files_context = ""
        
        # Concaténer le contenu de chaque fichier chargé en appliquant les limites de caractères
        for rel_path, file_data in self.loaded_files.items():
            content_to_use = file_data["numbered"] if numbered else file_data["content"]
            file_header = f"\n--- CONTENU DE {rel_path} ---\n"
            file_footer = "\n"
            
            # Vérifier la limite par fichier
            if len(content_to_use) > self.max_file_chars:
                truncated_content = content_to_use[:self.max_file_chars]
                # S'assurer de couper proprement sur un saut de ligne
                last_newline = truncated_content.rfind("\n")
                if last_newline != -1:
                    truncated_content = truncated_content[:last_newline]
                content_to_use = truncated_content + "\n[... TRONQUÉ : Ce fichier dépasse la limite autorisée par fichier ...]"
                
            file_entry = file_header + content_to_use + file_footer
            
            # Vérifier la limite globale
            if len(combined_files_context) + len(file_entry) > self.max_global_chars:
                remaining_chars = self.max_global_chars - len(combined_files_context)
                if remaining_chars > 100:
                    truncated_entry = file_entry[:remaining_chars]
                    last_newline = truncated_entry.rfind("\n")
                    if last_newline != -1:
                        truncated_entry = truncated_entry[:last_newline]
                    combined_files_context += truncated_entry + "\n[... TRONQUÉ GLOBALEMENT : Le contexte total dépasse la limite globale ...]\n"
                else:
                    combined_files_context += "\n[... TRONQUÉ GLOBALEMENT : Le contexte total dépasse la limite globale ...]\n"
                break
            else:
                combined_files_context += file_entry
                
        context += combined_files_context
        return context

    def close_file(self, path_str=None):
        """Ferme le fichier spécifié ou le fichier actif de compatibilité mono-fichier."""
        if not path_str:
            if self.current_file_path:
                path_str = self.current_file_path
            else:
                return False, "Aucun fichier n'est actuellement ouvert."
        
        try:
            abs_path = self._resolve_path(path_str)
            rel_path_str = str(abs_path.relative_to(self.working_dir.resolve())).replace('\\', '/')
        except Exception:
            # Fallback en cas d'erreur de résolution
            rel_path_str = str(path_str).replace('\\', '/')
            abs_path = Path(path_str)

        if rel_path_str not in self.loaded_files:
            return False, f"Le fichier '{path_str}' n'est pas chargé."

        old_name = Path(rel_path_str).name
        del self.loaded_files[rel_path_str]
        
        # Mettre à jour l'état de compatibilité mono-fichier
        # Si le fichier fermé était le fichier actif, on bascule vers le dernier encore chargé
        if self.current_file_path and str(Path(self.current_file_path).resolve()) == str(abs_path.resolve()):
            if self.loaded_files:
                last_rel_path = list(self.loaded_files.keys())[-1]
                try:
                    last_abs_path = self._resolve_path(last_rel_path)
                except Exception:
                    last_abs_path = Path(self.working_dir) / last_rel_path
                
                self.current_file_path = str(last_abs_path)
                self.current_file_content = self.loaded_files[last_rel_path]["content"]
                self.current_file_numbered_content = self.loaded_files[last_rel_path]["numbered"]
                self.last_file_load_success = True
                self.last_file_error = None
            else:
                self._reset_current_file(None)
                
        return True, f"Fichier '{old_name}' fermé."

    def close_all_files(self):
        """Ferme tous les fichiers chargés en contexte."""
        self.loaded_files.clear()
        self._reset_current_file(None)
        return True, "Tous les fichiers ont été fermés."

    def close_working_dir(self):
        """Ferme le répertoire de travail courant et réinitialise l'état associé."""
        old_dir = self.working_dir
        self.working_dir = None
        self.loaded_files.clear()
        self._reset_current_file(None)
        if old_dir:
            return True, f"Répertoire de travail '{old_dir}' fermé."
        return True, "Répertoire de travail fermé."


    def list_files(self):
        if self.loaded_files:
            loaded_names = list(self.loaded_files.keys())
            return f"Fichiers ouverts : {', '.join(loaded_names)}"
        
        files = self.get_available_files()
        if files:
            return f"Fichiers disponibles : {', '.join(files)}"
        return "Aucun fichier dans le répertoire."

    def get_available_files(self):
        """Liste tous les fichiers réels de tous les niveaux dans le working_dir (récursif)."""
        if not self.working_dir or not Path(self.working_dir).exists():
            return []
        
        ignored_dirs = {'.git', '__pycache__', 'venv', 'node_modules', 'avatar', 'avatars', '.gemini'}
        ignored_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pyc', '.bak', '.exe', '.bin'}
        
        files_list = []
        try:
            working_dir_path = Path(self.working_dir).resolve()
            for root, dirs, files in os.walk(working_dir_path):
                # Filtrer les dossiers indésirables en place pour que os.walk ne s'y aventure pas
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
                
                for file in files:
                    if file.startswith('.'):
                        continue
                    ext = Path(file).suffix.lower()
                    if ext in ignored_extensions:
                        continue
                    
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(working_dir_path)
                    files_list.append(str(rel_path).replace('\\', '/'))
            return sorted(files_list)
        except Exception as e:
            print(f"  [DEBUG FILE_MANAGER] Erreur get_available_files : {e}")
            return []

    def search_text(self, query):
        """Effectue une recherche textuelle (grep) limitée et sécurisée dans le répertoire de travail."""
        if not self.working_dir or not Path(self.working_dir).exists():
            return False, "Aucun répertoire de travail défini.", False
        
        if not query:
            return False, "Requête de recherche vide.", False

        available_files = self.get_available_files()
        results = []
        truncated = False
        total_matches = 0

        working_dir_path = Path(self.working_dir).resolve()

        for rel_path in available_files:
            if total_matches >= 50:
                truncated = True
                break
                
            abs_path = working_dir_path / rel_path
            try:
                # errors='ignore' permet de lire sans planter sur les caractères non-UTF-8
                with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
            except Exception:
                continue

            file_matches = 0
            for i, line in enumerate(lines):
                if query.lower() in line.lower():
                    if file_matches >= 5:
                        truncated = True
                        break # Déjà 5 correspondances pour ce fichier, on s'arrête
                    
                    results.append({
                        "file": rel_path,
                        "line_num": i + 1,
                        "content": line.strip()
                    })
                    file_matches += 1
                    total_matches += 1
                    
                    if total_matches >= 50:
                        truncated = True
                        break
            
            if total_matches >= 50:
                break

        return True, results, truncated

    def resolve_file_reference(self, raw_target, user_input):
        """
        Tente de résoudre quel fichier l'utilisateur veut ouvrir.
        Se base sur la réalité du working_dir récursif.
        """
        available_files = self.get_available_files()
        if not available_files:
            return False, "Aucun fichier disponible dans le répertoire actuel."

        # 1. Requête générique (path_raw == None ou string vide)
        if not raw_target or str(raw_target).strip().lower() in ["null", "none", ""]:
            return False, available_files

        user_input_lower = user_input.lower()
        clean_target = str(raw_target).strip('"\'').replace('\\', '/')
        
        # 2. Match Exact sur raw_target
        if clean_target in available_files:
            return True, clean_target
        
        # Match sur le nom du fichier seul (sans le chemin)
        for f in available_files:
            if Path(f).name == clean_target:
                return True, f
        
        # 3. Recherche par inclusion des noms de fichiers réels dans le message utilisateur
        found_files = []
        for f in sorted(available_files, key=lambda x: len(Path(x).name), reverse=True):
            fname = Path(f).name.lower()
            if fname in user_input_lower:
                found_files.append(f)
        
        if len(found_files) == 1:
            return True, found_files[0]
        
        if len(found_files) > 1:
            return False, found_files # Ambiguïté

        # 4. Aucun fichier réel trouvé
        return False, available_files
