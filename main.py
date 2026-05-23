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

def run_console(engine, memory, settings):
    files = FileManager()
    router = IntentRouter()
    router.model = engine.model
    assistant_name = memory.assistant_profile.get("nom", "Antis")
    
    def background_memory_task(user_msg):
        """Tâche d'extraction de faits en arrière-plan."""
        fact = engine.extract_fact(user_msg)
        if fact:
            memory.process_extracted_fact(fact)

    print("==============================================")
    print(f"   {assistant_name.upper()} - MODE CONSOLE (v2.4) ")
    print("==============================================")

    while True:
        user_summary = memory.get_user_info_summary()
        user_input = input("\nVous : ").strip()
        if not user_input: continue

        # Lancement de l'extraction en arrière-plan pour ne pas ralentir la réponse
        threading.Thread(target=background_memory_task, args=(user_input,), daemon=True).start()

        # Gestion des commandes slash spéciales en mode console
        if user_input.startswith('/'):
            parts = user_input.split(' ')
            cmd = parts[0].lower()
            
            if cmd == '/model':
                if len(parts) > 1:
                    model_name = parts[1].strip()
                    models = engine.get_installed_models()
                    
                    matched_model = None
                    if models:
                        if model_name in models:
                            matched_model = model_name
                        else:
                            for m in models:
                                if m.split(':')[0] == model_name.split(':')[0]:
                                    matched_model = m
                                    break
                                    
                    target_model = matched_model if matched_model else model_name
                    engine.model = target_model
                    router.model = target_model
                    settings.set_setting("selected_model", target_model)
                    print(f"\n[SYSTÈME] Modèle commuté vers : {target_model}")
                else:
                    print(f"\n[SYSTÈME] Modèle actuellement actif : {engine.model}. Pour changer, tape : /model <nom>")
                continue
            elif cmd == '/clear':
                memory.clear()
                print("\n[SYSTÈME] Historique de discussion effacé.")
                continue
            elif cmd == '/help':
                help_text = """COMMANDES CONSOLE DISPONIBLES :
/model <nom> : Changer le modèle local
/clear       : Effacer l'historique court terme
/help        : Afficher cette aide
/quit        : Quitter l'application"""
                print(f"\n{help_text}")
                continue
            elif cmd == '/quit':
                print("\nAu revoir !")
                sys.exit(0)

        # 1. DÉTECTION D'INTENTION SYSTÈME (LLM-First)
        result = router.process_intent(user_input, files)
        if result.get("handled"):
            print(f"\n[SYSTÈME] {result.get('message')}")
            
            # Injection de l'action dans la mémoire et arrêt du flux pour éviter les doublons
            memory.add_message("user", user_input)
            memory.add_message("assistant", result.get("system_context"))
            continue

        # 3. VERIFICATION ETAT AVANT REPONSE IA
        keywords_code = ["fichier", "code", "contenu", "analyse", "lis", "vois"]
        if not files.last_file_load_success and any(k in user_input.lower() for k in keywords_code):
            print(f"\n{assistant_name} : Aucun fichier n'est chargé. Utilise 'ouvre [fichier]' après avoir défini ton répertoire.")
            continue

        # 4. APPEL IA NORMAL
        print(f"\n{assistant_name} ({engine.model}) : ", end="", flush=True)
        files_context = files.get_context_for_ai() # Injecte l'état REEL du FileManager
        assistant_summary = memory.get_assistant_info_summary()
        
        response = engine.get_response(
            memory.get_context(), 
            user_summary=user_summary, 
            assistant_summary=assistant_summary,
            assistant_name=assistant_name, 
            files_context=files_context
        )
        print(response if response else "...")
        memory.add_message("user", user_input)
        memory.add_message("assistant", response if response else "...")

def main():
    settings = SettingsManager(SETTINGS_FILE)
    saved_model = settings.get_setting("selected_model", DEFAULT_MODEL_NAME)
    
    engine = AIEngine()
    engine.model = saved_model
    
    memory = MemoryManager()
    
    if "--console" in sys.argv:
        run_console(engine, memory, settings)
    else:
        AnnaGUI(engine, memory).run()

if __name__ == "__main__":
    main()
