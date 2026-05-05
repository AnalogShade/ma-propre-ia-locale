from ai_engine import AIEngine
from memory_manager import MemoryManager
from config import MODEL_NAME

def main():
    # Initialisation des composants
    engine = AIEngine()
    memory = MemoryManager()
    
    # Récupération du nom de l'assistant (Priorité au profil)
    assistant_name = memory.assistant_profile.get("nom", "Antis")

    print("==============================================")
    print(f"   {assistant_name.upper()} - VOTRE IA LOCALE (v1)   ")
    print("==============================================")
    print(f"Modèle : {engine.model}")
    print("Commandes : /quit, /clear, /model <nom>")
    print("----------------------------------------------")

    while True:
        # 1. Préparation du contexte (Profil + Historique)
        user_summary = memory.get_user_info_summary()
        context = memory.get_context()

        # 2. Entrée utilisateur
        user_input = input("\nVous : ").strip()

        if not user_input:
            continue

        # 3. Gestion des commandes
        if user_input.startswith('/'):
            parts = user_input.split(' ')
            cmd = parts[0].lower()

            if cmd == '/quit':
                print("Au revoir !")
                break
            elif cmd == '/clear':
                confirm = input("Effacer l'historique court terme ? (o/n) : ")
                if confirm.lower() == 'o':
                    memory.clear()
                continue
            elif cmd == '/model':
                if len(parts) > 1:
                    engine.model = parts[1]
                    print(f"Modèle : {engine.model}")
                continue

        # 4. GÉNÉRATION DE LA RÉPONSE
        assistant_name = memory.assistant_profile.get("nom", "Antis")
        print(f"\n{assistant_name} ({engine.model}) : ", end="", flush=True)
        
        response = engine.get_response(context, user_summary=user_summary, assistant_name=assistant_name)
        
        # Fallback si l'IA ne répond rien
        if not response:
            user_name = memory.user_profile.get("prénom", memory.user_profile.get("nom", "Louis"))
            response = f"Salut {user_name}, je suis là. (Ollama n'a pas renvoyé de texte)"
            
        print(response)

        # 5. MISE À JOUR DE LA MÉMOIRE (Conversation)
        memory.add_message("user", user_input)
        memory.add_message("assistant", response)

        # 6. EXTRACTION SECONDAIRE (En arrière-plan du flux principal)
        info = engine.extract_fact(user_input)
        if info and "categorie" in info:
            cat = info["categorie"].lower()
            cle = info["cle"]
            val = info["valeur"]

            if cat == "user_profile":
                memory.update_user_profile(cle, val)
                print(f"  [LOG: Profil utilisateur -> {cle}: {val}]")
            elif cat == "assistant_profile":
                memory.update_assistant_profile(cle, val)
                print(f"  [LOG: Profil assistant -> {cle}: {val}]")
            else:
                memory.add_fact(cle, val)
                print(f"  [LOG: Fait -> {val}]")
        elif info:
            print(f"  [DEBUG: L'IA a renvoyé un format inconnu : {info}]")

if __name__ == "__main__":
    main()
