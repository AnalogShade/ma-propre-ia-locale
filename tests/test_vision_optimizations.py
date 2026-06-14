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

    def test_estimate_image_vision_cost_gb(self):
        # Test 1: very small image
        self.assertEqual(self.engine.estimate_image_vision_cost_gb(60, 60), 0.05)
        # Test 2: medium image
        self.assertEqual(self.engine.estimate_image_vision_cost_gb(300, 300), 0.15)
        # Test 3: large image
        self.assertEqual(self.engine.estimate_image_vision_cost_gb(700, 700), 0.35)
        # Test 4: very large image
        self.assertEqual(self.engine.estimate_image_vision_cost_gb(1000, 1000), 0.75)
        # Test 5: fallback for invalid values
        self.assertEqual(self.engine.estimate_image_vision_cost_gb(None, 0), 0.35)

    def test_evaluate_request_risk_calculation(self):
        # Mock AIEngine methods to return controlled values
        original_get_gpu_vram = self.engine.get_gpu_vram
        original_get_model_size = self.engine.get_model_size
        
        try:
            # Case 1: Low risk (VRAM = 8GB, Model = 3GB, small image 60x60)
            # Model size (3GB) + Image (0.05GB) = 3.05GB. Ratio = 3.05/8 = 0.38 < 0.90 -> low_risk
            self.engine.get_gpu_vram = lambda: 8.0
            self.engine.get_model_size = lambda m: 3.0
            risk = self.engine.evaluate_request_risk("dummy_model", image_infos=[{"width": 60, "height": 60, "file_size_kb": 8.0}])
            self.assertEqual(risk["level"], "low_risk")
            self.assertEqual(risk["confidence"], "high")

            # Case 2: Moderate risk (VRAM = 6GB, Model = 5.5GB, small image 60x60)
            # Model size (5.5GB) + Image (0.05GB) = 5.55GB. Ratio = 5.55/6 = 0.925 (between 0.90 and 1.35) -> moderate_risk
            self.engine.get_gpu_vram = lambda: 6.0
            self.engine.get_model_size = lambda m: 5.5
            risk = self.engine.evaluate_request_risk("dummy_model", image_infos=[{"width": 60, "height": 60, "file_size_kb": 8.0}])
            self.assertEqual(risk["level"], "moderate_risk")
            self.assertEqual(risk["reason"], "Modèle légèrement supérieur à la VRAM détectée, mais image très petite.")
            
            # Case 3: High risk due to high ratio (VRAM = 6GB, Model = 8.5GB, small image 60x60)
            # Model size (8.5GB) + Image (0.05GB) = 8.55GB. Ratio = 8.55/6 = 1.425 >= 1.35 -> high_risk
            self.engine.get_gpu_vram = lambda: 6.0
            self.engine.get_model_size = lambda m: 8.5
            risk = self.engine.evaluate_request_risk("dummy_model", image_infos=[{"width": 60, "height": 60, "file_size_kb": 8.0}])
            self.assertEqual(risk["level"], "high_risk")

            # Case 4: Low VRAM escalation (VRAM = 3GB, Model = 2GB, medium image 200x200)
            # VRAM <= 4.0 and Model (2.0) is not heavy (2.0 < 3.0*0.9=2.7), but image is medium (200x200, pixels > 128*128).
            # So VRAM low and image medium/large -> high_risk escalation.
            self.engine.get_gpu_vram = lambda: 3.0
            self.engine.get_model_size = lambda m: 2.0
            risk = self.engine.evaluate_request_risk("dummy_model", image_infos=[{"width": 200, "height": 200, "file_size_kb": 20.0}])
            self.assertEqual(risk["level"], "high_risk")

            # Case 5: Low VRAM no escalation (VRAM = 3GB, Model = 1.5GB, small image 60x60)
            # VRAM <= 4.0, Model (1.5) not heavy, image is small -> no escalation.
            # Ratio = (1.5 + 0.05)/3 = 0.517. With low VRAM penalty: 0.517 + 0.15 = 0.667 < 0.90 -> low_risk
            self.engine.get_gpu_vram = lambda: 3.0
            self.engine.get_model_size = lambda m: 1.5
            risk = self.engine.evaluate_request_risk("dummy_model", image_infos=[{"width": 60, "height": 60, "file_size_kb": 8.0}])
            self.assertEqual(risk["level"], "low_risk")

            # Case 6: Large image and heavy model escalation (VRAM = 6GB, Model = 5.5GB, large image 700x700)
            # VRAM = 6.0, Model (5.5) >= 5.4 (heavy). Image dimension (700) >= 600 (large).
            # Under ratio, it would be moderate (ratio = (5.5 + 0.35)/6 = 0.975), but it escalates to high_risk.
            self.engine.get_gpu_vram = lambda: 6.0
            self.engine.get_model_size = lambda m: 5.5
            risk = self.engine.evaluate_request_risk("dummy_model", image_infos=[{"width": 700, "height": 700, "file_size_kb": 50.0}])
            self.assertEqual(risk["level"], "high_risk")

            # Case 7: Multiple medium/large images escalation (VRAM = 6GB, Model = 5.5GB, two medium images 200x200)
            # Model is heavy (5.5 >= 5.4). Two medium images (pixels > 128*128). Escalates to high_risk.
            self.engine.get_gpu_vram = lambda: 6.0
            self.engine.get_model_size = lambda m: 5.5
            risk = self.engine.evaluate_request_risk("dummy_model", image_infos=[
                {"width": 200, "height": 200, "file_size_kb": 20.0},
                {"width": 200, "height": 200, "file_size_kb": 20.0}
            ])
            self.assertEqual(risk["level"], "high_risk")

            # Case 8: Backward compatibility with boolean has_image=True
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
            def chat(self, model, messages, stream=False, options=None):
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
