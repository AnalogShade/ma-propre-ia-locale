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
        
    # 8. Test de validation Unicode et typographique (Niveau 4)
    print("\n[TEST 8] Validation de la normalisation Unicode et typographique (Niveau 4)...")
    temp_dir = Path(__file__).parent / "temp_unicode_test_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = temp_dir / "main.py"
    # Contenu du fichier avec apostrophes typographiques courbes (’) et espace insécable (\xa0) avant le point d'exclamation
    file_content = "def saluer():\n    print(\"C’est l’IA Anna !\")\n"
    test_file.write_text(file_content, encoding="utf-8")
    
    try:
        # Bloc SEARCH avec apostrophes droites (') et espace classique ( )
        search_content = "def saluer():\n    print(\"C'est l'IA Anna !\")"
        replace_text = "def saluer():\n    print(\"Hello Anna !\")"
        
        success, msg = editor.apply_edit(
            test_file,
            search_content,
            replace_text
        )
        assert success, f"Le patch tolérant à la typographie a échoué : {msg}"
        
        content = test_file.read_text(encoding="utf-8")
        assert "Hello Anna" in content, "Le fichier aurait dû être modifié par le remplacement typographique."
        print("  [PASS] Patch Unicode et typographique (Niveau 4) appliqué avec succès.")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 9. Test de reproduction du bug HTML réel (indentation manquante)
    print("\n[TEST 9] Reproduction du bug HTML réel (sans indentation)...")
    temp_dir = Path(__file__).parent / "temp_html_bug_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = temp_dir / "index.html"
    file_content = (
        "    <!-- Contact Section -->\n"
        "    <section id=\"contact\" class=\"contact-section container\">\n"
        "        <h3>Prêt(e) à coder ensemble ?</h3>\n"
        "        <p class=\"subtitle\">Je suis disponible pour analyser votre projet ! N'hésitez pas.</p>\n"
        "        \n"
        "        <div class=\"contact-info grid-3\">\n"
    )
    test_file.write_text(file_content, encoding="utf-8")
    
    try:
        # Bloc SEARCH sans espaces d'indentation au début
        search_content = (
            "<!-- Contact Section -->\n"
            "<section id=\"contact\" class=\"contact-section container\">\n"
            "    <h3>Prêt(e) à coder ensemble ?</h3>\n"
            "    <p class=\"subtitle\">Je suis disponible pour analyser votre projet ! N'hésitez pas.</p>\n"
            "        \n"
            "    <div class=\"contact-info grid-3\">"
        )
        replace_text = (
            "<!-- Contact Section -->\n"
            "<section id=\"contact\" class=\"contact-section container\">\n"
            "    <h3>🚀 Lancez Votre Projet avec Anna</h3>\n"
            "    <p class=\"subtitle\">Que ce soit pour un TDD ou une refonte. Je suis là !</p>\n"
            "        \n"
            "    <div class=\"contact-info grid-3\">"
        )
        
        success, msg = editor.apply_edit(test_file, search_content, replace_text)
        assert success, f"Le test de reproduction du bug HTML a échoué : {msg}"
        
        content = test_file.read_text(encoding="utf-8")
        assert "Lancez Votre Projet" in content, "La modification HTML n'a pas été appliquée."
        print("  [PASS] Bug HTML d'indentation résolu de manière robuste.")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 10. Plusieurs modifications dans le même fichier
    print("\n[TEST 10] Application de plusieurs patchs consécutifs dans le même fichier...")
    temp_dir = Path(__file__).parent / "temp_multi_patch_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = temp_dir / "main.py"
    file_content = (
        "def debut():\n"
        "    print('debut')\n"
        "\n"
        "def milieu():\n"
        "    print('milieu')\n"
        "\n"
        "def fin():\n"
        "    print('fin')\n"
    )
    test_file.write_text(file_content, encoding="utf-8")
    
    try:
        # Patch 1 : modifie debut
        success1, msg1 = editor.apply_edit(
            test_file,
            "def debut():\n    print('debut')",
            "def debut():\n    print('DEBUT MODIFIE')"
        )
        assert success1, f"Le patch 1 a échoué : {msg1}"
        
        # Patch 2 : modifie fin
        success2, msg2 = editor.apply_edit(
            test_file,
            "def fin():\n    print('fin')",
            "def fin():\n    print('FIN MODIFIEE')"
        )
        assert success2, f"Le patch 2 a échoué : {msg2}"
        
        content = test_file.read_text(encoding="utf-8")
        assert "DEBUT MODIFIE" in content, "Le premier patch n'est plus présent."
        assert "FIN MODIFIEE" in content, "Le second patch n'a pas été appliqué."
        print("  [PASS] Modifications multiples successives appliquées sans interférences.")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 11. Validation CRLF/LF
    print("\n[TEST 11] Validation de la cascade de fins de ligne CRLF/LF...")
    temp_dir = Path(__file__).parent / "temp_crlf_lf_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    test_file_lf = temp_dir / "main_lf.py"
    test_file_crlf = temp_dir / "main_crlf.py"
    
    # Écriture forcée avec \n (LF) et \r\n (CRLF)
    test_file_lf.write_bytes(b"def test():\n    print('lf')\n")
    test_file_crlf.write_bytes(b"def test():\r\n    print('crlf')\r\n")
    
    try:
        # Patch SEARCH écrit en LF (\n)
        search_content = "def test():\n    print('lf')"
        success_lf, msg_lf = editor.apply_edit(test_file_lf, search_content, "def test():\n    print('ok')")
        assert success_lf, f"L'application LF a échoué : {msg_lf}"
        
        # Le même patch appliqué sur CRLF
        search_crlf_target = "def test():\n    print('crlf')"
        success_crlf, msg_crlf = editor.apply_edit(test_file_crlf, search_crlf_target, "def test():\n    print('ok')")
        assert success_crlf, f"L'application CRLF a échoué : {msg_crlf}"
        
        # Vérifier que les fins de lignes restent conformes
        lf_content = test_file_lf.read_bytes()
        crlf_content = test_file_crlf.read_bytes()
        
        assert b"\r\n" not in lf_content, "Le fichier LF a été converti en CRLF de manière indésirable."
        assert b"\r\n" in crlf_content, "Le fichier CRLF a perdu ses retours CRLF."
        print("  [PASS] Cascade CRLF/LF transparente et respectueuse du format d'origine.")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 12. Protection contre l'ambiguïté (Pas de faux positifs)
    print("\n[TEST 12] Validation des protections contre l'ambiguïté...")
    temp_dir = Path(__file__).parent / "temp_ambiguity_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = temp_dir / "main.py"
    # Contient deux blocs identiques
    file_content = (
        "def doublon():\n"
        "    print('hello')\n"
        "\n"
        "def doublon():\n"
        "    print('hello')\n"
    )
    test_file.write_text(file_content, encoding="utf-8")
    
    try:
        # Recherche ambiguë
        success, msg = editor.apply_edit(
            test_file,
            "def doublon():\n    print('hello')",
            "def doublon():\n    print('world')"
        )
        assert not success, "Le patch aurait dû être rejeté car il correspond à deux zones distinctes !"
        assert "ambigu" in msg, f"Le message d'erreur doit signaler l'ambiguïté : {msg}"
        print("  [PASS] Protection contre les correspondances ambiguës validée (pas de faux positifs).")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 13. Validation de la gestion de session (Phase 2)
    print("\n[TEST 13] Validation de la gestion de session (Phase 2)...")
    temp_dir = Path(__file__).parent / "temp_session_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        import json
        create_blocks = [{
            "id": "ch_create_0",
            "file_path": "nouveau.txt",
            "content": "hello world"
        }]
        edit_blocks = [{
            "id": "ch_edit_0",
            "file_path": "existant.txt",
            "search_content": "existant",
            "replace_content": "remplace",
            "invalid": False
        }]
        
        # Démarrage de la session
        editor.start_session(temp_dir, create_blocks, edit_blocks)
        
        session_file = temp_dir / ".anna" / "changes_session.json"
        assert session_file.exists(), "Le fichier de session changes_session.json n'a pas été créé !"
        
        # Lecture et validation de l'état initial PROPOSED
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        assert data["session_id"].startswith("session_"), "Format d'ID de session incorrect."
        assert len(data["files"]) == 2, "Les fichiers de la session n'ont pas été enregistrés correctement."
        
        # Test de mise à jour d'état
        success = editor.update_change_state(temp_dir, "ch_edit_0", "APPLIED")
        assert success, "La mise à jour de l'état a échoué."
        
        with open(session_file, 'r', encoding='utf-8') as f:
            updated_data = json.load(f)
            
        edit_change = updated_data["files"]["existant.txt"]["changes"][0]
        assert edit_change["state"] == "APPLIED", f"Attendu l'état APPLIED, obtenu {edit_change['state']}"
        print("  [PASS] Session changes_session.json créée et mise à jour avec succès.")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 14. Validation du réessai unitaire (Phase 3)
    print("\n[TEST 14] Validation du réessai unitaire après échec (Phase 3)...")
    temp_dir = Path(__file__).parent / "temp_retry_project"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = temp_dir / "main.py"
    # Contenu initial du fichier
    file_content = "def saluer():\n    print('bonjour')\n"
    test_file.write_text(file_content, encoding="utf-8")
    
    try:
        # Bloc SEARCH erroné (qui va échouer à l'application)
        bad_search = "def saluer():\n    print('incorrect')"
        replace_text = "def saluer():\n    print('hello')"
        
        success1, msg1 = editor.apply_edit(test_file, bad_search, replace_text)
        assert not success1, "Le patch erroné aurait dû échouer !"
        
        # Simulation de l'enregistrement de l'échec dans la session
        create_blocks = []
        edit_blocks = [{
            "id": "ch_edit_retry",
            "file_path": str(test_file),
            "search_content": bad_search,
            "replace_content": replace_text,
            "invalid": False
        }]
        editor.start_session(temp_dir, create_blocks, edit_blocks)
        editor.update_change_state(temp_dir, "ch_edit_retry", "FAILED", error_message=msg1)
        
        # L'utilisateur ou le système corrige le SEARCH (c'est l'action de Retry)
        correct_search = "def saluer():\n    print('bonjour')"
        success2, msg2 = editor.apply_edit(test_file, correct_search, replace_text)
        assert success2, f"Le réessai avec le SEARCH correct a échoué : {msg2}"
        
        # Mise à jour de l'état dans la session
        editor.update_change_state(temp_dir, "ch_edit_retry", "APPLIED")
        
        # Vérifier que le fichier est bien modifié et que l'état de la session est mis à jour
        content = test_file.read_text(encoding="utf-8")
        assert "hello" in content, "Le fichier n'a pas été mis à jour après le réessai."
        
        session_file = temp_dir / ".anna" / "changes_session.json"
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
            
        change_state = session_data["files"][str(test_file)]["changes"][0]["state"]
        assert change_state == "APPLIED", f"L'état de session aurait dû être APPLIED, obtenu {change_state}"
        print("  [PASS] Réessai unitaire après échec validé avec succès (Phase 3).")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 15. Validation des transitions d'états UI (Phase 3)
    print("\n[TEST 15] Validation des transitions d'états UI (Phase 3)...")
    import tkinter as tk
    
    # Création d'une application Tkinter minimale
    root = tk.Tk()
    root.withdraw() # Cache la fenêtre principale
    
    try:
        # Mock d'un block_state et des widgets associés
        block_state = {"status": "pending"}
        btn_apply = tk.Button(root, text="Appliquer")
        btn_cancel = tk.Button(root, text="Annuler")
        status_label = tk.Label(root, text="")
        error_status_label = tk.Label(root, text="")
        action_title = "Appliquer"
        
        # Copie locale simplifiée de la logique update_ui_for_status de gui.py
        def update_ui_for_status_mock():
            status = block_state["status"]
            if status == "applied":
                status_label.config(text="✓ Appliqué", fg="#80ff80")
                if btn_apply and btn_apply.winfo_exists():
                    btn_apply.config(text=f"✓ {action_title}", state="disabled", bg="#03dac6", fg="black")
                if btn_cancel and btn_cancel.winfo_exists():
                    btn_cancel.config(state="disabled")
            elif status == "cancelled":
                status_label.config(text="✗ Annulé", fg="#888888")
                if btn_apply and btn_apply.winfo_exists():
                    btn_apply.config(text=f"✓ {action_title}", state="disabled", bg="#03dac6", fg="black")
                if btn_cancel and btn_cancel.winfo_exists():
                    btn_cancel.config(state="disabled")
            elif status == "failed":
                status_label.config(text="⚠ Échoué", fg="#ff5555")
                if btn_apply and btn_apply.winfo_exists():
                    btn_apply.config(text="🔄 Réessayer", state="normal", bg="#4a90e2", fg="white")
                if btn_cancel and btn_cancel.winfo_exists():
                    btn_cancel.config(state="normal")
            elif status in ("apply_pending", "retry_pending"):
                status_label.config(text="🔄 Analyse en cours...", fg="#4a90e2")
                if btn_apply and btn_apply.winfo_exists():
                    btn_apply.config(state="disabled")
                if btn_cancel and btn_cancel.winfo_exists():
                    btn_cancel.config(state="disabled")
            elif status == "invalid":
                status_label.config(text="⚠ Invalide", fg="#ff5555")
            else:
                status_label.config(text="", fg="#e0e0e0")

        # 1. État initial (pending)
        update_ui_for_status_mock()
        assert status_label.cget("text") == "", "Attendu status label vide pour 'pending'"
        
        # 2. Transition vers apply_pending (Analyse en cours)
        block_state["status"] = "apply_pending"
        update_ui_for_status_mock()
        assert "Analyse en cours" in status_label.cget("text"), "Attendu 'Analyse en cours...' pendant le traitement"
        assert btn_apply.cget("state") == "disabled", "Le bouton d'application doit être désactivé pendant le traitement"
        assert btn_cancel.cget("state") == "disabled", "Le bouton d'annulation doit être désactivé pendant le traitement"
        
        # 3. Échec de l'application (failed)
        block_state["status"] = "failed"
        update_ui_for_status_mock()
        assert "Échoué" in status_label.cget("text"), "Attendu statut 'Échoué'"
        assert btn_apply.cget("text") == "🔄 Réessayer", "Le bouton aurait dû changer pour 'Réessayer'"
        assert btn_apply.cget("state") == "normal", "Le bouton Réessayer doit être actif"
        assert btn_cancel.cget("state") == "normal", "Le bouton d'annulation doit être actif après un échec"
        
        # 4. Succès après réessai (applied)
        block_state["status"] = "applied"
        update_ui_for_status_mock()
        assert "Appliqué" in status_label.cget("text"), "Attendu statut 'Appliqué'"
        assert btn_apply.cget("state") == "disabled", "Le bouton d'application doit être désactivé après succès"
        assert btn_cancel.cget("state") == "disabled", "Le bouton d'annulation doit être désactivé après succès"
        
        print("  [PASS] Transitions d'états et propriétés UI validées avec succès.")
        
    finally:
        root.destroy()

    print("\n=== TOUS LES TESTS DE VALIDATION DE PATCH ONT RÉUSSI ! ===")

if __name__ == "__main__":
    test_patch_validator()

