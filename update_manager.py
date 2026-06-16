import os
import sys
import subprocess
from datetime import datetime, timedelta

# Configuration du dépôt GitHub
REPO_OWNER = "AnalogShade"
REPO_NAME = "ma-propre-ia-locale"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"

def check_git_installed():
    """Vérifie si la commande git est utilisable sur le système."""
    try:
        res = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=3)
        return res.returncode == 0
    except Exception:
        return False

def get_installation_type(root_dir=None):
    """
    Détecte le type d'installation :
    - 'GIT_CLONE' : dépôt Git valide et Git installé.
    - 'GIT_MISSING' : dossier .git présent mais Git non disponible.
    - 'ZIP_INSTALL' : dossier .git absent.
    """
    if root_dir is None:
        root_dir = os.path.abspath(".")
    
    git_dir_exists = os.path.isdir(os.path.join(root_dir, ".git"))
    git_installed = check_git_installed()
    
    if git_dir_exists:
        if git_installed:
            return "GIT_CLONE"
        else:
            return "GIT_MISSING"
    else:
        return "ZIP_INSTALL"

def get_local_file_git_sha(file_path, root_dir):
    """Calcule le SHA-1 Git d'un fichier local."""
    try:
        res = subprocess.run(["git", "hash-object", file_path], capture_output=True, text=True, timeout=5, cwd=root_dir)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None

def convert_zip_to_git_step1(root_dir=None):
    """
    Étape 1 de la conversion ZIP -> Git :
    Initialise le dépôt, ajoute le remote, fait un fetch, et compare les signatures
    de fichiers locaux avec la version officielle pour vérifier la correspondance.
    Retourne : (success, matches_official, error_msg)
    """
    if root_dir is None:
        root_dir = os.path.abspath(".")
        
    from config import log_diagnostic
    log_diagnostic(f"[Updater] Étape 1 de conversion ZIP -> Git dans : {root_dir}")
    
    try:
        # 1. git init
        res = subprocess.run(["git", "init"], capture_output=True, text=True, timeout=10, cwd=root_dir)
        if res.returncode != 0:
            return False, False, f"git init a échoué: {res.stderr.strip()}"
            
        # 2. git remote add origin
        res_remote = subprocess.run(["git", "remote"], capture_output=True, text=True, timeout=5, cwd=root_dir)
        if "origin" not in res_remote.stdout:
            res = subprocess.run(["git", "remote", "add", "origin", REPO_URL + ".git"], capture_output=True, text=True, timeout=5, cwd=root_dir)
            if res.returncode != 0:
                return False, False, f"git remote add a échoué: {res.stderr.strip()}"
                
        # 3. git fetch origin main
        res = subprocess.run(["git", "fetch", "origin", "main"], capture_output=True, text=True, timeout=30, cwd=root_dir)
        if res.returncode != 0:
            return False, False, f"git fetch a échoué: {res.stderr.strip()}"
            
        # 4. Comparaison
        res_tree = subprocess.run(["git", "ls-tree", "-r", "origin/main"], capture_output=True, text=True, timeout=15, cwd=root_dir)
        if res_tree.returncode != 0:
            return False, False, f"git ls-tree a échoué: {res_tree.stderr.strip()}"
            
        lines = res_tree.stdout.strip().split("\n")
        matches_official = True
        
        for line in lines:
            if not line.strip():
                continue
            # Format attendu : <mode> <type> <sha1>    <file>
            parts = line.replace("\t", " ").split(maxsplit=3)
            if len(parts) >= 4:
                remote_sha = parts[2]
                file_rel_path = parts[3].strip()
                
                local_file_path = os.path.join(root_dir, file_rel_path)
                if not os.path.exists(local_file_path):
                    matches_official = False
                    log_diagnostic(f"[Updater] Fichier suivi absent localement : {file_rel_path}")
                    break
                else:
                    local_sha = get_local_file_git_sha(local_file_path, root_dir)
                    if local_sha != remote_sha:
                        matches_official = False
                        log_diagnostic(f"[Updater] Fichier suivi modifié localement : {file_rel_path} (local={local_sha}, remote={remote_sha})")
                        break
                        
        return True, matches_official, None
    except Exception as e:
        log_diagnostic(f"[Updater] Erreur lors de l'étape 1 de conversion : {e}")
        return False, False, str(e)

def convert_zip_to_git_step2(force_sync, root_dir=None):
    """
    Étape 2 de la conversion ZIP -> Git :
    Attache HEAD à main et aligne l'index Git (soit proprement avec un reset mixte,
    soit de façon forcée avec reset --hard si force_sync=True).
    Retourne : (success, error_msg)
    """
    if root_dir is None:
        root_dir = os.path.abspath(".")
        
    from config import log_diagnostic
    log_diagnostic(f"[Updater] Étape 2 de conversion ZIP -> Git (force_sync={force_sync})")
    
    try:
        # 1. Rattacher HEAD à main
        res = subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], capture_output=True, text=True, timeout=5, cwd=root_dir)
        if res.returncode != 0:
            return False, f"git symbolic-ref a échoué: {res.stderr.strip()}"
            
        # 2. Reset de l'index
        if force_sync:
            res = subprocess.run(["git", "reset", "--hard", "origin/main"], capture_output=True, text=True, timeout=15, cwd=root_dir)
        else:
            res = subprocess.run(["git", "reset", "origin/main"], capture_output=True, text=True, timeout=15, cwd=root_dir)
            
        if res.returncode != 0:
            return False, f"git reset a échoué: {res.stderr.strip()}"
            
        log_diagnostic("[Updater] Conversion ZIP -> Git complétée avec succès.")
        return True, None
    except Exception as e:
        log_diagnostic(f"[Updater] Erreur lors de l'étape 2 de conversion : {e}")
        return False, str(e)

