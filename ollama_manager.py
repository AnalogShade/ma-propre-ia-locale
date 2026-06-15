import os
import sys
import subprocess
import shutil
import urllib.request
import time
import atexit
import socket

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

def is_port_occupied(port=11434):
    """Vérifie par socket TCP si un service écoute sur le port spécifié."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            return False

def check_ollama_api(timeout=1.0):
    """
    Vérifie si l'API d'Ollama répond sur l'endpoint léger /api/tags.
    Retourne un tuple (responds_ok, status_msg).
    """
    url = f"{OLLAMA_URL}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as response:
            duration = time.time() - t0
            if response.status == 200:
                if duration > 0.8 * timeout:
                    return True, f"Ollama répond mais lentement ({duration:.2f}s)"
                return True, "Ollama déjà actif"
            else:
                return False, f"Code HTTP inattendu : {response.status}"
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.timeout):
            return False, "Ollama ne répond pas (timeout de l'API)"
        return False, f"Ollama indisponible ({e.reason})"
    except Exception as e:
        return False, f"Erreur de connexion Ollama : {e}"

def is_ollama_running():
    """Vérifie si le service Ollama écoute sur le port 11434 et répond à l'API."""
    running, _ = check_ollama_api(timeout=1.0)
    return running

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
    Démarre le serveur Ollama si aucun service n'est déjà actif sur le port 11434.
    Retourne le processus Popen si démarré par nous, sinon None.
    """
    port_busy = is_port_occupied()
    
    if port_busy:
        # Le port est occupé, on ne tente pas de double bind. On vérifie l'API.
        api_ok, api_msg = check_ollama_api(timeout=1.5)
        if api_ok:
            if "lentement" in api_msg:
                _log(f"[OLLAMA] Ollama répond mais lentement.")
            else:
                _log("[OLLAMA] Ollama déjà actif.")
        else:
            _log(f"[OLLAMA] Avertissement: Le port 11434 est occupé, mais l'API ne répond pas ou répond lentement : {api_msg}. Utilisation de l'instance existante.")
        return None

    exe_path = find_ollama_executable()
    if not exe_path:
        _log("[OLLAMA] Ollama indisponible (impossible de trouver l'exécutable Ollama sur votre système. Veuillez l'installer ou le lancer manuellement).")
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

    # Attente active non bloquante pour l'utilisateur
    start_time = time.time()
    _log("[OLLAMA] Attente de la disponibilité de l'API Ollama...")
    while time.time() - start_time < timeout_seconds:
        api_ok, api_msg = check_ollama_api(timeout=1.0)
        if api_ok:
            _log(f"[OLLAMA] Ollama lancé par Anna en {time.time() - start_time:.1f} secondes.")
            return proc
        
        # Vérification si le processus s'est arrêté brutalement
        if proc.poll() is not None:
            _log(f"[OLLAMA] Le processus Ollama s'est arrêté de façon inattendue avec le code de retour {proc.returncode}.")
            return None
            
        time.sleep(0.5)

    _log(f"[OLLAMA] Temps d'attente de {timeout_seconds} secondes dépassé. Le démarrage automatique a échoué.")
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
