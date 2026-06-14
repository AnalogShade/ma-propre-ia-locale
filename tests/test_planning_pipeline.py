import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_controller import AgentController
from planning_agent import PlanningAgent

class TestPlanningPipeline(unittest.TestCase):
    def setUp(self):
        self.ctrl = AgentController()
        # Configurer le get_response de l'engine pour renvoyer une réponse par défaut
        self.ctrl.engine.get_response = MagicMock(return_value="Réponse de test")

    @patch('planning_agent.PlanningAgent.generate_plan')
    def test_planning_not_called_in_chat_mode(self, mock_generate_plan):
        # Sans fichier ouvert et sans mot-clé technique -> Mode.CHAT
        self.ctrl.files.loaded_files = {}
        
        # Message CHAT
        result = self.ctrl.process_user_message_sync("Bonjour ! Comment ça va ?", status_callback=lambda x: None)
        
        # L'agent de planification ne doit pas être appelé en mode CHAT
        mock_generate_plan.assert_not_called()
        self.assertNotIn("Plan", result.get("content", ""))

    @patch('planning_agent.PlanningAgent.generate_plan')
    def test_planning_called_in_code_mode(self, mock_generate_plan):
        # Avec fichier ouvert -> Mode.CODE
        self.ctrl.files.loaded_files = {
            "main.py": {"content": "print('hello')", "numbered": "1: print('hello')"}
        }
        
        mock_generate_plan.return_value = "<details><summary>📋 Plan</summary>Plan de test</details>"
        
        # Message CODE
        result = self.ctrl.process_user_message_sync("Corrige le fichier main.py", status_callback=lambda x: None)
        
        # L'agent de planification doit être appelé
        mock_generate_plan.assert_called_once()
        # Le plan doit être injecté au début du contenu final
        self.assertTrue(result.get("content", "").startswith("<details><summary>📋 Plan</summary>Plan de test</details>"))

    def test_planning_agent_generate_plan_direct(self):
        # Test direct de la méthode de génération de plan
        mock_engine = MagicMock()
        mock_engine.system_prompt = "original_prompt"
        mock_engine.get_response.return_value = "Plan brut avec <think>de la reflexion</think> et le plan final."
        
        plan = PlanningAgent.generate_plan(
            engine=mock_engine,
            context_messages=[],
            files_context="context",
            user_summary="",
            assistant_summary=""
        )
        
        # Le prompt d'origine doit être restauré
        self.assertEqual(mock_engine.system_prompt, "original_prompt")
        # Les balises <think> doivent être supprimées
        self.assertNotIn("<think>", plan)
        self.assertIn("Plan brut avec  et le plan final.", plan)

if __name__ == "__main__":
    unittest.main()
