import sys
import json
from ai_engine import AIEngine
from memory_manager import MemoryManager
from config import MODEL_NAME
from gui import AnnaGUI
from file_manager import FileManager
from intent_router import IntentRouter

def run_console(engine, memory):
    files = FileManager()
    router = IntentRouter()
    assistant_name = memory.assistant_profile.get("nom", "Antis")
    print("==============================================")
    print(f"   {assistant_name.upper()} - MODE CONSOLE (v2.4) ")
    print("==============================================")

    while True:
        user_summary = memory.get_user_info_summary()
        user_input = input("\nVous : ").strip()
        if not user_input: continue

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
        
        response = engine.get_response(memory.get_context(), user_summary=user_summary, assistant_name=assistant_name, files_context=files_context)
        print(response if response else "...")
        memory.add_message("user", user_input)
        memory.add_message("assistant", response if response else "...")

def main():
    if "--console" in sys.argv:
        run_console(AIEngine(), MemoryManager())
    else:
        AnnaGUI(AIEngine(), MemoryManager()).run()

if __name__ == "__main__":
    main()
