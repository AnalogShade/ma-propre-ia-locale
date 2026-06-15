import sys
import os

# 1. Démarrage automatique d'Ollama si configuré
try:
    from settings_manager import SettingsManager
    from config import SETTINGS_FILE
    settings = SettingsManager(SETTINGS_FILE)
    enable_auto = settings.get_setting("enable_auto_ollama", True)
    if enable_auto:
        import ollama_manager
        proc = ollama_manager.start_ollama_if_needed()
        if proc:
            ollama_manager.register_cleanup(proc)
except Exception as e:
    print(f"[ANNA] Avertissement: Impossible d'initialiser le démarrage automatique d'Ollama : {e}")

# 2. Vérification précoce des dépendances
try:
    import dependency_checker
    is_console = "--console" in sys.argv
    checker_results = dependency_checker.run_checker(is_console=is_console)
    if checker_results is None:
        print("[ANNA] Démarrage annulé en raison de dépendances manquantes.")
        sys.exit(1)
except Exception as e:
    print(f"[ANNA] Erreur lors de la vérification des dépendances : {e}")
    sys.exit(1)

# 2. Imports sécurisés après la vérification
from ai_engine import AIEngine
from memory_manager import MemoryManager
from config import SETTINGS_FILE, DEFAULT_MODEL_NAME
from settings_manager import SettingsManager
from gui import AnnaGUI

