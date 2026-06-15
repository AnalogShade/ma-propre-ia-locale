import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_engine import AIEngine
from agent_controller import AgentController

class TestStreamRobustness(unittest.TestCase):
    def setUp(self):
        self.engine = AIEngine()
        self.ctrl = AgentController()

    @patch('ollama.Client')
    def test_normal_streaming(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_chunks = [
            {'message': {'content': 'Hello'}},
            {'message': {'content': ' world'}},
            {'message': {'content': '!'}}
        ]
        mock_client.chat.return_value = mock_chunks

        received_chunks = []
        received_status = []

        def chunk_cb(c):
            received_chunks.append(c)

        def status_cb(s):
            received_status.append(s)

        response = self.engine.get_response(
            context_messages=[{'role': 'user', 'content': 'hi'}],
            chunk_callback=chunk_cb,
            status_callback=status_cb
        )

        self.assertEqual(response, "Hello world!")
        self.assertEqual(received_chunks, ["Hello", " world", "!"])
        self.assertIn("Envoi au modèle...", received_status)

    @patch('ollama.Client')
    def test_streaming_fallback_on_exception(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        def side_effect(*args, **kwargs):
            if kwargs.get('stream'):
                raise RuntimeError("Stream failed")
            else:
                return {'message': {'content': 'Hello sync world!'}}

        mock_client.chat.side_effect = side_effect

        received_chunks = []
        received_status = []

        def chunk_cb(c):
            received_chunks.append(c)

        def status_cb(s):
            received_status.append(s)

        response = self.engine.get_response(
            context_messages=[{'role': 'user', 'content': 'hi'}],
            chunk_callback=chunk_cb,
            status_callback=status_cb
        )

        self.assertEqual(response, "Hello sync world!")
        self.assertEqual(received_chunks, ["Hello sync world!"])
        self.assertTrue(any("Repli synchrone" in s for s in received_status))

    def test_split_response_with_think_tags(self):
        # Simulate gui's split_response function
        from gui import AnnaGUI
        # Initialize GUI in a mock/dummy way (or create a dummy class with the same method to test)
        # Since AnnaGUI needs tk.Tk(), we can just import and call the method on a dummy object or mock
        gui = MagicMock()
        gui.split_response = AnnaGUI.split_response.__get__(gui, MagicMock)
        
        # Test closed tag
        think, final = gui.split_response("abc<think>def</think>ghi")
        self.assertEqual(think, "def")
        self.assertEqual(final, "abcghi")

        # Test unclosed tag
        think, final = gui.split_response("abc<think>def")
        self.assertEqual(think, "def")
        self.assertEqual(final, "abc")

        # Test no tag
        think, final = gui.split_response("abcghi")
        self.assertEqual(think, "")
        self.assertEqual(final, "abcghi")

    @patch('ollama.Client')
    @patch('ollama.chat')
    def test_controller_response_cleaning(self, mock_chat, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        # Setup mock return response with think tags
        mock_response = {
            'message': {
                'content': '<think>I am thinking about code.</think>FILE: main.py\n<<<<<<< CREATE\nprint("hi")\n>>>>>>> CREATE'
            }
        }
        mock_client.chat.return_value = mock_response
        mock_chat.return_value = mock_response
        
        # Clear memory messages before test
        self.ctrl.memory.clear()
        
        result = self.ctrl.process_user_message_sync("hello")
        
        # Verify the returned content is cleaned
        self.assertNotIn("<think>", result.get("content"))
        self.assertNotIn("thinking about code", result.get("content"))
        self.assertIn("FILE: main.py", result.get("content"))
        
        # Verify memory message is cleaned
        last_msg = self.ctrl.memory.get_context()[-1]
        self.assertEqual(last_msg["role"], "assistant")
        self.assertNotIn("<think>", last_msg["content"])
        self.assertIn("FILE: main.py", last_msg["content"])
        
        # Verify diff blocks are parsed correctly from cleaned response
        self.assertEqual(len(result.get("create_blocks")), 1)
        self.assertEqual(result.get("create_blocks")[0]["file_path"], "main.py")

    @patch('ollama.Client')
    def test_native_thinking_stream(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_chunks = [
            {'message': {'thinking': 'Thinking'}},
            {'message': {'thinking': ' process'}},
            {'message': {'content': 'Final response'}}
        ]
        mock_client.chat.return_value = mock_chunks

        received_chunks = []

        def chunk_cb(c):
            received_chunks.append(c)

        response = self.engine.get_response(
            context_messages=[{'role': 'user', 'content': 'hi'}],
            chunk_callback=chunk_cb
        )

        self.assertEqual(response, "<think>Thinking process</think>Final response")
        self.assertEqual(received_chunks, ["<think>", "Thinking", " process", "</think>", "Final response"])

    @patch('ollama.Client')
    @patch('ollama.chat')
    def test_multiple_and_unclosed_think_tags_cleaning(self, mock_chat, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Test case 1: Multiple closed think tags
        mock_response = {
            'message': {
                'content': '<think>Think 1</think>Content 1<think>Think 2</think>Content 2'
            }
        }
        mock_client.chat.return_value = mock_response
        mock_chat.return_value = mock_response
        self.ctrl.memory.clear()
        
        result = self.ctrl.process_user_message_sync("hello")
        self.assertEqual(result.get("content").strip(), "Content 1Content 2")
        
        # Test case 2: Unclosed think tag at the end (e.g. cut off)
        mock_response_unclosed = {
            'message': {
                'content': '<think>Think 1</think>Content 1<think>Think 2 unclosed...'
            }
        }
        mock_client.chat.return_value = mock_response_unclosed
        mock_chat.return_value = mock_response_unclosed
        
        result_unclosed = self.ctrl.process_user_message_sync("hello again")
        self.assertEqual(result_unclosed.get("content").strip(), "Content 1")

    @patch('ollama.Client')
    def test_silenced_streaming_during_auto_correction(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        def chat_side_effect(*args, **kwargs):
            if kwargs.get('stream'):
                return [
                    {'message': {'content': 'FILE: main.py\n'}},
                    {'message': {'content': '<<<<<<< SEARCH\nbody {\n    ...\n}\n=======\nbody {\n    color: red;\n}\n>>>>>>> REPLACE'}}
                ]
            else:
                return {
                    'message': {
                        'content': 'FILE: main.py\n<<<<<<< SEARCH\nbody {\n    margin: 0;\n}\n=======\nbody {\n    color: red;\n}\n>>>>>>> REPLACE'
                    }
                }
        mock_client.chat.side_effect = chat_side_effect
        
        received_chunks = []
        def chunk_cb(c):
            received_chunks.append(c)
            
        self.ctrl.memory.clear()

        
        original_get_response = self.ctrl.engine.get_response
        captured_callbacks = []
        
        def mock_get_response(*args, **kwargs):
            captured_callbacks.append(kwargs.get('chunk_callback'))
            return original_get_response(*args, **kwargs)
            
        with patch.object(self.ctrl.engine, 'get_response', side_effect=mock_get_response):
            self.ctrl.process_user_message_sync("hello", chunk_callback=chunk_cb)
            
        self.assertEqual(captured_callbacks[0], chunk_cb)
        self.assertIsNone(captured_callbacks[1])

    @patch('ollama.Client')
    def test_controller_timeout_message(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        import httpx
        mock_client.chat.side_effect = httpx.TimeoutException("Mocked timeout")
        
        self.ctrl.memory.clear()
        
        result = self.ctrl.process_user_message_sync("hello")
        
        content = result.get("content")
        self.assertIn("expiré (timeout)", content)
        self.assertIn("VRAM swapping", content)
        self.assertIn("ollama_request_timeout", content)
        self.assertEqual(result.get("type"), "text")

if __name__ == '__main__':
    unittest.main()


