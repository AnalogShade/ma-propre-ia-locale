import os
import sys
import subprocess
import shutil
import urllib.request
import time
import atexit

OLLAMA_URL = "http://127.0.0.1:11434"
_ollama_process = None

def _log(msg):
    """Affiche le message sur la console et l'écrit dans les diagnostics."""
    print(msg)
    try:
        from config import log_diagnostic
        log_diagnostic(msg)
    except Exception:
        pass

def is_ollama_running():
    """Vérifie si le service Ollama écoute sur le port 11434."""
    try:
        req = urllib.request.Request(OLLAMA_URL, method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            return response.status in (200, 204)
    except Exception:
        return False

def find_ollama_executable():
    """Recherche l'exécutable Ollama dans le PATH ou dans les dossiers d'installation courants."""
    exe_name = "ollama.exe" if sys.platform == "win32" else "ollama"
    path_exe = shutil.which(exe_name)
    if path_exe:
        return path_exe

    # Chemins d'installation par défaut si absent du PATH
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            standard_path = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
            if os.path.exists(standard_path):
                return standard_path
        
        program_files = os.environ.get("ProgramFiles", "")
        if program_files:
            standard_path = os.path.join(program_files, "Ollama", "ollama.exe")
            if os.path.exists(standard_path):
                return standard_path
    elif sys.platform == "darwin":
        standard_paths = [
            "/Applications/Ollama.app/Contents/Resources/ollama",
            "/usr/local/bin/ollama",
            "/opt/homebrew/bin/ollama"
        ]
        for p in standard_paths:
            if os.path.exists(p):
                return p
    else:
        standard_paths = [
            "/usr/local/bin/ollama",
            "/usr/bin/ollama"
        ]
        for p in standard_paths:
            if os.path.exists(p):
                return p

    return None

def start_ollama_if_needed(timeout_seconds=15):
    """
    Démarre le serveur Ollama si celui-ci n'est pas déjà actif.
    Retourne le processus Popen si démarré par nous, sinon None.
    """
    if is_ollama_running():
        _log("[OLLAMA] Le service Ollama est déjà actif.")
        return None

    exe_path = find_ollama_executable()
    if not exe_path:
        _log("[OLLAMA] Impossible de trouver l'exécutable Ollama sur votre système. Veuillez l'installer ou le lancer manuellement.")
        return None

    _log(f"[OLLAMA] Tentative de démarrage automatique d'Ollama via : {exe_path}")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.Popen(
            [exe_path, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
    except Exception as e:
        _log(f"[OLLAMA] Échec lors du lancement du processus Ollama : {e}")
        return None

    # Attente active que le serveur réponde
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if is_ollama_running():
            _log(f"[OLLAMA] Le serveur Ollama a été démarré avec succès en {time.time() - start_time:.1f} secondes.")
            return proc
        
        # Vérification si le processus s'est arrêté brutalement
        if proc.poll() is not None:
            _log(f"[OLLAMA] Le processus Ollama s'est arrêté de façon inattendue avec le code de retour {proc.returncode}.")
            return None
            
        time.sleep(0.5)

    _log(f"[OLLAMA] Temps d'attente de {timeout_seconds} secondes dépassé. Le démarrage automatique a échoué.")
    _log("[OLLAMA] Vous pouvez essayer de lancer Ollama manuellement.")
    # On arrête proprement le processus qu'on avait lancé puisqu'il ne répond pas
    stop_ollama(proc)
    return None

def stop_ollama(proc):
    """Arrête proprement le processus de serveur Ollama lancé."""
    if proc is None:
        return
        
    _log("[OLLAMA] Fermeture du serveur Ollama lancé par l'application...")
    try:
        if sys.platform == "win32":
            # Sous Windows, 'ollama serve' peut générer des sous-processus de modèles (runners).
            # Nous utilisons 'taskkill' avec /F (force) et /T (arbre de processus) pour tout nettoyer.
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
                _log("[OLLAMA] Processus Ollama et son arbre de sous-processus arrêtés avec succès via taskkill.")
            except Exception as e:
                # Fallback sur la méthode standard de Python
                _log(f"[OLLAMA] Échec de taskkill ({e}). Tentative d'arrêt via terminate()...")
                proc.terminate()
                proc.wait(timeout=3.0)
        else:
            proc.terminate()
            try:
                proc.wait(timeout=3.0)
                _log("[OLLAMA] Processus Ollama arrêté proprement.")
            except subprocess.TimeoutExpired:
                _log("[OLLAMA] Le processus ne répond pas. Fermeture forcée...")
                proc.kill()
                proc.wait()
                _log("[OLLAMA] Processus Ollama forcé à s'arrêter.")
    except Exception as e:
        _log(f"[OLLAMA] Erreur lors de l'arrêt du processus Ollama : {e}")

def register_cleanup(proc):
    """Enregistre le processus pour être arrêté à la fermeture d'Anna."""
    global _ollama_process
    _ollama_process = proc
    atexit.register(cleanup_on_exit)

def cleanup_on_exit():
    """Callback atexit appelé lors de la fermeture de l'application."""
    global _ollama_process
    if _ollama_process is not None:
        stop_ollama(_ollama_process)
        _ollama_process = None
