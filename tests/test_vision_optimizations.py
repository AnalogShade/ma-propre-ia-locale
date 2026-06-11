import sys
import os
import unittest
from PIL import Image

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from attachments import ImageAttachment
from ai_engine import AIEngine
from config import VISION_IMAGE_MAX_SIZE, VISION_IMAGE_JPEG_QUALITY

class TestVisionOptimizations(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.attachments_dir = os.path.join(self.test_dir, "temp_attachments")
        os.makedirs(self.attachments_dir, exist_ok=True)
        self.engine = AIEngine()

    def tearDown(self):
        import shutil
        if os.path.exists(self.attachments_dir):
            try:
                shutil.rmtree(self.attachments_dir)
            except Exception:
                pass

    def test_image_resizing_and_jpeg_conversion(self):
        # Create a large image (e.g. 1000x800)
        img = Image.new('RGB', (1000, 800), color='red')
        att = ImageAttachment(img)
        
        # Prepare for API
        path = att.prepare_for_api(self.attachments_dir)
        self.assertTrue(path.endswith('.jpg'))
        self.assertTrue(os.path.exists(path))
        
        # Verify size of saved image is resized
        with Image.open(path) as saved_img:
            w, h = saved_img.size
            self.assertEqual(w, VISION_IMAGE_MAX_SIZE)
            self.assertEqual(h, int(800 * (VISION_IMAGE_MAX_SIZE / 1000)))
        att.clean()

    def test_image_no_resizing_needed(self):
        # Create a small image (e.g. 200x150)
        img = Image.new('RGB', (200, 150), color='green')
        att = ImageAttachment(img)
        
        path = att.prepare_for_api(self.attachments_dir)
        self.assertTrue(path.endswith('.jpg'))
        
        with Image.open(path) as saved_img:
            w, h = saved_img.size
            self.assertEqual(w, 200)
            self.assertEqual(h, 150)
        att.clean()

    def test_default_prompt_injection(self):
        # Simulate send_message text injection logic
        has_image = True
        msg_empty = ""
        msg_spaces = "   \n "
        
        final_msg_empty = "Décris précisément l'image jointe." if has_image and not msg_empty.strip() else msg_empty
        final_msg_spaces = "Décris précisément l'image jointe." if has_image and not msg_spaces.strip() else msg_spaces
        
        self.assertEqual(final_msg_empty, "Décris précisément l'image jointe.")
        self.assertEqual(final_msg_spaces, "Décris précisément l'image jointe.")

    def test_evaluate_request_risk_fallback_no_gpu_or_model(self):
        # Test risk evaluation when nvidia-smi fails (returns None) or model size is None
        original_get_gpu_vram = self.engine.get_gpu_vram
        original_get_model_size = self.engine.get_model_size
        
        try:
            self.engine.get_gpu_vram = lambda: None
            self.engine.get_model_size = lambda m: None
            
            risk = self.engine.evaluate_request_risk("dummy_model", has_image=True)
            self.assertEqual(risk["level"], "moderate_risk")
            self.assertEqual(risk["confidence"], "low")
        finally:
            self.engine.get_gpu_vram = original_get_gpu_vram
            self.engine.get_model_size = original_get_model_size

    def test_evaluate_request_risk_calculation(self):
        # Mock AIEngine methods to return controlled values
        original_get_gpu_vram = self.engine.get_gpu_vram
        original_get_model_size = self.engine.get_model_size
        
        try:
            # Case 1: Low risk (VRAM = 8GB, Model = 3GB)
            # Model size (3GB) + Image extra (1.5GB) = 4.5GB < 8GB * 0.75 (6GB) -> low_risk
            self.engine.get_gpu_vram = lambda: 8.0
            self.engine.get_model_size = lambda m: 3.0
            risk = self.engine.evaluate_request_risk("dummy_model", has_image=True)
            self.assertEqual(risk["level"], "low_risk")
            self.assertEqual(risk["confidence"], "high")

            # Case 2: Moderate risk (VRAM = 6GB, Model = 3.5GB)
            # Model size (3.5GB) + Image extra (1.5GB) = 5.0GB > 6GB * 0.75 (4.5GB) but <= 6GB -> moderate_risk
            self.engine.get_gpu_vram = lambda: 6.0
            self.engine.get_model_size = lambda m: 3.5
            risk = self.engine.evaluate_request_risk("dummy_model", has_image=True)
            self.assertEqual(risk["level"], "moderate_risk")
            
            # Case 3: High risk (VRAM = 6GB, Model = 8GB)
            # Model size (8GB) + Image extra (1.5GB) = 9.5GB > 6GB -> high_risk
            self.engine.get_gpu_vram = lambda: 6.0
            self.engine.get_model_size = lambda m: 8.0
            risk = self.engine.evaluate_request_risk("dummy_model", has_image=True)
            self.assertEqual(risk["level"], "high_risk")
        finally:
            self.engine.get_gpu_vram = original_get_gpu_vram
            self.engine.get_model_size = original_get_model_size

    def test_on_start_callback_triggering(self):
        original_get_client = self.engine._get_client
        
        class MockClient:
            def chat(self, model, messages, stream=False):
                if stream:
                    def generator():
                        yield {"message": {"content": "Hello"}}
                    return generator()
                return {"message": {"content": "Hello"}}
                
        try:
            self.engine._get_client = lambda: MockClient()
            
            # Case 1: with stream (chunk_callback provided)
            callback_called = [False]
            def start_cb():
                callback_called[0] = True
                
            self.engine.get_response(
                context_messages=[{"role": "user", "content": "hi"}],
                chunk_callback=lambda x: None,
                on_start_callback=start_cb
            )
            self.assertTrue(callback_called[0])
            
            # Case 2: without stream (chunk_callback not provided)
            callback_called_sync = [False]
            def start_cb_sync():
                callback_called_sync[0] = True
                
            self.engine.get_response(
                context_messages=[{"role": "user", "content": "hi"}],
                on_start_callback=start_cb_sync
            )
            self.assertTrue(callback_called_sync[0])
            
        finally:
            self.engine._get_client = original_get_client

if __name__ == "__main__":
    unittest.main()
