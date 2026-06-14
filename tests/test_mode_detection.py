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

if __name__ == "__main__":
    unittest.main()
