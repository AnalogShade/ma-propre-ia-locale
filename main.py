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
        # 1. Entrée utilisateur
        user_input = input("\nVous : ").strip()

        if not user_input:
            continue

        # 2. Gestion des commandes spécialisées
        if user_input.startswith('/'):
            parts = user_input.split(' ')
            cmd = parts[0].lower()

            if cmd == '/quit':
                print("Au revoir !")
                break

            elif cmd == '/clear':
                confirm = input("Voulez-vous vraiment effacer la mémoire ? (o/n) : ")
                if confirm.lower() == 'o':
                    memory.clear()
                    print("Mémoire réinitialisée.")
                continue

            elif cmd == '/model':
                if len(parts) > 1:
                    new_model = parts[1]
                    engine.model = new_model
                    print(f"Modèle changé pour : {new_model}")
                else:
                    print("Usage: /model <nom_du_modele>")
                continue

        # 3. Traitement de la conversation
        # On ajoute le message de l'utilisateur à la mémoire
        memory.add_message("user", user_input)

        # On récupère les derniers messages pour donner du contexte à l'IA
        context = memory.get_context()

        # On affiche le début de la réponse
        print(f"\nAntis ({engine.model}) : ", end="", flush=True)
        
        # On demande la réponse à Ollama
        response = engine.get_response(context)
        print(response)

        # On enregistre la réponse de l'IA dans la mémoire
        memory.add_message("assistant", response)

if __name__ == "__main__":
    main()
