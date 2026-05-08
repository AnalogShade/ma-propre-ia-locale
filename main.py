import sys
import json
from ai_engine import AIEngine
from memory_manager import MemoryManager
from config import MODEL_NAME
from gui import AnnaGUI
from file_manager import FileManager
from intent_router import IntentRouter

def handle_file_intent(text, files, router):
    """Utilise l'IA pour détecter l'intention sur les fichiers ou le projet."""
    intent = router.get_file_intent(text)
    action = intent.get("action")
    path = intent.get("path")

    if action == "none":
        return None

    # Exécution de l'action
    if action == "open_file" and path:
        success, msg = files.load_file(path)
        print(f"  [SYSTÈME: {msg}]")
        return msg
    elif action == "set_working_dir" and path:
        success, msg = files.set_working_dir(path)
        print(f"  [SYSTÈME: {msg}]")
        return msg
    elif action == "close_file":
        target = path if path else files.current_file_path
        if target:
            success, msg = files.close_file(target)
            print(f"  [SYSTÈME: {msg}]")
            return msg
    elif action == "reload_file":
        target = path if path else files.current_file_path
        if target:
            success, msg = files.load_file(target)
            print(f"  [SYSTÈME: {msg} (Rechargé)]")
            return msg
    return None

def run_console(engine, memory):
    """Lance la version console de l'application."""
    files = FileManager()
    router = IntentRouter()
    assistant_name = memory.assistant_profile.get("nom", "Antis")
    print("==============================================")
    print(f"   {assistant_name.upper()} - MODE CONSOLE (v2)   ")
    print("==============================================")
    print(f"Modèle : {engine.model}")
    print("Commandes : /quit, /clear, /model <nom>, /openfile <path>, /setdir <path>, /listfiles")
    print("----------------------------------------------")

    while True:
        user_summary = memory.get_user_info_summary()
        files_context = files.get_context_for_ai()
        user_input = input("\nVous : ").strip()

        if not user_input: continue

        # Gestion des commandes manuelles (/)
        if user_input.startswith('/'):
            parts = user_input.split(' ', 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else None

            if cmd == '/quit': break
            elif cmd == '/clear':
                confirm = input("Effacer l'historique ? (o/n) : ")
                if confirm.lower() == 'o': memory.clear()
                continue
            elif cmd == '/model':
                if arg:
                    engine.model = arg
                    print(f"Modèle : {engine.model}")
                continue
            elif cmd == '/openfile':
                if arg:
                    success, msg = files.load_file(arg)
                    print(f"  [SYSTÈME: {msg}]")
                continue
            elif cmd == '/setdir':
                if arg:
                    success, msg = files.set_working_dir(arg)
                    print(f"  [SYSTÈME: {msg}]")
                continue
            elif cmd == '/listfiles':
                if files.working_dir:
                    print(f"  [SYSTÈME: Répertoire de travail : {files.working_dir}]")
                print(f"  [SYSTÈME: {files.list_files()}]")
                continue
            # Les commandes manuelles n'appellent pas l'IA par défaut
            continue

        # Détection langage naturel pour les fichiers et le répertoire
        file_system_msg = handle_file_intent(user_input, files, router)
        
        # Si une action de fichier a été tentée, on l'ajoute au contexte de l'IA
        if file_system_msg:
            files_context += f"\n[NOTIFICATION SYSTÈME : {file_system_msg}]\n"

        # Logique de réponse
        assistant_name = memory.assistant_profile.get("nom", "Antis")
        print(f"\n{assistant_name} ({engine.model}) : ", end="", flush=True)
        
        memory.add_message("user", user_input)
        context = memory.get_context()
        
        response = engine.get_response(context, user_summary=user_summary, assistant_name=assistant_name, files_context=files_context)
        
        if not response:
            user_name = memory.user_profile.get("prénom", memory.user_profile.get("nom", "Louis"))
            response = f"Salut {user_name}, je suis là. (Ollama n'a pas renvoyé de texte)"
            
        print(response)

        if response and "Ollama n'a pas renvoyé de texte" not in response:
            memory.add_message("assistant", response)

        # Extraction de faits
        info = engine.extract_fact(user_input)
        if info and "categorie" in info:
            cat, cle, val = info["categorie"].lower(), info["cle"], info["valeur"]
            if cat == "user_profile": memory.update_user_profile(cle, val)
            elif cat == "assistant_profile": memory.update_assistant_profile(cle, val)
            else: memory.add_fact(cle, val)

def main():
    # Initialisation des composants
    engine = AIEngine()
    memory = MemoryManager()
    
    # Choix de l'interface
    if "--console" in sys.argv:
        run_console(engine, memory)
    else:
        print("Lancement de l'interface graphique...")
        app = AnnaGUI(engine, memory)
        app.run()

if __name__ == "__main__":
    main()
