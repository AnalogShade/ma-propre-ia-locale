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
    """
    Détecte directement si l'utilisateur donne un répertoire de travail via regex.
    Retourne le chemin extrait ou None.
    """
    patterns = [
        r"(?:répertoire de travail|dossier de travail|dossier du projet|répertoire du projet|working directory|working_dir)[\s:]+([a-zA-Z]:\\[^\"<>|]+|/[^\"<>|]+|\.[\\/][^\"<>|]+)",
        r"(?:répertoire de travail|dossier de travail|dossier du projet|répertoire du projet|working directory|working_dir)[\s:]+(.*)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            # Nettoyage si le chemin se termine par une ponctuation
            path = path.rstrip('.?!')
            return path
    return None

def handle_file_intent(text, files, router):
    """Analyse l'intention via l'IA pour les autres actions (ouverture, etc.)."""
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
    print(f"   {assistant_name.upper()} - MODE CONSOLE (v2.3) ")
    print("==============================================")

    while True:
        user_summary = memory.get_user_info_summary()
        user_input = input("\nVous : ").strip()
        if not user_input: continue

        # 1. DÉTECTION DIRECTE (REGEX) pour le répertoire de travail
        dir_path = detect_working_dir_regex(user_input)
        if dir_path:
            print(f"  [DEBUG MAIN] Détection directe set_working_dir")
            print(f"  [DEBUG MAIN] Chemin extrait : {dir_path}")
            success, msg = files.set_working_dir(dir_path)
            
            if success:
                print(f"\n[SYSTÈME] Répertoire de travail défini :\n{dir_path}")
            else:
                print(f"\n[SYSTÈME] Échec : {msg}")
            
            memory.add_message("user", user_input)
            memory.add_message("assistant", f"[ACTION SYSTÈME] {msg}")
            continue

        # 2. Détection via IA pour les autres intentions
        handled, success, msg = handle_file_intent(user_input, files, router)
        
        if handled:
            if success:
                print(f"\n[SYSTÈME] Action réussie : {msg}")
            else:
                print(f"\n[SYSTÈME] Échec : {msg}")
                if files.working_dir:
                    print(f"Répertoire actuel : {files.working_dir}")
            
            memory.add_message("user", user_input)
            memory.add_message("assistant", f"[ACTION SYSTÈME] {msg}")
            continue

        # 3. Vérification si question sur code sans fichier
        keywords = ["fichier", "code", "contenu", "analyse", "lis"]
        if not files.last_file_load_success and any(k in user_input.lower() for k in keywords):
            print(f"\n{assistant_name} : Aucun fichier n'est chargé. Je ne peux pas répondre à cette question.")
            continue

        # 4. Appel IA normal
        print(f"\n{assistant_name} ({engine.model}) : ", end="", flush=True)
        files_context = files.get_context_for_ai()
        memory.add_message("user", user_input)
        
        response = engine.get_response(memory.get_context(), user_summary=user_summary, assistant_name=assistant_name, files_context=files_context)
        print(response if response else "...")
        memory.add_message("assistant", response if response else "...")

def main():
    if "--console" in sys.argv:
        run_console(AIEngine(), MemoryManager())
    else:
        AnnaGUI(AIEngine(), MemoryManager()).run()

if __name__ == "__main__":
    main()
