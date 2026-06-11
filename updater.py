import os
import sys
import time
import shutil
import zipfile
import tempfile
import datetime
import argparse
import subprocess
import urllib.request

# Configuration du dépôt GitHub pour téléchargement direct
REPO_OWNER = "AnalogShade"
REPO_NAME = "ma-propre-ia-locale"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"
ZIP_URL = f"{REPO_URL}/archive/refs/heads/main.zip"

# Exclusions centralisées
EXCLUDED_PATHS = {
    "data",
    "voices",
    "venv",
    ".venv",
    "env",
    ".git",
    "__pycache__",
    "models",
    "checkpoints",
    "loras",
    "embeddings",
    "outputs",
    "update.log"
}

EXCLUDED_EXTENSIONS = {
    ".gguf",
    ".safetensors",
    ".ckpt",
    ".pt",
    ".pth",
    ".onnx"
}

def log_msg(message):
    """Écrit le message dans la console et dans le fichier %TEMP%/anna_update.log."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    log_path = os.path.join(tempfile.gettempdir(), "anna_update.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def is_process_running(pid):
    """Vérifie si un processus avec le PID donné est toujours en cours d'exécution."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        pass

    # Fallback Windows
    try:
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            return exit_code.value == 259  # STILL_ACTIVE
    except Exception:
        pass
    return False

def check_path_excluded(rel_path):
    """Vérifie si le chemin relatif fait partie des exclusions."""
    parts = rel_path.replace("\\", "/").split("/")
    # Vérification dossier racine exclu
    if parts and parts[0] in EXCLUDED_PATHS:
        return True
    # Vérification extensions exclues
    ext = os.path.splitext(rel_path)[1].lower()
    if ext in EXCLUDED_EXTENSIONS:
        return True
    return False

def run_git_update(root_dir):
    """Exécute la mise à jour par Git pull."""
    log_msg("Lancement de la mise à jour Git (git pull)...")
    try:
        res = subprocess.run(["git", "pull", "origin", "main"], cwd=root_dir, capture_output=True, text=True, timeout=30)
        log_msg("Sortie Git : " + res.stdout.strip())
        if res.returncode == 0:
            log_msg("Mise à jour Git réussie.")
            return True, None
        else:
            return False, res.stderr.strip()
    except Exception as e:
        return False, str(e)

