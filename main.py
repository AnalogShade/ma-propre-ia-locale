import sys
import json
import threading
from ai_engine import AIEngine
from memory_manager import MemoryManager
from config import SETTINGS_FILE, DEFAULT_MODEL_NAME
from settings_manager import SettingsManager
from gui import AnnaGUI
from file_manager import FileManager
from intent_router import IntentRouter
from code_editor import CodeEditor

def run_console(ctrl):
    assistant_name = ctrl.memory.assistant_profile.get("nom", "Anna")

    print("==============================================")
    print(f"   {assistant_name.upper()} - MODE CONSOLE (v3.0) ")
    print("==============================================")

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
                
                # Gestion interactive des modifications de fichiers
                create_blocks = result.get("create_blocks", [])
                edit_blocks = result.get("edit_blocks", [])
                
                if create_blocks or edit_blocks:
                    from pathlib import Path
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
                            if success:
                                # Recharger le fichier pour qu'il soit dans le contexte IA
                                ctrl.files.load_file(block['file_path'])
                        else:
                            print("\n[SYSTÈME] Création annulée.")
                            
                    # Traitement des modifications
                    for block in edit_blocks:
                        print(f"\n[MODIFICATION] Fichier ciblé : {block['file_path']}")
                        print("-" * 40)
                        print("<<< ANCIEN CODE (SEARCH)")
                        print(block['search_content'])
                        print("===")
                        print(">>> NOUVEAU CODE (REPLACE)")
                        print(block['replace_content'])
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
                            if success:
                                # Recharger le fichier mis à jour pour le contexte
                                ctrl.files.load_file(block['file_path'])
                        else:
                            print("\n[SYSTÈME] Modification annulée.")
                    print("\n" + "="*50)
    except (EOFError, KeyboardInterrupt):
        print("\n\nAu revoir !")
        sys.exit(0)

def main():
    if "--console" in sys.argv:
        from agent_controller import AgentController
        ctrl = AgentController()
        run_console(ctrl)
    else:
        # Initialisation standalone pour la GUI (comportement d'origine préservé à 100%)
        settings = SettingsManager(SETTINGS_FILE)
        saved_model = settings.get_setting("selected_model", DEFAULT_MODEL_NAME)
        
        engine = AIEngine()
        engine.model = saved_model
        
        memory = MemoryManager()
        AnnaGUI(engine, memory).run()

if __name__ == "__main__":
    main()
