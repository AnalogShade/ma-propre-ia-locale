import sys
import os
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_controller import AgentController

class TestModeDetection(unittest.TestCase):
    def setUp(self):
        self.ctrl = AgentController()

    def test_default_chat_mode(self):
        # Sans fichier ouvert, sans action spécifique et sans mots-clés techniques
        mode, reason = self.ctrl.detect_working_mode("Bonjour Anna ! Comment vas-tu aujourd'hui ?", "none")
        self.assertEqual(mode, "CHAT")
        self.assertIn("Aucun fichier ouvert", reason)

    def test_code_mode_by_files(self):
        # Règle 1 : Avec des fichiers ouverts
        self.ctrl.files.loaded_files = {"main.py": {"content": "print('hello')", "numbered": "1: print('hello')"}}
        mode, reason = self.ctrl.detect_working_mode("Salut Anna !", "none")
        self.assertEqual(mode, "CODE")
        self.assertIn("Fichier(s) ouvert(s)", reason)

    def test_code_mode_by_intent(self):
        # Règle 2 : Sans fichier mais avec intention technique détectée
        self.ctrl.files.loaded_files = {}
        mode, reason = self.ctrl.detect_working_mode("Ouvre le fichier", "load_context")
        self.assertEqual(mode, "CODE")
        self.assertIn("Intention technique détectée", reason)

    def test_code_mode_by_keywords(self):
        # Règle 3 : Sans fichier, sans intention détectée par le routeur, mais avec mots-clés techniques
        self.ctrl.files.loaded_files = {}
        
        # Test avec "python"
        mode, reason = self.ctrl.detect_working_mode("Peux-tu m'expliquer comment marche une boucle en python ?", "none")
        self.assertEqual(mode, "CODE")
        self.assertIn("Mots-clés techniques détectés", reason)
        self.assertIn("python", reason)
        self.assertIn("boucle", reason)

        # Test avec "classe"
        mode, reason = self.ctrl.detect_working_mode("Crée une classe pour gérer le plateau", "none")
        self.assertEqual(mode, "CODE")
        self.assertIn("Mots-clés techniques", reason)
        self.assertIn("classe", reason)

    def test_semantic_intent_workspace_query(self):
        # "Liste les fichiers du dossier" -> WORKSPACE_QUERY, CHAT
        mode, reason = self.ctrl.detect_working_mode("Liste les fichiers du dossier", "none", semantic_intent="WORKSPACE_QUERY")
        self.assertEqual(mode, "CHAT")
        self.assertIn("Intention sémantique détectée", reason)

    def test_semantic_intent_command_execution(self):
        # "Lance les tests unitaires" -> COMMAND_EXECUTION, CHAT
        mode, reason = self.ctrl.detect_working_mode("Lance les tests unitaires", "none", semantic_intent="COMMAND_EXECUTION")
        self.assertEqual(mode, "CHAT")
        self.assertIn("Intention sémantique détectée", reason)

    def test_semantic_intent_code_analysis(self):
        # "Analyse main.py" -> CODE_ANALYSIS, CODE
        mode, reason = self.ctrl.detect_working_mode("Analyse main.py", "load_context", semantic_intent="CODE_ANALYSIS")
        self.assertEqual(mode, "CODE")
        self.assertIn("Intention sémantique détectée", reason)

    def test_semantic_intent_code_modification(self):
        # "Corrige le bug dans main.py" etc. -> CODE_MODIFICATION, CODE
        for phrase in [
            "Corrige le bug dans main.py",
            "Modifie main.py pour ajouter un bouton",
            "Crée un nouveau fichier config.py",
            "Ajoute une fonction de sauvegarde dans file_manager.py",
            "Refactorise cette classe sans changer son comportement"
        ]:
            mode, reason = self.ctrl.detect_working_mode(phrase, "load_context", semantic_intent="CODE_MODIFICATION")
            self.assertEqual(mode, "CODE", f"Échec pour la phrase : {phrase}")
            self.assertIn("Intention sémantique", reason)
            
    def test_fallback_when_semantic_intent_is_none(self):
        # Sans semantic_intent, vérifie le fonctionnement de l'heuristique
        self.ctrl.files.loaded_files = {}
        mode, reason = self.ctrl.detect_working_mode("liste des fichiers", "none", semantic_intent=None)
        # "fichiers" est dans technical_keywords
        self.assertEqual(mode, "CODE")
        self.assertIn("Mots-clés techniques", reason)

if __name__ == "__main__":
    unittest.main()
