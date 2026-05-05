from ai_engine import AIEngine
from memory_manager import MemoryManager
from config import MODEL_NAME

def main():
    # Initialisation des composants
    engine = AIEngine()
    memory = MemoryManager()
    
    print("==============================================")
    print("   ANTIS - VOTRE IA LOCALE (v1)   ")
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

        # 4. Traitement de la conversation
        print(f"\nAntis ({engine.model}) : ", end="", flush=True)
        
        # On passe le résumé utilisateur pour que l'IA sache à qui elle parle
        response = engine.get_response(context, user_summary=user_summary)
        print(response)

        # 5. Mise à jour de la mémoire
        memory.add_message("user", user_input)
        memory.add_message("assistant", response)

        # 6. Extraction et classement automatique (Le "trieur")
        info = engine.extract_fact(user_input)
        if info and "categorie" in info:
            cat = info["categorie"].lower()
            cle = info["cle"]
            val = info["valeur"]

            if "user_profile" in cat:
                memory.update_user_profile(cle, val)
                print(f"  [Profil utilisateur mis à jour : {cle} = {val}]")
            elif "assistant_profile" in cat:
                memory.update_assistant_profile(cle, val)
                print(f"  [Profil assistant mis à jour : {cle} = {val}]")
            else:
                memory.add_fact(cle, val)
                print(f"  [Fait enregistré : {val}]")

if __name__ == "__main__":
    main()
