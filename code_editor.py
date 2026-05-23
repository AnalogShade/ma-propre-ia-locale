import os
from pathlib import Path

class CodeEditor:
    def __init__(self):
        """
        Initialise le gestionnaire d'édition et de création sécurisée de fichiers.
        """
        pass

    def parse_create_blocks(self, text):
        """
        Analyse le texte pour extraire les blocs de création de fichiers.
        Format attendu :
        FILE: nom_du_fichier.ext
        <<<<<<< CREATE
        contenu...
        >>>>>>> CREATE
        
        Retourne une liste de dictionnaires :
        [
            {
                "file_path": "nom_du_fichier.ext",
                "content": "contenu..."
            },
            ...
        ]
        """
        blocks = []
        if not text:
            return blocks
            
        lines = text.splitlines()
        current_file = None
        in_block = False
        block_content = []
        
        for line in lines:
            stripped = line.strip()
            
            # Détection de l'en-tête du fichier
            if stripped.startswith("FILE:"):
                # On nettoie le chemin (retrait des espaces, backticks, guillemets)
                current_file = stripped[5:].strip().strip('`"\'* ')
                continue
                
            # Détection du début du bloc de création
            if stripped.startswith("<<<<<<< CREATE"):
                if current_file:
                    in_block = True
                    block_content = []
                continue
                
            # Détection de la fin du bloc de création
            if stripped.startswith(">>>>>>> CREATE"):
                if in_block and current_file:
                    blocks.append({
                        "file_path": current_file,
                        "content": "\n".join(block_content)
                    })
                    in_block = False
                    current_file = None
                continue
                
            # Accumulation du contenu (on préserve les espaces de début de ligne d'origine)
            if in_block:
                block_content.append(line)
                
        return blocks

    def parse_search_replace_blocks(self, text):
        """
        Analyse le texte pour extraire les blocs de modification de fichiers.
        Format attendu :
        FILE: nom_du_fichier.ext
        <<<<<<< SEARCH
        code existant...
        =======
        nouveau code...
        >>>>>>> REPLACE
        
        Retourne une liste de dictionnaires :
        [
            {
                "file_path": "nom_du_fichier.ext",
                "search_content": "code existant...",
                "replace_content": "nouveau code..."
            },
            ...
        ]
        """
        blocks = []
        if not text:
            return blocks
            
        lines = text.splitlines()
        current_file = None
        state = "seeking"  # "seeking", "search", "replace"
        search_lines = []
        replace_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Détection de l'en-tête du fichier
            if state == "seeking" and stripped.startswith("FILE:"):
                current_file = stripped[5:].strip().strip('`"\'* ')
                continue
                
            # Détection du début du bloc SEARCH
            if stripped.startswith("<<<<<<< SEARCH"):
                if current_file:
                    state = "search"
                    search_lines = []
                    replace_lines = []
                continue
                
            # Détection de la séparation =======
            if state == "search" and stripped.startswith("======="):
                state = "replace"
                continue
                
            # Détection de la fin du bloc REPLACE
            if state == "replace" and stripped.startswith(">>>>>>> REPLACE"):
                if current_file:
                    blocks.append({
                        "file_path": current_file,
                        "search_content": "\n".join(search_lines),
                        "replace_content": "\n".join(replace_lines)
                    })
                state = "seeking"
                current_file = None
                continue
                
            # Accumulation du contenu selon l'état actuel (préservation des espaces)
            if state == "search":
                search_lines.append(line)
            elif state == "replace":
                replace_lines.append(line)
                
        return blocks

    def _create_backup(self, file_path):
        """
        Crée une copie de sauvegarde temporaire (.bak) du fichier ciblé.
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False
                
            backup_path = path.with_suffix(path.suffix + ".bak")
            import shutil
            shutil.copy2(path, backup_path)
            return True
        except Exception as e:
            print(f"  [DEBUG EDITOR] Erreur lors de la création de la sauvegarde pour {file_path} : {e}")
            return False

    def _restore_backup(self, file_path):
        """
        Restaure le fichier d'origine depuis sa sauvegarde (.bak) et supprime le fichier de sauvegarde.
        """
        try:
            path = Path(file_path)
            backup_path = path.with_suffix(path.suffix + ".bak")
            
            if not backup_path.exists():
                return False
                
            import shutil
            if path.exists():
                os.remove(path)
            shutil.move(backup_path, path)
            return True
        except Exception as e:
            print(f"  [DEBUG EDITOR] Erreur lors de la restauration de la sauvegarde pour {file_path} : {e}")
            return False

    def _delete_backup(self, file_path):
        """
        Supprime le fichier de sauvegarde (.bak) temporaire devenu inutile.
        """
        try:
            path = Path(file_path)
            backup_path = path.with_suffix(path.suffix + ".bak")
            if backup_path.exists():
                os.remove(backup_path)
                return True
            return False
        except Exception as e:
            print(f"  [DEBUG EDITOR] Erreur lors de la suppression de la sauvegarde pour {file_path} : {e}")
            return False

    def apply_edit(self, file_path, search_text, replace_text):
        """
        Applique une modification Search & Replace sécurisée sur le disque.
        Crée une sauvegarde .bak et effectue un rollback automatique en cas d'erreur.
        
        Retourne un tuple (success, message).
        """
        try:
            path = Path(file_path).resolve()
            if not path.exists():
                return False, f"Le fichier '{file_path}' n'existe pas."
                
            # Lire le contenu actuel
            with open(path, 'r', encoding='utf-8') as f:
                original_content = f.read()
                
            # Détection et normalisation des fins de ligne du fichier
            newline_char = "\n"
            if "\r\n" in original_content:
                newline_char = "\r\n"
                
            search_normalized = search_text.replace("\r\n", "\n").replace("\n", newline_char)
            replace_normalized = replace_text.replace("\r\n", "\n").replace("\n", newline_char)
            
            # Vérifier si le texte SEARCH est présent dans le fichier
            if search_normalized not in original_content:
                return False, "Le bloc de code à remplacer (SEARCH) n'a pas été trouvé exactement dans le fichier. Modification annulée."
                
            # Créer la sauvegarde de sécurité
            if not self._create_backup(path):
                return False, "Impossible de créer la sauvegarde de sécurité (.bak). Écriture annulée."
                
            try:
                # Effectuer le remplacement
                new_content = original_content.replace(search_normalized, replace_normalized)
                
                # Écrire sur le disque
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                    
                # Supprimer la sauvegarde temporaire devenue inutile
                self._delete_backup(path)
                return True, "La modification a été appliquée avec succès."
            except Exception as write_error:
                # Rollback en cas d'erreur d'écriture physique
                self._restore_backup(path)
                return False, f"Erreur d'écriture sur le disque : {write_error}. Le fichier original a été restauré."
                
        except Exception as e:
            return False, f"Une erreur inattendue est survenue : {e}"

    def create_file(self, file_path, content, working_dir=None):
        """
        Crée un nouveau fichier sur le disque après validation de sécurité du chemin.
        
        Retourne un tuple (success, message).
        """
        try:
            path = Path(file_path)
            
            # Résolution du chemin absolu
            if not path.is_absolute() and working_dir:
                resolved_path = (Path(working_dir) / path).resolve()
            else:
                resolved_path = path.resolve()
                
            # Vérification de sécurité : interdire l'écriture hors du working_dir
            if working_dir:
                working_dir_path = Path(working_dir).resolve()
                try:
                    # Sur Python >= 3.9, is_relative_to est parfait
                    if not resolved_path.is_relative_to(working_dir_path):
                        return False, "Accès refusé : Impossible de créer un fichier en dehors du répertoire de travail."
                except AttributeError:
                    # Rétrocompatibilité Python < 3.9
                    try:
                        resolved_path.relative_to(working_dir_path)
                    except ValueError:
                        return False, "Accès refusé : Impossible de créer un fichier en dehors du répertoire de travail."
            
            # Vérifier si le dossier parent existe, sinon le créer
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Écrire le fichier
            with open(resolved_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return True, f"Le fichier '{resolved_path.name}' a été créé avec succès."
            
        except Exception as e:
            return False, f"Erreur lors de la création du fichier : {e}"