def convert_zip_to_git_cleanup(root_dir=None):
    """Supprime proprement le dossier .git en cas d'annulation de la conversion."""
    if root_dir is None:
        root_dir = os.path.abspath(".")
        
    from config import log_diagnostic
    log_diagnostic("[Updater] Annulation de la conversion, nettoyage du dossier .git")
    
    git_dir = os.path.join(root_dir, ".git")
    if os.path.isdir(git_dir):
        try:
            import shutil
            def remove_readonly(func, path, excinfo):
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(git_dir, onerror=remove_readonly)
            log_diagnostic("[Updater] Nettoyage du dossier .git terminé.")
            return True
        except Exception as e:
            log_diagnostic(f"[Updater] Erreur lors de la suppression du dossier .git : {e}")
            return False
    return True

def install_git():
    """Tente d'installer Git automatiquement sur Windows via winget."""
    from config import log_diagnostic
    log_diagnostic("[Updater] Tentative d'installation de Git via winget...")
    try:
        res = subprocess.run([
            "winget", "install", "--id", "Git.Git", "-e",
            "--accept-source-agreements", "--accept-package-agreements"
        ], capture_output=True, text=True, timeout=300)
        
        if res.returncode == 0:
            log_diagnostic("[Updater] Installation de Git via winget réussie.")
            return True, "winget"
        else:
            log_diagnostic(f"[Updater] winget a échoué avec le code {res.returncode}. Sortie: {res.stdout.strip()} {res.stderr.strip()}")
    except Exception as e:
        log_diagnostic(f"[Updater] Échec du lancement de winget : {e}")
        
    return False, None

def should_check_auto(settings):
    """Détermine si la vérification automatique des mises à jour doit s'exécuter (max 1 fois par 24h)."""
    if not settings.get_setting("auto_check_updates", True):
        return False

    last_check_str = settings.get_setting("last_update_check", "")
    if not last_check_str:
        return True

    try:
        last_check = datetime.fromisoformat(last_check_str)
        if datetime.now() - last_check > timedelta(hours=24):
            return True
    except Exception:
        return True

    return False

def check_for_updates(settings, force=False, root_dir=None):
    """
    Vérifie s'il y a une mise à jour Git.
    Retourne : (update_available, remote_commit, error_msg, mode)
    """
    if root_dir is None:
        root_dir = os.path.abspath(".")
        
    from config import log_diagnostic
    
    mode = get_installation_type(root_dir)
    
    # Si vérification automatique (fond de tâche), on ignore silencieusement pour ZIP et GIT_MISSING
    if not force:
        if mode in ("ZIP_INSTALL", "GIT_MISSING"):
            return False, None, None, mode
        if not should_check_auto(settings):
            return False, None, None, None
            
    if mode == "GIT_CLONE":
        try:
            log_diagnostic(f"[Updater] Lancement de git fetch dans {root_dir}...")
            res_fetch = subprocess.run(["git", "fetch"], capture_output=True, text=True, timeout=20, cwd=root_dir)
            if res_fetch.returncode == 0:
                res_local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, cwd=root_dir)
                local_commit = res_local.stdout.strip()
                
                res_remote = subprocess.run(["git", "rev-parse", "@{u}"], capture_output=True, text=True, timeout=5, cwd=root_dir)
                if res_remote.returncode != 0:
                    res_remote = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True, timeout=5, cwd=root_dir)
                    
                remote_commit = res_remote.stdout.strip()
                
                if local_commit != remote_commit:
                    log_diagnostic(f"[Updater] Mise à jour disponible : {remote_commit[:7]} (actuelle : {local_commit[:7]})")
                    
                    res_status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5, cwd=root_dir)
                    status_lines = res_status.stdout.splitlines()
                    has_local_changes = False
                    for line in status_lines:
                        if line.strip() and not line.startswith("??"):
                            has_local_changes = True
                            break
                            
                    if has_local_changes:
                        log_diagnostic("[Updater] Changements locaux détectés sur des fichiers suivis.")
                        return True, remote_commit[:7], "local_changes", mode
                    return True, remote_commit[:7], None, mode
                else:
                    log_diagnostic("[Updater] Anna est déjà à jour.")
                    settings.set_setting("last_update_check", datetime.now().isoformat())
                    return False, local_commit[:7], None, mode
            else:
                err_msg = res_fetch.stderr.strip()
                log_diagnostic(f"[Updater] Échec de git fetch : {err_msg}")
                return False, None, f"git fetch a échoué: {err_msg}", mode
        except Exception as e:
            log_diagnostic(f"[Updater] Exception lors de la vérification : {e}")
            return False, None, str(e), mode
            
    return False, None, None, mode

def start_updater(mode):
    """
    Lance le script updater.py externe dans une console séparée
    et ferme immédiatement le processus principal d'Anna.
    """
    pid = os.getpid()
    root_dir = os.path.abspath(".")
    
    launcher_path = os.path.join(root_dir, "lancer_ia.bat")
    if os.path.exists(launcher_path):
        launcher = launcher_path
    else:
        launcher = f'"{sys.executable}" "{os.path.join(root_dir, "main.py")}"'

    from pathlib import Path
    python_exe = sys.executable
    if Path(python_exe).name.lower() == "pythonw.exe":
        python_exe = str(Path(python_exe).with_name("python.exe"))

    updater_script = os.path.join(root_dir, "updater.py")

    args = [
        "--pid", str(pid),
        "--root", root_dir,
        "--mode", "git",  # Force uniquement le mode git dans l'updater
        "--launcher", launcher
    ]

    cmd = [python_exe, updater_script] + args
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    print(f"[Updater] Lancement de l'updater externe avec {python_exe}")
    subprocess.Popen(cmd, creationflags=creationflags)

