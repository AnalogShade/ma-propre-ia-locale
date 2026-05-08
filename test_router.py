import sys
import os
from file_manager import FileManager
from intent_router import IntentRouter

def run_tests():
    files = FileManager()
    router = IntentRouter()

    test_cases = [
        "Salut Anna, comment tu vas ?",
        "Je veux travailler dans le dossier C:\\Users\\Utilisateur\\Documents\\Dev\\ma propre ia locale",
        "Ouvre le fichier main.py",
        "Recharge le fichier",
        "Je regardais un fichier intéressant hier"
    ]

    print("\n--- DÉBUT DES TESTS DU ROUTEUR LLM-FIRST ---\n")

    for i, msg in enumerate(test_cases, 1):
        print(f"\n======================================")
        print(f"TEST {i}: {msg}")
        print(f"======================================")
        
        # Simulation du comportement de main.py
        result = router.process_intent(msg, files)
        
        print("\n--- RÉSULTAT OBTENU ---")
        print(f"Handled: {result.get('handled')}")
        print(f"Action retournée: {result.get('action')}")
        
        if result.get("handled"):
            print(f"Message Système: {result.get('message')}")
            print("Action: ARRÊT DU FLUX (Pas de réponse conversationnelle)")
        else:
            print("Action: FLUX NORMAL (L'IA répondra conversationnellement)")
        
        print(f"État FileManager -> Working Dir: {files.working_dir}")
        print(f"État FileManager -> Fichier Courant: {files.current_file_path}")

if __name__ == "__main__":
    run_tests()