def run_zip_update(root_dir):
    """Exécute la mise à jour par téléchargement de l'archive ZIP et remplacement sécurisé."""
    temp_dir = None
    backup_dir = None
    files_copied = []
    
    try:
        # 1. Création des dossiers temporaires système
        temp_dir = tempfile.mkdtemp(prefix="anna_update_")
        backup_dir = tempfile.mkdtemp(prefix="anna_backup_")
        zip_path = os.path.join(temp_dir, "archive.zip")

        log_msg(f"Téléchargement du code source depuis {ZIP_URL}...")
        req = urllib.request.Request(
            ZIP_URL,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=45) as response, open(zip_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        
        log_msg("Extraction du ZIP...")
        extracted_dir = os.path.join(temp_dir, "extracted")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extracted_dir)

        # Les ZIP de GitHub ont un sous-dossier racine du type <repo>-<branch>
        subdirs = os.listdir(extracted_dir)
        if not subdirs:
            return False, "Le ZIP extrait est vide."
        source_dir = os.path.join(extracted_dir, subdirs[0])

        log_msg("Préparation de la sauvegarde temporaire avant remplacement...")
        # On liste les fichiers à copier pour faire une sauvegarde préventive
        files_to_update = []
        for root, dirs, files in os.walk(source_dir):
            rel_path = os.path.relpath(root, source_dir)
            
            # Appliquer les exclusions de dossier
            if check_path_excluded(rel_path):
                continue
                
            for file in files:
                file_rel = os.path.join(rel_path, file) if rel_path != "." else file
                if check_path_excluded(file_rel):
                    continue
                files_to_update.append(file_rel)

        # Sauvegarde des fichiers locaux existants cibles dans backup_dir
        for file_rel in files_to_update:
            local_file_path = os.path.join(root_dir, file_rel)
            if os.path.exists(local_file_path):
                backup_file_path = os.path.join(backup_dir, file_rel)
                os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)
                shutil.copy2(local_file_path, backup_file_path)

        log_msg("Application des nouveaux fichiers sources...")
        # Copie et écrasement des fichiers
        for file_rel in files_to_update:
            source_file = os.path.join(source_dir, file_rel)
            target_file = os.path.join(root_dir, file_rel)
            
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            shutil.copy2(source_file, target_file)
            files_copied.append(file_rel)
            
        log_msg(f"Remplacement terminé ({len(files_copied)} fichiers copiés).")
        return True, None

    except Exception as e:
        log_msg(f"Erreur lors de la mise à jour ZIP : {e}")
        # Restauration en cas d'erreur
        if files_copied and backup_dir:
            log_msg("Lancement du rollback de sécurité pour restaurer les fichiers d'origine...")
            try:
                for file_rel in files_to_update:
                    backup_file = os.path.join(backup_dir, file_rel)
                    target_file = os.path.join(root_dir, file_rel)
                    if os.path.exists(backup_file):
                        os.makedirs(os.path.dirname(target_file), exist_ok=True)
                        shutil.copy2(backup_file, target_file)
                    elif os.path.exists(target_file) and file_rel in files_copied:
                        # Si le fichier a été copié mais n'existait pas avant, on le supprime pour revenir à l'état initial
                        os.remove(target_file)
                log_msg("Rollback complété avec succès. Anna a été restaurée dans son état initial.")
            except Exception as rollback_err:
                log_msg(f"ERREUR CRITIQUE lors du rollback : {rollback_err}")
        return False, str(e)
        
    finally:
        # Nettoyage des dossiers temporaires système
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
        if backup_dir and os.path.exists(backup_dir):
            try:
                shutil.rmtree(backup_dir)
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(description="Updater autonome externe d'Anna.")
    parser.add_argument("--pid", type=int, required=True, help="PID du processus Anna parent à attendre.")
    parser.add_argument("--root", type=str, required=True, help="Chemin racine du projet Anna.")
    parser.add_argument("--mode", type=str, choices=["git", "zip"], required=True, help="Mode de mise à jour.")
    parser.add_argument("--launcher", type=str, default="", help="Commande de redémarrage d'Anna.")
    args = parser.parse_args()

    log_msg("==============================================")
    log_msg("    ANNA - PROCESSUS DE MISE À JOUR EXTERNE   ")
    log_msg("==============================================")
    log_msg(f"Mode : {args.mode.upper()}")
    log_msg(f"Dossier cible : {args.root}")

    # 1. Attente de la fermeture complète d'Anna
    log_msg(f"Attente de la fermeture de l'application principale Anna (PID: {args.pid})...")
    while is_process_running(args.pid):
        time.sleep(0.5)
    log_msg("Anna s'est fermée. Début de la procédure de mise à jour.")

    # 2. Exécution de la mise à jour selon le mode
    if args.mode == "git":
        success, err = run_git_update(args.root)
    else:
        success, err = run_zip_update(args.root)

    # 3. Finalisation et redémarrage
    if success:
        log_msg("Mise à jour complétée avec succès.")
        if args.launcher:
            log_msg(f"Redémarrage d'Anna avec la commande : {args.launcher}")
            try:
                subprocess.Popen(args.launcher, shell=True, cwd=args.root)
                log_msg("Anna a été relancée.")
            except Exception as launch_err:
                log_msg(f"Impossible de redémarrer Anna automatiquement : {launch_err}")
        
        log_msg("Appuyez sur Entrée pour fermer cette fenêtre...")
        input()
    else:
        log_msg("==============================================")
        log_msg(f"ÉCHEC DE LA MISE À JOUR : {err}")
        log_msg("L'application n'a pas pu être mise à jour.")
        log_msg("Appuyez sur Entrée pour fermer cette fenêtre...")
        input()
        sys.exit(1)

if __name__ == "__main__":
    main()
