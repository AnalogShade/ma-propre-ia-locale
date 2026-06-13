import sys
import os
import shutil
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from code_editor import CodeEditor

def test_patch_validator():
    print("\n--- DEBUT DES TESTS DE LA VALIDATION STRICTE DES PATCHES (SEARCH/REPLACE) ---\n")
    
    editor = CodeEditor()
    
    # 1. Test has_placeholders
    print("[TEST 1] Validation de CodeEditor.has_placeholders...")
    
    valid_searches = [
        "body { background-color: white; }",
        "def hello():\n    print('hello world')",
        "color: #ff6f61; /* Maintien de la couleur */"
    ]
    
    invalid_searches = [
        "body {\n    ...\n}",
        "body {\n    /* ... [autres sections inchangées] ... */\n}",
        "// ... code existant ...",
        "<!-- ... -->",
        "body {\n    [inchangé]\n}",
        "body {\n    [autres sections]\n}",
        "/* autres sections inchangées */"
    ]
    
    for idx, valid in enumerate(valid_searches):
        assert not editor.has_placeholders(valid), f"Faux positif sur recherche valide {idx} : {repr(valid)}"
    print("  [PASS] Tous les faux positifs évités (recherches valides acceptées).")
        
    for idx, invalid in enumerate(invalid_searches):
        assert editor.has_placeholders(invalid), f"Non-détection d'ellipse sur recherche invalide {idx} : {repr(invalid)}"
    print("  [PASS] Toutes les ellipses et placeholders d'omissions détectés avec succès.")
    
    # 2. Test parse_search_replace_blocks
    print("\n[TEST 2] Validation du marquage invalide au parsing...")
    
    bad_llm_response = """
Voici les modifications requises :
FILE: style.css
<<<<<<< SEARCH
body {
    /* ... [autres sections inchangées] ... */
    margin: 0;
}
=======
body {
    background-color: #121212;
    margin: 0;
}
>>>>>>> REPLACE
"""
    
    blocks = editor.parse_search_replace_blocks(bad_llm_response)
    assert len(blocks) == 1, "Devrait avoir extrait un bloc."
    assert blocks[0]["invalid"] is True, "Le bloc aurait dû être marqué comme invalide !"
    assert "Rejeté" in blocks[0]["error_message"], "Un message d'erreur explicite doit être associé."
    print("  [PASS] Le bloc est correctement analysé et marqué comme invalide dès le parsing.")
    
    # 3. Test de rejet à l'application apply_edit
    print("\n[TEST 3] Validation du rejet de sécurité physique (apply_edit)...")
    
    temp_dir = Path(__file__).parent / "temp_patch_test_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = temp_dir / "style.css"
    test_file.write_text("body { background-color: white; margin: 0; }", encoding="utf-8")
    
    try:
        # Tenter d'appliquer un bloc contenant des ellipses
        success, msg = editor.apply_edit(
            test_file,
            "body {\n    /* ... [autres sections inchangées] ... */\n}",
            "body { background-color: black; }"
        )
        
        assert not success, "L'application du patch aurait dû être rejetée !"
        assert "refusée" in msg or "rejeté" in msg, "Le message doit expliquer le motif du rejet."
        print("  [PASS] L'écriture d'un patch avec placeholders a bien été rejetée au niveau sécurité.")
        
        # Vérifier que le fichier n'a pas été modifié
        content = test_file.read_text(encoding="utf-8")
        assert "white" in content, "Le fichier ne devrait pas avoir changé sur le disque."
        print("  [PASS] L'état du disque est resté intact.")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 4. Test de validation contextuelle des ellipses
    print("\n[TEST 4] Validation contextuelle des ellipses (has_placeholders)...")
    temp_dir = Path(__file__).parent / "temp_contextual_test_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = temp_dir / "main.py"
    # Fichier contenant légitimement des points de suspension dans un commentaire
    file_content = (
        "# Jeu de Tic Tac Toe\n"
        "def afficher_plateau(plateau):\n"
        "    print(\"-\" * 13)\n"
        "    # ... la logique d'affichage va venir ici\n"
        "    pass\n"
    )
    test_file.write_text(file_content, encoding="utf-8")
    
    try:
        # A. Un bloc SEARCH contenant l'ellipse légitime identique au fichier doit être VALIDÉ
        search_legitimate = "    print(\"-\" * 13)\n    # ... la logique d'affichage va venir ici\n    pass"
        is_placeholder = editor.has_placeholders(search_legitimate, file_path=test_file)
        assert not is_placeholder, "L'ellipse légitime présente dans le fichier aurait dû être acceptée !"
        print("  [PASS] Ellipse légitime dans le fichier correctement acceptée.")
        
        # B. Un bloc SEARCH contenant une ellipse absente du fichier doit être REJETÉ
        search_placeholder = "def afficher_plateau(plateau):\n    ...\n    pass"
        is_placeholder = editor.has_placeholders(search_placeholder, file_path=test_file)
        assert is_placeholder, "L'ellipse inventée (placeholder) aurait dû être rejetée !"
        print("  [PASS] Ellipse inventée (non présente dans le fichier) correctement rejetée.")
        
        # C. Appliquer la modification légitime avec apply_edit
        success, msg = editor.apply_edit(
            test_file,
            search_legitimate,
            "    print(\"-------------\")"
        )
        assert success, f"L'application du patch légitime a échoué : {msg}"
        print("  [PASS] L'application de la modification légitime avec points de suspension a réussi.")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    print("\n=== TOUS LES TESTS DE VALIDATION DE PATCH ONT RÉUSSI ! ===")

if __name__ == "__main__":
    test_patch_validator()

