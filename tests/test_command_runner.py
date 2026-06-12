import unittest
import os
import tempfile
import time
from command_runner import CommandRunner

class TestCommandRunner(unittest.TestCase):
    def setUp(self):
        self.runner = CommandRunner()

    def test_parse_command_blocks(self):
        text = """
Voici ma proposition :
<<<<<<< EXECUTE_COMMAND
python --version
>>>>>>> EXECUTE_COMMAND
J'espère que ça aide !
"""
        blocks = self.runner.parse_command_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["command"], "python --version")

    def test_parse_multiple_command_blocks(self):
        text = """
<<<<<<< EXECUTE_COMMAND
echo "hello"
>>>>>>> EXECUTE_COMMAND
Puis :
<<<<<<< EXECUTE_COMMAND
echo "world"
>>>>>>> EXECUTE_COMMAND
"""
        blocks = self.runner.parse_command_blocks(text)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["command"], 'echo "hello"')
        self.assertEqual(blocks[1]["command"], 'echo "world"')

    def test_validate_command_blacklist(self):
        # Tester une commande valide
        is_valid, msg = self.runner.validate_command("python main.py", tempfile.gettempdir())
        self.assertTrue(is_valid, msg)
        
        # Tester des commandes interdites par la blacklist
        for cmd in ["rm -rf /", "del /f /s /q test.txt", "shutdown -s", "format c:"]:
            is_valid, msg = self.runner.validate_command(cmd, tempfile.gettempdir())
            self.assertFalse(is_valid, f"Devrait rejeter : {cmd}")
            self.assertIn("politique de sécurité", msg)

    def test_validate_command_empty_working_dir(self):
        is_valid, msg = self.runner.validate_command("python main.py", "")
        self.assertFalse(is_valid)
        self.assertIn("répertoire de travail", msg)

    def test_execute_async(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_received = []
            complete_status = {}
            
            def on_output(text):
                output_received.append(text)
                
            def on_complete(return_code, stdout, stderr, is_cancelled):
                complete_status['code'] = return_code
                complete_status['stdout'] = stdout
                complete_status['stderr'] = stderr
                complete_status['cancelled'] = is_cancelled

            pid = self.runner.execute_async(
                "echo hello_test",
                tmpdir,
                on_output,
                on_complete
            )
            
            self.assertIsNotNone(pid)
            
            # Attendre que la commande se termine (devrait être quasi instantané)
            timeout = 5
            start_time = time.time()
            while 'code' not in complete_status and time.time() - start_time < timeout:
                time.sleep(0.1)
                
            self.assertIn('code', complete_status)
            self.assertEqual(complete_status['code'], 0)
            self.assertIn("hello_test", "".join(output_received))

if __name__ == "__main__":
    unittest.main()
