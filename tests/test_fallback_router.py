import sys
import os
import shutil
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_controller import AgentController

def test_fallback_routing():
    print("\n--- DEBUT DES TESTS DE LA COUCHE DE SAFETY FALLBACK (LLM-FIRST) ---\n")
    
    # 1. Préparer un répertoire de test temporaire avec des fichiers fictifs
    temp_dir = Path(__file__).parent / "temp_fallback_test_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Créer index.html et style.css
    (temp_dir / "index.html").write_text("<!DOCTYPE html><html><body><h1>Test</h1></body></html>", encoding="utf-8")
    (temp_dir / "style.css").write_text("body { background-color: white; }", encoding="utf-8")
    
    try:
        ctrl = AgentController()
        ctrl.clear_history()
        
        # S'assurer qu'Ollama est disponible avant de faire les tests LLM
        models = ctrl.engine.get_installed_models()
        if not models:
            print("[INFO] Ollama n'est pas démarré ou aucun modèle n'est installé. Passage des assertions LLM.")
            return
            
        print(f"Modèle de test actif : {ctrl.engine.model}")
        
        # Définir le répertoire de travail
        print(f"\n[ÉTAPE 1] Définition du répertoire de travail sur {temp_dir}...")
        res = ctrl.process_user_message_sync(f"commence par aller dans ce dossier {temp_dir.resolve()}")
        print(f"Résultat : {res.get('message')}")
        assert ctrl.files.working_dir is not None, "Le working_dir devrait être défini !"
        
        # Fermer tout fichier éventuellement ouvert
        ctrl.files.close_all_files()
        assert len(ctrl.files.loaded_files) == 0, "Aucun fichier ne doit être chargé au départ."
        
        # Test 1: Demande implicite nécessitant style.css
        print("\n[ÉTAPE 2] Test d'une demande implicite : 'modifie le style pour avoir un thème plus sombre'...")
        # On utilise une callback factice pour logger l'avancement
        def status_cb(status):
            print(f"  [Status] {status}")
            
        res2 = ctrl.process_user_message_sync("modifie le style pour avoir un thème plus sombre", status_callback=status_cb)
        print(f"Type de réponse : {res2.get('type')}")
        print(f"Notification système : {res2.get('system_notification')}")
        print(f"Fichiers chargés après traitement : {list(ctrl.files.loaded_files.keys())}")
        
        # Assertion : style.css doit être chargé automatiquement via le fallback
        assert "style.css" in ctrl.files.loaded_files, "style.css aurait dû être chargé automatiquement via le fallback !"
        print("[PASS] Le fallback a correctement identifié et chargé style.css !")
        
        # Test 2: Demande générale (non liée au projet)
        ctrl.files.close_all_files()
        print("\n[ÉTAPE 3] Test d'une demande générale : 'comment ça va ?'...")
        res3 = ctrl.process_user_message_sync("comment ça va ?", status_callback=status_cb)
        print(f"Type de réponse : {res3.get('type')}")
        print(f"Fichiers chargés après traitement : {list(ctrl.files.loaded_files.keys())}")
        
        # Assertion : Aucun fichier ne doit être chargé
        assert len(ctrl.files.loaded_files) == 0, "Aucun fichier ne doit être chargé pour une salutation !"
        print("[PASS] Le fallback a ignoré correctement la demande générale sans charger de fichier !")
        
        # Test 3: Commande explicite d'origine (non-régression)
        ctrl.files.close_all_files()
        print("\n[ÉTAPE 4] Test d'une commande explicite d'origine : 'Recharge le fichier'...")
        # Note : On simule l'existence d'un fichier actif d'abord
        ctrl.files.load_file("style.css")
        res4 = ctrl.process_user_message_sync("recharge le fichier", status_callback=status_cb)
        print(f"Type de réponse : {res4.get('type')}")
        print(f"Notification système : {res4.get('system_notification')}")
        print("[PASS] Commande explicite traitée avec succès !")
        
        print("\n=== TOUS LES TESTS DE SAFETY FALLBACK ONT RÉUSSI ! ===")
        
    finally:
        # Nettoyage
        if 'ctrl' in locals():
            try:
                ctrl.files.close_all_files()
                ctrl.files.working_dir = None
            except Exception:
                pass
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_fallback_routing()
