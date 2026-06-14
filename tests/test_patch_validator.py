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
        
    # 5. Test de diagnostics d'instrumentation (Phase 1)
    print("\n[TEST 5] Validation de l'instrumentation diagnostic (Phase 1)...")
    
    test_diag_response = """
FILE: main.py
<<<<<<< SEARCH
def hello():
    pass
=======
def hello():
    print("hi")
>>>>>>> REPLACE

FILE: other.py
<<<<<<< SEARCH
def unclosed():
    pass
=======
def unclosed():
    print("unclosed block")
"""
    
    diags = {}
    blocks = editor.parse_search_replace_blocks(test_diag_response, diagnostics=diags)
    
    # Vérifier les marqueurs
    assert diags["raw_markers_file"] == 2, f"Attendu 2 FILE:, obtenu {diags['raw_markers_file']}"
    assert diags["raw_markers_search"] == 2, f"Attendu 2 SEARCH, obtenu {diags['raw_markers_search']}"
    assert diags["raw_markers_replace"] == 1, f"Attendu 1 REPLACE, obtenu {diags['raw_markers_replace']}"
    
    # Vérifier le bloc incomplet
    assert len(diags["incomplete_blocks"]) == 1, f"Attendu 1 bloc incomplet, obtenu {len(diags['incomplete_blocks'])}"
    inc_block = diags["incomplete_blocks"][0]
    assert inc_block["file_path"] == "other.py", f"Attendu 'other.py', obtenu {inc_block['file_path']}"
    assert inc_block["state"] == "replace", f"Attendu l'état 'replace', obtenu {inc_block['state']}"
    assert "unclosed" in inc_block["replace_preview"], f"Attendu 'unclosed' dans l'aperçu, obtenu {inc_block['replace_preview']}"
    # 6. Test de diagnostics de génération Ollama (Phase 1B)
    print("\n[TEST 6] Validation de l'instrumentation Ollama (Phase 1B)...")
    from ai_engine import AIEngine
    from unittest.mock import MagicMock, patch
    
    engine = AIEngine()
    
    # Mock show info
    mock_show_obj = MagicMock()
    mock_show_obj.modelfile = "PARAMETER num_ctx 4096\nPARAMETER num_predict 2048"
    mock_show_obj.parameters = "num_ctx 4096\nnum_predict 2048"
    mock_show_obj.modelinfo = {"gemma.context_length": 8192}
    
    mock_show = MagicMock(return_value=mock_show_obj)
    
    # Mock client and chat
    mock_client = MagicMock()
    mock_chat_response = {
        "message": {"role": "assistant", "content": "Hello test!"},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 42,
        "eval_count": 12,
        "total_duration": 1000000000
    }
    mock_client.chat.return_value = mock_chat_response
    
    diags_ollama = {}
    with patch('ollama.show', mock_show), \
         patch.object(engine, '_get_client', return_value=mock_client):
         # Appel synchrone (chunk_callback=None)
         res = engine.get_response(
             context_messages=[{"role": "user", "content": "Hello"}],
             ollama_diagnostics=diags_ollama
         )
         
    assert res == "Hello test!", f"Attendu 'Hello test!', obtenu {res}"
    assert diags_ollama["done"] is True, "Attendu done=True"
    assert diags_ollama["done_reason"] == "stop", "Attendu done_reason='stop'"
    assert diags_ollama["prompt_eval_count"] == 42, "Attendu prompt_eval_count=42"
    assert diags_ollama["eval_count"] == 12, "Attendu eval_count=12"
    assert diags_ollama["model_ctx"] == 4096, f"Attendu model_ctx=4096, obtenu {diags_ollama['model_ctx']}"
    assert diags_ollama["model_predict"] == 2048, f"Attendu model_predict=2048, obtenu {diags_ollama['model_predict']}"
    assert diags_ollama["model_native_ctx"] == 8192, f"Attendu model_native_ctx=8192, obtenu {diags_ollama['model_native_ctx']}"
    
    # Vérifier que le paramètre options a bien été transmis avec num_ctx
    called_args, called_kwargs = mock_client.chat.call_args
    assert called_kwargs.get("options") == {"num_ctx": 8192}, f"Attendu options avec num_ctx=8192, obtenu {called_kwargs.get('options')}"
    
    # 7. Test de validation non-contiguë tolérante aux commentaires et lignes vides
    print("\n[TEST 7] Validation de la tolérance aux commentaires et vides dans la non-contiguïté...")
    temp_dir = Path(__file__).parent / "temp_comment_tolerant_test_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = temp_dir / "main.py"
    file_content = (
        "def main():\n"
        "    print('line 1')\n"
        "    # Un commentaire au milieu qui sera saute\n"
        "    print('line 2')\n"
        "    \n"
        "    print('line 3')\n"
    )
    test_file.write_text(file_content, encoding="utf-8")
    
    try:
        # A. Essai d'application d'un patch sans le commentaire ni la ligne vide
        search_no_comment = "def main():\n    print('line 1')\n    print('line 2')\n    print('line 3')"
        replace_text = "def main():\n    print('replaced')"
        
        success, msg = editor.apply_edit(
            test_file,
            search_no_comment,
            replace_text
        )
        assert success, f"Le patch tolérant aux commentaires a échoué : {msg}"
        
        content = test_file.read_text(encoding="utf-8")
        assert "replaced" in content, "Le fichier aurait dû être modifié."
        assert "line 1" not in content, "Le contenu original doit avoir disparu."
        print("  [PASS] Patch non-contigu appliqué avec succès en ignorant les commentaires et lignes vides.")
        
        # B. Essai d'application d'un patch avec du code réel au milieu (doit échouer)
        file_content_code = (
            "def main():\n"
            "    print('line 1')\n"
            "    x = 42\n"  # Code réel !
            "    print('line 2')\n"
        )
        test_file.write_text(file_content_code, encoding="utf-8")
        
        success, msg = editor.apply_edit(
            test_file,
            "def main():\n    print('line 1')\n    print('line 2')",
            "def main():\n    print('replaced')"
        )
        assert not success, "Le patch aurait dû être rejeté car il y a du code réel au milieu !"
        assert "omissions" in msg or "sautées" in msg, "Le message doit faire référence à des omissions."
        print("  [PASS] Rejet correct lorsque du code réel est présent dans l'omission.")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    print("\n=== TOUS LES TESTS DE VALIDATION DE PATCH ONT RÉUSSI ! ===")

if __name__ == "__main__":
    test_patch_validator()

