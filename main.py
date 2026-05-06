import sys
from ai_engine import AIEngine
from memory_manager import MemoryManager
from config import MODEL_NAME
from gui import AnnaGUI
from file_manager import FileManager

def run_console(engine, memory):
    """Lance la version console de l'application."""
    files = FileManager()
    assistant_name = memory.assistant_profile.get("nom", "Antis")
    print("==============================================")
    print(f"   {assistant_name.upper()} - MODE CONSOLE (v1)   ")
    print("==============================================")
    print(f"Modèle : {engine.model}")
    print("Commandes : /quit, /clear, /model <nom>, /openfile <path>, /listfiles")
    print("----------------------------------------------")

    while True:
        user_summary = memory.get_user_info_summary()
        files_context = files.get_context_for_ai()
        user_input = input("\nVous : ").strip()

        if not user_input: continue

        if user_input.startswith('/'):
            parts = user_input.split(' ')
            cmd = parts[0].lower()
            if cmd == '/quit': break
            elif cmd == '/clear':
                confirm = input("Effacer l'historique ? (o/n) : ")
                if confirm.lower() == 'o': memory.clear()
                continue
            elif cmd == '/model':
                if len(parts) > 1:
                    engine.model = parts[1]
                    print(f"Modèle : {engine.model}")
                continue
            elif cmd == '/openfile':
                if len(parts) > 1:
                    success, msg = files.load_file(parts[1])
                    print(f"  [SYSTÈME: {msg}]")
                continue
            elif cmd == '/listfiles':
                print(f"  [SYSTÈME: {files.list_files()}]")
                continue
            elif cmd == '/closefile':
                if len(parts) > 1:
                    success, msg = files.close_file(parts[1])
                    print(f"  [SYSTÈME: {msg}]")
                continue
            elif cmd == '/reloadfile':
                if len(parts) > 1:
                    success, msg = files.load_file(parts[1])
                    print(f"  [SYSTÈME: {msg} (Rechargé)]")
                continue

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

        # Extraction
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
    # Par défaut: GUI. Si argument --console: Console.
    if "--console" in sys.argv:
        run_console(engine, memory)
    else:
        print("Lancement de l'interface graphique...")
        app = AnnaGUI(engine, memory)
        app.run()

if __name__ == "__main__":
    main()