def run_console(ctrl, checker_results=None):
    assistant_name = ctrl.memory.assistant_profile.get("nom", "Anna")

    print("==============================================")
    print(f"   {assistant_name.upper()} - MODE CONSOLE (v3.0) ")
    print("==============================================")

    if checker_results and checker_results.get("user_messages"):
        dependency_checker.safe_print_console("\nNotifications système :")
        for msg in checker_results["user_messages"]:
            dependency_checker.safe_print_console(f"  {msg}")
        dependency_checker.safe_print_console("==============================================\n")

    try:
        while True:
            user_input = input("\nVous : ").strip()
            if not user_input:
                continue

            # 1. Traitement des commandes slash unifiées
            slash_result = ctrl.process_slash_command(user_input)
            if slash_result:
                if slash_result.get("action") == "quit":
                    print(f"\n{slash_result.get('message')}")
                    sys.exit(0)
                
                print(f"\n[SYSTÈME] {slash_result.get('message')}")
                continue

            # 2. Traitement du message par le contrôleur
            result = ctrl.process_user_message_sync(user_input)
            
            # 3. Gestion des retours du contrôleur
            res_type = result.get("type")
            
            if res_type == "intent_handled":
                print(f"\n[SYSTÈME] {result.get('message')}")
                continue
                
            elif res_type == "error":
                print(f"\n{assistant_name} : {result.get('message')}")
                continue
                
            elif res_type == "ai_response" or res_type == "text":
                # Affichage de la notification système si présente (ex: chargement de contexte sémantique)
                if result.get("system_notification"):
                    print(f"\n[SYSTÈME] {result.get('system_notification')}")
                    
                response = result.get("content")
                print(f"\n{assistant_name} ({ctrl.engine.model}) : {response}")
                
                # Gestion interactive des modifications et commandes
                create_blocks = result.get("create_blocks", [])
                edit_blocks = result.get("edit_blocks", [])
                command_blocks = result.get("command_blocks", [])
                
                if create_blocks or edit_blocks or command_blocks:
                    from pathlib import Path
                    
                    if create_blocks or edit_blocks:
                        print("\n" + "="*50)
                        print("   PROPOSITIONS DE MODIFICATION DE FICHIERS")
                        print("="*50)
                        
                        # Traitement des créations
                        for block in create_blocks:
                            print(f"\n[CRÉATION] Fichier ciblé : {block['file_path']}")
                            print("-" * 40)
                            print(block['content'])
                            print("-" * 40)
                            
                            choix = input(f"Créer ce fichier dans le répertoire ? (o/n) : ").strip().lower()
                            if choix == 'o':
                                success, msg = ctrl.editor.create_file(block['file_path'], block['content'], working_dir=ctrl.files.working_dir)
                                print(f"\n[SYSTÈME] {msg}")
                                change_id = block.get("id")
                                if success:
                                    if change_id:
                                        ctrl.editor.update_change_state(ctrl.files.working_dir, change_id, "APPLIED")
                                    # Recharger le fichier pour qu'il soit dans le contexte IA
                                    ctrl.files.load_file(block['file_path'])
                                else:
                                    if change_id:
                                        ctrl.editor.update_change_state(ctrl.files.working_dir, change_id, "FAILED", error_message=msg)
                            else:
                                print("\n[SYSTÈME] Création annulée.")
                                change_id = block.get("id")
                                if change_id:
                                    ctrl.editor.update_change_state(ctrl.files.working_dir, change_id, "CANCELLED")
                                
                        # Traitement des modifications
                        for block in edit_blocks:
                            print(f"\n📂 PROPOSITION DE MODIFICATION DE : {block['file_path']}")
                            if block.get('invalid'):
                                print(f"\n[REJETÉ] {block.get('error_message')}")
                                print("-" * 40)
                                continue
                                
                            print("-" * 40)
                            print("<<<<<<< SEARCH")
                            print(block['search_content'])
                            print("=======")
                            print(block['replace_content'])
                            print(">>>>>>> REPLACE")
                            print("-" * 40)
                            
                            choix = input(f"Appliquer cette modification ? (o/n) : ").strip().lower()
                            if choix == 'o':
                                # Résolution sécurisée du chemin absolu
                                file_path = block['file_path']
                                if not Path(file_path).is_absolute() and ctrl.files.working_dir:
                                    abs_path = (Path(ctrl.files.working_dir) / file_path).resolve()
                                else:
                                    abs_path = Path(file_path).resolve()
                                    
                                success, msg = ctrl.editor.apply_edit(abs_path, block['search_content'], block['replace_content'])
                                print(f"\n[SYSTÈME] {msg}")
                                change_id = block.get("id")
                                if success:
                                    if change_id:
                                        ctrl.editor.update_change_state(ctrl.files.working_dir, change_id, "APPLIED")
                                    # Recharger le fichier mis à jour pour le contexte
                                    ctrl.files.load_file(block['file_path'])
                                else:
                                    if change_id:
                                        ctrl.editor.update_change_state(ctrl.files.working_dir, change_id, "FAILED", error_message=msg)
                            else:
                                print("\n[SYSTÈME] Modification annulée.")
                                change_id = block.get("id")
                                if change_id:
                                    ctrl.editor.update_change_state(ctrl.files.working_dir, change_id, "CANCELLED")
                                
                    # Traitement des propositions de commandes
                    if command_blocks:
                        print("\n" + "="*50)
                        print("   PROPOSITIONS D'EXÉCUTION DE COMMANDES")
                        print("="*50)
                        for block in command_blocks:
                            cmd = block['command']
                            print(f"\n🖥️ COMMANDE PROPOSÉE : {cmd}")
                            if block.get('invalid'):
                                print(f"\n[BLOQUÉE (SÉCURITÉ)] {block.get('error_message')}")
                                print("-" * 40)
                                continue
                                
                            choix = input(f"Exécuter cette commande dans le répertoire ? (o/n) : ").strip().lower()
                            if choix == 'o':
                                print(f"\n[SYSTÈME] Début de l'exécution de la commande : {cmd}")
                                import subprocess
                                import threading
                                import os
                                
                                creationflags = 0
                                if os.name == 'nt':
                                    creationflags = subprocess.CREATE_NO_WINDOW
                                    
                                stdout_list = []
                                stderr_list = []
                                
                                try:
                                    proc = subprocess.Popen(
                                        cmd,
                                        shell=True,
                                        cwd=ctrl.files.working_dir,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        text=True,
                                        bufsize=1,
                                        creationflags=creationflags
                                    )
                                    
                                    # Lecture en temps réel
                                    def read_stdout():
                                        for line in iter(proc.stdout.readline, ''):
                                            print(line, end='')
                                            stdout_list.append(line)
                                    def read_stderr():
                                        for line in iter(proc.stderr.readline, ''):
                                            print(line, end='', file=sys.stderr)
                                            stderr_list.append(line)
                                            
                                    t_out = threading.Thread(target=read_stdout, daemon=True)
                                    t_err = threading.Thread(target=read_stderr, daemon=True)
                                    t_out.start()
                                    t_err.start()
                                    
                                    proc.wait()
                                    t_out.join()
                                    t_err.join()
                                    
                                    return_code = proc.returncode
                                    print(f"\n[SYSTÈME] Commande terminée avec le code de retour : {return_code}")
                                except Exception as e:
                                    return_code = -1
                                    error_msg = f"Erreur d'exécution : {e}"
                                    print(f"\n[SYSTÈME] {error_msg}")
                                    stderr_list.append(error_msg)
                                    
                                # Construction des extraits de sortie
                                stdout_excerpt = "".join(stdout_list)
                                stderr_excerpt = "".join(stderr_list)
                                if len(stdout_excerpt) > 1000:
                                    stdout_excerpt = stdout_excerpt[:1000] + "\n... [Sortie stdout tronquée]"
                                if len(stderr_excerpt) > 1000:
                                    stderr_excerpt = stderr_excerpt[:1000] + "\n... [Sortie stderr tronquée]"
                                    
                                ctrl.inject_execution_result_to_history(cmd, return_code, stdout_excerpt, stderr_excerpt, False)
                            else:
                                print("\n[SYSTÈME] Commande annulée.")
                    print("\n" + "="*50)
    except (EOFError, KeyboardInterrupt):
        print("\n\nAu revoir !")
        sys.exit(0)

def main():
    if "--console" in sys.argv:
        from agent_controller import AgentController
        ctrl = AgentController()
        run_console(ctrl, checker_results)
    else:
        # Initialisation standalone pour la GUI (comportement d'origine préservé à 100%)
        settings = SettingsManager(SETTINGS_FILE)
        saved_model = settings.get_setting("selected_model", DEFAULT_MODEL_NAME)
        
        engine = AIEngine()
        engine.model = saved_model
        
        memory = MemoryManager()
        AnnaGUI(engine, memory, checker_results).run()

if __name__ == "__main__":
    main()
