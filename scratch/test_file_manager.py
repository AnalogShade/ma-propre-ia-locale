import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from file_manager import FileManager

def setup_test_env():
    test_dir = Path("scratch/test_project")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    file1 = test_dir / "hello.py"
    file1.write_text("print('Hello')\nprint('World')\n# A comment\ndef foo():\n    pass\n", encoding='utf-8')
    
    return test_dir

def test_file_manager():
    print("--- Test de FileManager v2 ---")
    fm = FileManager()
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
    
    # 4. Test replace_lines
    mod = {
        "action": "replace_lines",
        "file": "hello.py",
        "start_line": 4,
        "end_line": 5,
        "new_content": "def foo():\n    print('Modified foo')",
        "reason": "Test de modification de fonction"
    }
    success, result = fm.apply_modification(mod)
    print(f"Apply replace_lines: {success}")
    if success:
        print(f"  Summary: {result['summary']}")
        print(f"  Backup: {result['backup']}")
        content = Path(result['file']).read_text(encoding='utf-8')
        print("New content:\n" + content)

    # 5. Test replace_text (success)
    mod_text = {
        "action": "replace_text",
        "file": "hello.py",
        "target_text": "print('World')",
        "new_text": "print('Anna')",
        "reason": "Changement de nom"
    }
    success, result = fm.apply_modification(mod_text)
    print(f"Apply replace_text: {success} | {result.get('summary') if success else result}")
    
    # 6. Test replace_text (failure: multiple occurrences)
    file_mult = test_dir / "mult.txt"
    file_mult.write_text("aaa\naaa\naaa\n", encoding='utf-8')
    mod_mult = {
        "action": "replace_text",
        "file": "mult.txt",
        "target_text": "aaa",
        "new_text": "bbb"
    }
    success, result = fm.apply_modification(mod_mult)
    print(f"Apply replace_text (multiple): {success} (Expected: False) | {result}")

    # 7. Test security (outside working_dir)
    success, msg = fm.load_file("../../main.py")
    print(f"Security test (load outside): Success={success} | Msg={msg}")

    # 8. Test insert_after_line
    mod_ins = {
        "action": "insert_after_line",
        "file": "hello.py",
        "line": 1,
        "new_content": "print('After line 1')",
        "reason": "Test insertion"
    }
    success, result = fm.apply_modification(mod_ins)
    print(f"Apply insert_after_line: {success} | {result.get('summary') if success else result}")

    # 9. Test insert_before_line
    mod_before = {
        "action": "insert_before_line",
        "file": "hello.py",
        "line": 1,
        "new_content": "# File Header",
        "reason": "Test insertion before"
    }
    success, result = fm.apply_modification(mod_before)
    print(f"Apply insert_before_line: {success} | {result.get('summary') if success else result}")
    
    if success:
        print("Final content:\n" + Path(result['file']).read_text(encoding='utf-8'))

if __name__ == "__main__":
    test_file_manager()
