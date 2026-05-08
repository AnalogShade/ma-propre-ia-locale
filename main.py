import sys
import json
import re
from ai_engine import AIEngine
from memory_manager import MemoryManager
from config import MODEL_NAME
from gui import AnnaGUI
from file_manager import FileManager
from intent_router import IntentRouter

def detect_working_dir_regex(text):
    """Détecte le répertoire de travail via regex (priorité absolue)."""
    # Pattern simplifié : cherche un mot clé suivi de ce qui ressemble à un chemin
    keywords = r"répertoire de travail|dossier de travail|dossier du projet|répertoire du projet|working directory|working_dir"
    pattern = rf"(?:{keywords})[\s:]+([a-zA-Z]:\\[^\"<>|]+|/[^\"<>|]+)"
    
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.?!')
    
    # Fallback si le chemin ne commence pas par une lettre de lecteur (ex: relatif)
    pattern_fallback = rf"(?:{keywords})[\s:]+(.+)"
    match = re.search(pattern_fallback, text, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.?!')
        
    return None

def handle_file_intent(text, files, router):
    intent = router.get_file_intent(text)
    action = intent.get("action")
    path = intent.get("path")

    if action == "none": return False, True, None

    if action == "open_file" and path:
        success, msg = files.load_file(path)
        return True, success, msg
    
    elif action == "set_working_dir" and path:
        success, msg = files.set_working_dir(path)
        return True, success, msg
    
    return False, True, None

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

        # 1. REGEX (Priorité)
        dir_path = detect_working_dir_regex(user_input)
        if dir_path:
            print(f"  [DEBUG MAIN] Détection directe set_working_dir")
            success, msg = files.set_working_dir(dir_path)
            print(f"\n[SYSTÈME] {msg}")
            memory.add_message("user", user_input)
            memory.add_message("assistant", f"[ACTION SYSTÈME] {msg}")
            continue

        # 2. IA INTENT
        handled, success, msg = handle_file_intent(user_input, files, router)
        if handled:
            print(f"\n[SYSTÈME] {msg}")
            if not success:
                # Blocage immédiat de l'IA en cas d'erreur de chargement
                print(f"{assistant_name} : Je ne peux pas accéder à ce fichier. Erreur : {msg}")
                memory.add_message("user", user_input)
                memory.add_message("assistant", f"Erreur : {msg}")
                continue
            
            # Si succès, on bloque quand même l'IA libre pour éviter les doublons de réponse
            memory.add_message("user", user_input)
            memory.add_message("assistant", f"[ACTION SYSTÈME] {msg}")
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
