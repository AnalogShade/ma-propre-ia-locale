import os
import sys
import time
import tempfile
import datetime
import argparse
import subprocess
import shutil

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

def run_git_update(root_dir):
    """Exécute la mise à jour par Git pull."""
    log_msg("Lancement de la mise à jour Git (git pull)...")
    if not shutil.which("git"):
        return False, "La commande 'git' est introuvable sur le système. Veuillez installer Git pour permettre les mises à jour automatiques."
    try:
        res = subprocess.run(["git", "pull", "origin", "main"], cwd=root_dir, capture_output=True, text=True, timeout=60)
        log_msg("Sortie Git : " + res.stdout.strip())
        if res.returncode == 0:
            log_msg("Mise à jour Git réussie.")
            return True, None
        else:
            err_output = res.stderr.strip() or res.stdout.strip()
            log_msg(f"Erreur lors du pull Git : {err_output}")
            return False, err_output
    except Exception as e:
        log_msg(f"Exception lors du pull Git : {e}")
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Updater autonome externe d'Anna.")
    parser.add_argument("--pid", type=int, required=True, help="PID du processus Anna parent à attendre.")
    parser.add_argument("--root", type=str, required=True, help="Chemin racine du projet Anna.")
    parser.add_argument("--mode", type=str, choices=["git"], required=True, help="Mode de mise à jour.")
    parser.add_argument("--launcher", type=str, default="", help="Commande de redémarrage d'Anna.")
    args = parser.parse_args()

    log_msg("==============================================")
    log_msg("    ANNA - PROCESSUS DE MISE À JOUR EXTERNE   ")
    log_msg("==============================================")
    log_msg(f"Dossier cible : {args.root}")

    # 1. Attente de la fermeture complète d'Anna
    log_msg(f"Attente de la fermeture de l'application principale Anna (PID: {args.pid})...")
    while is_process_running(args.pid):
        time.sleep(0.5)
    log_msg("Anna s'est fermée. Début de la procédure de mise à jour.")

    # 2. Exécution de la mise à jour
    success, err = run_git_update(args.root)

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

