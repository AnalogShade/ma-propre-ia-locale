import os
import time

class FileManager:
    def __init__(self, max_chars=10000):
        self.loaded_files = {} # {path: {"content": str, "last_mod": float, "is_truncated": bool}}
        self.max_chars = max_chars # Limite pour éviter de saturer le contexte de l'IA

    def load_file(self, path):
        """Charge un fichier texte en mémoire."""
        if not os.path.exists(path):
            return False, "Le fichier n'existe pas."

        try:
            # Vérification de la taille pour avertir si besoin
            file_size = os.path.getsize(path)
            last_mod = os.path.getmtime(path)

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            is_truncated = False
            if len(content) > self.max_chars:
                content = content[:self.max_chars]
                is_truncated = True

            self.loaded_files[path] = {
                "content": content,
                "last_mod": last_mod,
                "is_truncated": is_truncated,
                "name": os.path.basename(path)
            }

            msg = f"Fichier '{os.path.basename(path)}' chargé."
            if is_truncated:
                msg += f" (Tronqué à {self.max_chars} caractères)"
            
            return True, msg

        except Exception as e:
            return False, f"Erreur de lecture : {str(e)}"

    def close_file(self, path):
        """Retire un fichier de la mémoire active."""
        # On essaie de trouver le fichier par son nom ou son chemin complet
        to_delete = None
        for p in self.loaded_files:
            if p == path or os.path.basename(p) == path:
                to_delete = p
                break
        
        if to_delete:
            del self.loaded_files[to_delete]
            return True, f"Fichier '{os.path.basename(to_delete)}' fermé."
        return False, "Fichier non trouvé dans la liste des fichiers ouverts."

    def list_files(self):
        """Retourne la liste des fichiers chargés."""
        if not self.loaded_files:
            return "Aucun fichier chargé."
        
        lines = ["Fichiers ouverts :"]
        for p, data in self.loaded_files.items():
            status = "(Tronqué)" if data["is_truncated"] else "(Complet)"
            lines.append(f"- {data['name']} {status} : {p}")
        return "\n".join(lines)

    def get_context_for_ai(self):
        """Prépare le bloc de texte à injecter dans le prompt système."""
        if not self.loaded_files:
            return ""

        context = "\n--- DOCUMENTS ACTUELLEMENT OUVERTS ---\n"
        for path, data in self.loaded_files.items():
            context += f"NOM DU FICHIER : {data['name']}\n"
            context += f"CONTENU :\n{data['content']}\n"
            if data["is_truncated"]:
                context += "... [CONTENU TRONQUÉ POUR LE CONTEXTE] ...\n"
            context += "---------------------------------------\n"
        context += "Tu peux utiliser ces documents pour répondre aux questions de l'utilisateur.\n"
        return context
