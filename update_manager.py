import os
import sys
import subprocess
import urllib.request
from datetime import datetime, timedelta

# Configuration du dépôt GitHub
REPO_OWNER = "AnalogShade"
REPO_NAME = "ma-propre-ia-locale"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"
ZIP_URL = f"{REPO_URL}/archive/refs/heads/main.zip"
RAW_VERSION_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/version.txt"

VERSION_FILE = "version.txt"
DEFAULT_VERSION = "3.0.0"

# Exclusions de mise à jour centralisées
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

def parse_version(version_str):
    """
    Découpe proprement une version (ex: '3.10.0') en un tuple d'entiers (3, 10, 0)
    pour permettre des comparaisons mathématiques robustes.
    """
    version_str = version_str.strip().lower().lstrip('v')
    parts = []
    for p in version_str.split('.'):
        digits = []
        for char in p:
            if char.isdigit():
                digits.append(char)
            else:
                break
        if digits:
            parts.append(int("".join(digits)))
        else:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])

def get_local_version():
    """Lit le numéro de version depuis le fichier version.txt local."""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return DEFAULT_VERSION

def is_git_repository():
    """Vérifie si le projet est un clone Git et si la commande git est utilisable."""
    if not os.path.isdir(".git"):
        return False
    try:
        # Tente d'exécuter git --version pour s'assurer que git est dans le PATH
        res = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=3)
        return res.returncode == 0
    except Exception:
        return False

def has_local_git_changes():
    """Retourne True si le répertoire Git local contient des modifications non commises."""
    try:
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5)
        return len(res.stdout.strip()) > 0
    except Exception:
        return False

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

def check_for_updates(settings, force=False):
    """
    Vérifie les mises à jour disponibles.
    Si force=True, ignore l'intervalle de 24h.
    Retourne : (update_available, remote_version_or_commit, error_msg, mode)
    """
    if not force and not should_check_auto(settings):
        # Pas de vérification nécessaire
        return False, None, None, None

    # Tente la vérification réseau
    network_success = False
    update_available = False
    remote_ver_or_commit = None
    error_msg = None
    mode = None

    if is_git_repository():
        mode = "git"
        try:
            # Récupère les modifications distantes sans fusionner
            res_fetch = subprocess.run(["git", "fetch"], capture_output=True, text=True, timeout=10)
            if res_fetch.returncode == 0:
                network_success = True
                # Récupère les hash de commits local et distant
                res_local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
                local_commit = res_local.stdout.strip()

                # Tente de récupérer la branche de suivi amont
                res_remote = subprocess.run(["git", "rev-parse", "@{u}"], capture_output=True, text=True, timeout=5)
                if res_remote.returncode != 0:
                    res_remote = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True, timeout=5)

                remote_commit = res_remote.stdout.strip()

                if local_commit != remote_commit:
                    update_available = True
                    remote_ver_or_commit = remote_commit[:7]
                    # Vérification préliminaire des modifications locales
                    if has_local_git_changes():
                        error_msg = "local_changes"
                else:
                    remote_ver_or_commit = local_commit[:7]
            else:
                # Échec du fetch (ex: pas d'internet), on tente le fallback HTTP (ZIP)
                raise Exception("Git fetch échoué")
        except Exception:
            # Fallback vers le mode ZIP si Git échoue
            pass

    # Si pas en mode Git, ou si le fetch Git a échoué
    if not network_success:
        mode = "zip"
        try:
            local_ver = get_local_version()
            req = urllib.request.Request(
                RAW_VERSION_URL,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            # Timeout réseau de 8 secondes
            with urllib.request.urlopen(req, timeout=8) as response:
                remote_ver = response.read().decode('utf-8').strip()
                network_success = True
                
            if remote_ver:
                if parse_version(remote_ver) > parse_version(local_ver):
                    update_available = True
                    remote_ver_or_commit = remote_ver
                else:
                    remote_ver_or_commit = local_ver
            else:
                raise Exception("Fichier de version distant vide")
        except Exception as e:
            error_msg = str(e)

    # Ne met à jour last_update_check que si le réseau a répondu correctement
    if network_success:
        settings.set_setting("last_update_check", datetime.now().isoformat())

    return update_available, remote_ver_or_commit, error_msg, mode

def start_updater(mode):
    """
    Lance le script updater.py externe dans une console cmd.exe séparée (/k en dev)
    et ferme immédiatement le processus principal d'Anna.
    """
    pid = os.getpid()
    root_dir = os.path.abspath(".")
    
    # Détection de la commande de redémarrage
    launcher_path = os.path.join(root_dir, "lancer_ia.bat")
    if os.path.exists(launcher_path):
        launcher = launcher_path
    else:
        # Fallback commande Python
        launcher = f'"{sys.executable}" "{os.path.join(root_dir, "main.py")}"'

    # Correction pour exécuter python.exe (avec console) au lieu de pythonw.exe
    python_exe = sys.executable
    if python_exe.lower().endswith("pythonw.exe"):
        python_exe = python_exe[:-9] + "python.exe"

    updater_script = os.path.join(root_dir, "updater.py")

    # Arguments transmis à updater.py
    args = [
        "--pid", str(pid),
        "--root", root_dir,
        "--mode", mode,
        "--launcher", launcher
    ]

    # Construction de la commande cmd pour démarrer la console séparée en mode debug (/k)
    cmd = [
        "cmd.exe", "/c", "start", "cmd", "/k",
        python_exe, updater_script
    ] + args

    # Démarrage du processus externe sans bloquer
    subprocess.Popen(cmd, shell=True)
