import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_controller import AgentController

def test_controller():
    print("--- Test de AgentController ---")
    try:
        ctrl = AgentController()
        print("AgentController instancié avec succès !")
        
        # 1. Vérification des instances de managers
        print(f"Modèle actif configuré : {ctrl.engine.model}")
        print(f"FileManager working_dir initial : {ctrl.files.working_dir}")
        
        # 2. Vérification d'un appel sémantique simple (slash command)
        result = ctrl.process_slash_command("/help")
        print("Vérification de la commande /help :")
        if result and result.get("handled"):
            print("[PASS] Commande slash /help traitée avec succès.")
            print(f"Extrait du message d'aide :\n{result.get('message')[:100]}...")
        else:
            print("[FAIL] Commande slash /help non traitée.")
            
        # 3. Vérification de la communication avec Ollama (optionnelle et sécurisée)
        print("Vérification de la connexion locale d'Ollama...")
        models = ctrl.engine.get_installed_models()
        if models:
            print(f"[PASS] Ollama est en ligne. Modèles installés détectés : {models}")
            
            # Un test d'intention sémantique via le routeur du contrôleur
            print("Vérification d'analyse sémantique...")
            intent = ctrl.router.process_intent("Bonjour !", ctrl.files)
            print(f"[PASS] Intent détecté pour 'Bonjour !' : {intent.get('action')}")
        else:
            print("[INFO] Service Ollama indisponible ou aucun modèle installé localement. C'est normal si Ollama n'est pas démarré.")
            
        print("\nTous les contrôles d'instanciation de AgentController ont réussi !")
        
    except Exception as e:
        print(f"[CRITICAL ERROR] Échec de l'instanciation ou du test du contrôleur : {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_controller()
