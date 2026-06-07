import os
import sys
from PIL import Image
import ollama

def test_vision():
    # 1. Create a simple solid color image (blue square) to test vision
    test_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(test_dir, "test_color.png")
    
    print(f"Creating a temporary test image at: {img_path}")
    # Create a 200x200 solid blue image
    img = Image.new('RGB', (200, 200), color='blue')
    img.save(img_path)
    
    # 2. Test models in order
    models_to_test = ["gemma4:12b", "gemma4:latest"]
    
    for model in models_to_test:
        print(f"\n--- Testing vision capabilities with model '{model}' ---")
        try:
            # Let's perform a simple chat request with the image attached
            messages = [
                {
                    'role': 'user',
                    'content': 'What color is this solid square? Please answer in one word if possible.',
                    'images': [img_path]
                }
            ]
            print("Sending request to Ollama...")
            response = ollama.chat(model=model, messages=messages)
            
            content = response.get('message', {}).get('content', '')
            print(f"Success! Model response: {content.strip()}")
            
            # If we succeed, we can cleanup and exit successfully
            cleanup(img_path)
            return True
            
        except Exception as e:
            print(f"Error testing model '{model}': {e}")
            
    # Try generic 'gemma4' or check installed models if both failed
    print("\nAttempting to query installed models...")
    try:
        models_info = ollama.list()
        print("Installed models:")
        for m in models_info.get('models', []):
            name = m.get('model', m.get('name', ''))
            print(f"- {name}")
    except Exception as list_err:
        print(f"Could not retrieve model list from Ollama: {list_err}")
        
    cleanup(img_path)
    return False

def cleanup(path):
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"Cleaned up temporary image: {path}")
        except Exception as e:
            print(f"Failed to remove temporary image: {e}")

if __name__ == "__main__":
    success = test_vision()
    sys.exit(0 if success else 1)
