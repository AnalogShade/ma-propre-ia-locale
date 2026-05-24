import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from file_manager import FileManager
from code_editor import CodeEditor

def setup_test_env():
    test_dir = Path("tests/test_project")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    file1 = test_dir / "hello.py"
    file1.write_text("print('Hello')\nprint('World')\n# A comment\ndef foo():\n    pass\n", encoding='utf-8')
    
    return test_dir

def test_file_manager_and_editor():
    print("--- Test de FileManager & CodeEditor ---")
    fm = FileManager()
    editor = CodeEditor()
    test_dir = setup_test_env()
    
    # 1. Test set_working_dir
    success, msg = fm.set_working_dir(test_dir)
    print(f"Set working dir: {success} | {msg}")
    
    # 2. Test load_file (relatif)
    success, msg = fm.load_file("hello.py")
    print(f"Load hello.py: {success} | {msg}")
    
    # 3. Test context for AI (line numbers)
    context = fm.get_context_for_ai()
    print("Context for AI preview:")
    print(context[:200] + "...")
    
    # 4. Test CodeEditor - create_file
    new_file_path = "tests/test_project/new_file.py"
    success, msg = editor.create_file(new_file_path, "print('New file!')", working_dir=fm.working_dir)
    print(f"CodeEditor create_file: {success} | {msg}")
    
    # 5. Test CodeEditor - apply_edit (Search & Replace)
    abs_hello_path = (test_dir / "hello.py").resolve()
    search_text = "print('World')"
    replace_text = "print('Anna')"
    success, msg = editor.apply_edit(abs_hello_path, search_text, replace_text)
    print(f"CodeEditor apply_edit: {success} | {msg}")
    
    # Vérification du nouveau contenu de hello.py
    if success:
        content = Path(abs_hello_path).read_text(encoding='utf-8')
        print("Nouveau contenu de hello.py :\n" + content)

    # 6. Test de sécurité (lecture hors du working_dir)
    success, msg = fm.load_file("../../main.py")
    print(f"Test de sécurité (chargement hors limite): Succès={success} (Attendu: False) | Msg={msg}")

    # 7. Test de sécurité (écriture hors du working_dir via CodeEditor)
    success, msg = editor.create_file("../../outside.py", "print('Malicious')", working_dir=fm.working_dir)
    print(f"Test de sécurité (écriture hors limite): Succès={success} (Attendu: False) | Msg={msg}")

if __name__ == "__main__":
    test_file_manager_and_editor()
