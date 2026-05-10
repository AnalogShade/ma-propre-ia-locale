import sys
import json
import threading
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
    
    def background_memory_task(user_msg):
        """T\u00e2che d'extraction de faits en arri\u00e8re-plan."""
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

        # Lancement de l'extraction en arri\u00e8re-plan pour ne pas ralentir la r\u00e9ponse
        threading.Thread(target=background_memory_task, args=(user_input,), daemon=True).start()

        # 1. D\u00c9TECTION D'INTENTION SYST\u00c8ME (LLM-First)
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
        files_context = files.get_context_for_ai() # Injecte l'\u00e9tat REEL du FileManager
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
    if "--console" in sys.argv:
        run_console(AIEngine(), MemoryManager())
    else:
        AnnaGUI(AIEngine(), MemoryManager()).run()

if __name__ == "__main__":
    main()
