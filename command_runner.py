import os
import re
import subprocess
import threading

class CommandRunner:
    def __init__(self, controller=None):
        self.controller = controller
        self._active_processes = {}
        # Sensible default blacklist
        self.blacklist = [
            r"\brm\s+-rf\b",
            r"\brmdir\s+/[sS]\b",
            r"\bdel\s+/[fFqQsS]*\b",
            r"\bformat\b",
            r"\bmkfs\b",
            r"\bshutdown\b",
            r"\breboot\b",
            r"\binit\s+[06]\b"
        ]

    def parse_command_blocks(self, text):
        """
        Extrait les blocs de commande du texte de réponse de l'assistant.
        Format attendu :
        <<<<<<< EXECUTE_COMMAND
        commande
        >>>>>>> EXECUTE_COMMAND
        
        Retourne une liste de dictionnaires :
        [
            {
                "command": "python main.py"
            },
            ...
        ]
        """
        if not text:
            return []
            
        blocks = []
        lines = text.splitlines()
        in_block = False
        block_content = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("<<<<<<< EXECUTE_COMMAND"):
                in_block = True
                block_content = []
                continue
            if stripped.startswith(">>>>>>> EXECUTE_COMMAND"):
                if in_block:
                    cmd = "\n".join(block_content).strip()
                    if cmd:
                        blocks.append({
                            "command": cmd
                        })
                    in_block = False
                continue
            if in_block:
                block_content.append(line)
        return blocks

    def validate_command(self, command, working_dir):
        """
        Valide si la commande est sécurisée et peut être exécutée.
        Retourne (is_valid, message_erreur).
        """
        if not command or not command.strip():
            return False, "La commande est vide."

        # Récupérer la blacklist à partir de la configuration globale si dispo
        blacklist_patterns = self.blacklist
        if self.controller:
            try:
                import config
                blacklist_patterns = getattr(config, 'BLACKLIST_COMMANDS', self.blacklist)
            except ImportError:
                pass

        # Recherche de motifs interdits
        for pattern in blacklist_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"La commande contient un terme ou motif interdit par la politique de sécurité : '{pattern}'."

        # Vérification du répertoire de travail
        if not working_dir:
            return False, "Aucun répertoire de travail n'est défini dans l'application."

        if not os.path.exists(working_dir):
            return False, f"Le répertoire de travail '{working_dir}' n'existe pas sur le disque."

        return True, ""

    def execute_async(self, command, working_dir, on_output, on_complete):
        """
        Exécute la commande de manière asynchrone dans un thread d'arrière-plan.
        Retourne le PID du processus lancé, ou None en cas d'erreur de lancement immédiat.
        
        on_output : callback(chunk_text) appelé périodiquement à la réception de texte.
        on_complete : callback(return_code, stdout_excerpt, stderr_excerpt, is_cancelled) appelé à la fin.
        """
        if not working_dir:
            on_output("[ERREUR] Aucun répertoire de travail défini.\n")
            on_complete(-1, "", "Aucun répertoire de travail défini.", False)
            return None

        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered pour un affichage fluide
                creationflags=creationflags
            )
        except Exception as e:
            error_msg = f"Erreur de lancement : {str(e)}"
            on_output(f"[ERREUR] {error_msg}\n")
            on_complete(-1, "", error_msg, False)
            return None

        pid = proc.pid
        is_cancelled = [False]
        self._active_processes[pid] = (proc, is_cancelled)

        def reader_thread():
            stdout_list = []
            stderr_list = []

            # Fonctions de lecture pour stdout et stderr
            def read_stream(stream, is_stderr):
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    on_output(line)
                    if is_stderr:
                        stderr_list.append(line)
                    else:
                        stdout_list.append(line)

            t_out = threading.Thread(target=read_stream, args=(proc.stdout, False), daemon=True)
            t_err = threading.Thread(target=read_stream, args=(proc.stderr, True), daemon=True)
            t_out.start()
            t_err.start()

            # Attente de la fin du processus et des threads de lecture
            proc.wait()
            t_out.join()
            t_err.join()

            # Fermeture explicite des flux pour éviter les ResourceWarnings
            try:
                proc.stdout.close()
            except Exception:
                pass
            try:
                proc.stderr.close()
            except Exception:
                pass

            # Nettoyage de l'arborescence des processus actifs
            if pid in self._active_processes:
                del self._active_processes[pid]

            # Construction des extraits de sortie pour la mémoire du LLM (max 1000 caractères)
            stdout_excerpt = "".join(stdout_list)
            stderr_excerpt = "".join(stderr_list)

            if len(stdout_excerpt) > 1000:
                stdout_excerpt = stdout_excerpt[:1000] + "\n... [Sortie stdout tronquée]"
            if len(stderr_excerpt) > 1000:
                stderr_excerpt = stderr_excerpt[:1000] + "\n... [Sortie stderr tronquée]"

            on_complete(proc.returncode, stdout_excerpt, stderr_excerpt, is_cancelled[0])

        t = threading.Thread(target=reader_thread, daemon=True)
        t.start()

        return pid

    def stop_process(self, pid):
        """
        Arrête le processus associé au PID spécifié et toute son arborescence de processus.
        """
        if pid in self._active_processes:
            proc, is_cancelled = self._active_processes[pid]
            is_cancelled[0] = True
            try:
                if os.name == 'nt':
                    # Arrêt de toute l'arborescence sur Windows pour tuer les processus fils (ex: serveurs Web)
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    proc.terminate()
                    proc.wait(timeout=2)
            except Exception as e:
                print(f"[COMMAND_RUNNER WARNING] Impossible d'arrêter le processus {pid} proprement : {e}")
                try:
                    proc.kill()
                except Exception:
                    pass
