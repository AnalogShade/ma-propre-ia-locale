import sys
import collections
import threading
from datetime import datetime

class SharedBuffer:
    """
    Buffer tournant thread-safe conservant en mémoire les N dernières lignes de logs.
    """
    def __init__(self, max_lines=5000):
        self.max_lines = max_lines
        self.lines = collections.deque(maxlen=max_lines)
        self.current_line = []
        self.lock = threading.Lock()

    def append_text(self, message):
        with self.lock:
            if not message:
                return
            
            # Découpage du message pour gérer les retours à la ligne
            parts = message.split('\n')
            
            # S'il n'y a pas de saut de ligne, on accumule dans la ligne courante
            if len(parts) == 1:
                self.current_line.append(parts[0])
            else:
                # On complète la ligne courante avec le début du message splité et on l'ajoute
                self.current_line.append(parts[0])
                self.lines.append("".join(self.current_line))
                
                # Ajout des lignes intermédiaires complètes
                for part in parts[1:-1]:
                    self.lines.append(part)
                
                # Le dernier élément devient la nouvelle ligne courante en cours d'écriture
                self.current_line = [parts[-1]]

    def get_logs(self):
        with self.lock:
            lines_list = list(self.lines)
            if self.current_line:
                lines_list.append("".join(self.current_line))
            return "\n".join(lines_list)


class TerminalLogCapturer:
    """
    Flux d'écriture personnalisé interceptant stdout/stderr et les redirigeant
    à la fois vers le flux original de la console et le tampon partagé.
    """
    def __init__(self, original_stream, shared_buffer):
        self.original_stream = original_stream
        self.shared_buffer = shared_buffer

    def write(self, message):
        # Écriture dans le flux d'origine (si disponible)
        if self.original_stream:
            try:
                self.original_stream.write(message)
            except Exception:
                pass
        
        # Capture dans notre tampon partagé
        self.shared_buffer.append_text(message)

    def flush(self):
        # Vidage du flux d'origine
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass


# Tampon partagé global pour stocker les logs de l'application (limite à 5000 lignes)
_shared_buffer = SharedBuffer(max_lines=5000)
_original_stdout = None
_original_stderr = None

def setup_terminal_capture():
    """
    Remplace sys.stdout et sys.stderr pour intercepter les flux de sortie.
    """
    global _original_stdout, _original_stderr
    if _original_stdout is None:
        _original_stdout = sys.stdout
        sys.stdout = TerminalLogCapturer(_original_stdout, _shared_buffer)
    if _original_stderr is None:
        _original_stderr = sys.stderr
        sys.stderr = TerminalLogCapturer(_original_stderr, _shared_buffer)

def restore_terminal_capture():
    """
    Restaure les flux stdout et stderr originaux (à appeler à la fermeture).
    """
    global _original_stdout, _original_stderr
    if _original_stdout is not None:
        sys.stdout = _original_stdout
        _original_stdout = None
    if _original_stderr is not None:
        sys.stderr = _original_stderr
        _original_stderr = None

def get_terminal_logs():
    """
    Retourne les logs console interceptés sous forme d'une chaîne unique.
    """
    return _shared_buffer.get_logs()

def generate_export_content(chat_text, trace_text, active_model, working_dir, current_file):
    """
    Génère un bloc de texte formaté au format Markdown contenant l'ensemble des
    informations de diagnostic et les logs de l'application.
    """
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Construction de l'en-tête de diagnostic
    header = [
        "==================================================",
        "ANNA DEBUG LOGS & TRACES",
        f"Date & Heure        : {date_str}",
        "Application         : ANNA - IA Locale",
        f"Modèle Actif        : {active_model or 'Aucun'}",
        f"Dossier de Travail  : {working_dir or 'Aucun'}",
        f"Fichier Actif       : {current_file or 'Aucun'}",
        "=================================================="
    ]
    header_text = "\n".join(header)
    
    # Section Historique du Chat
    chat_section = (
        "### 💬 HISTORIQUE DU CHAT\n"
        "--------------------------------------------------\n"
        f"{chat_text.strip() if chat_text else 'Aucun message.'}\n"
    )
    
    # Section Trace du Modèle
    trace_section = (
        "### 🔍 TRACE DU MODÈLE\n"
        "--------------------------------------------------\n"
        f"{trace_text.strip() if trace_text else 'Aucune trace.'}\n"
    )
    
    # Section Trace du Terminal
    terminal_section = (
        "### 💻 TRACE DU TERMINAL (CONSOLE)\n"
        "--------------------------------------------------\n"
        f"{get_terminal_logs().strip() if get_terminal_logs().strip() else 'Aucun log console.'}\n"
    )
    
    return f"{header_text}\n\n{chat_section}\n{trace_section}\n{terminal_section}"


# =========================================================================
# CODE POUR INTÉGRATIONS FUTURES (Exemple d'utilisation avec le module logging)
# =========================================================================
#
# import logging
#
# class SharedBufferLoggingHandler(logging.Handler):
#     """
#     Handler personnalisé pour le module logging de Python permettant d'écrire
#     directement dans notre tampon de debug partagé sans passer par sys.stderr.
#     """
#     def __init__(self, shared_buffer):
#         super().__init__()
#         self.shared_buffer = shared_buffer
#
#     def emit(self, record):
#         try:
#             msg = self.format(record)
#             self.shared_buffer.append_text(msg + '\n')
#         except Exception:
#             self.handleError(record)
#
