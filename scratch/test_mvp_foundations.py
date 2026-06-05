import os
import sys
import shutil
import unittest
from pathlib import Path

# Ajouter le répertoire parent au sys.path pour pouvoir importer file_manager
parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from file_manager import FileManager

class TestMVPFoundations(unittest.TestCase):
    def setUp(self):
        # Création d'un dossier de test temporaire dans scratch
        self.test_dir = Path(__file__).resolve().parent / "temp_test_sandbox"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # Création de fichiers de test standard
        self.create_test_file("file1.txt", "Hello world, this is a test file.\nLine 2: python code here.\nLine 3: test helper.\n")
        self.create_test_file("sub/file2.txt", "This is file2 in a subdirectory.\nIt has python code def my_func():\n    pass\nAnother line with python keyword.\n")
        self.create_test_file("sub/subsub/file3.txt", "Deep nested file.\nContains python content.\n")
              # Création de fichiers à ignorer
        self.create_test_file(".gemini/file4.txt", "Should be ignored entirely.\n")
        self.create_test_file(".git/config", "git config file.\n")
        self.create_test_file("venv/bin/activate", "venv activate script.\n")
        self.create_test_file("__pycache__/main.cpython-310.pyc", "binary pyc bytecode")
        self.create_test_file("binary.png", "fake png content")
        self.create_test_file("sub/backup.bak", "fake backup content")
        
        # Fichier avec correspondances nombreuses pour tester la limitation
        repeated_content = "\n".join([f"match_here line {i}" for i in range(15)])
        self.create_test_file("repeated.txt", repeated_content)
        
        # Fichier large pour tester la troncature de contexte
        large_content = "A" * 15000  # 15 000 caractères
        self.create_test_file("large.txt", large_content)
        
        # Initialisation du FileManager
        self.fm = FileManager()
        self.fm.set_working_dir(str(self.test_dir))

    def tearDown(self):
        # Nettoyage du dossier temporaire
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def create_test_file(self, rel_path, content):
        file_path = self.test_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_path_security(self):
        print("\n--- Test de la sécurité des chemins ---")
        
        # 1. Chemin valide dans le working_dir
        resolved = self.fm._resolve_path("file1.txt")
        self.assertTrue(resolved.exists())
        
        # 2. Chemin valide avec '..' qui reste dans le working_dir
        resolved_dotdot = self.fm._resolve_path("sub/../file1.txt")
        self.assertEqual(resolved, resolved_dotdot)
        
        # 3. Chemin invalide sortant du working_dir (relatif)
        with self.assertRaises((ValueError, PermissionError)):
            self.fm._resolve_path("../outside.txt")
            
        # 4. Chemin invalide sortant du working_dir (absolu)
        external_abs = Path("/Windows/System32/cmd.exe").resolve()
        with self.assertRaises((ValueError, PermissionError)):
            self.fm._resolve_path(str(external_abs))
            
        # 5. Tentative de chargement d'un fichier en dehors du working_dir
        success, msg = self.fm.load_file("../outside.txt")
        self.assertFalse(success)
        self.assertIn("Accès refusé", msg)

    def test_recursive_listing(self):
        print("\n--- Test du listage récursif ---")
        files = self.fm.get_available_files()
        
        # Devraient être présents
        self.assertIn("file1.txt", files)
        self.assertIn("sub/file2.txt", files)
        self.assertIn("sub/subsub/file3.txt", files)
        self.assertIn("repeated.txt", files)
        self.assertIn("large.txt", files)
        
        # Devraient être exclus
        self.assertNotIn(".gemini/file4.txt", files)
        self.assertNotIn(".git/config", files)
        self.assertNotIn("venv/bin/activate", files)
        self.assertNotIn("__pycache__/main.cpython-310.pyc", files)
        self.assertNotIn("binary.png", files)
        self.assertNotIn("sub/backup.bak", files)
        
        # Tous les chemins doivent être relatifs avec slashs normaux
        for f in files:
            self.assertFalse(Path(f).is_absolute())
            self.assertNotIn("\\", f)

    def test_text_search(self):
        print("\n--- Test de la recherche textuelle (grep) avec limites ---")
        
        # 1. Recherche normale
        success, results, truncated = self.fm.search_text("python")
        self.assertTrue(success)
        self.assertFalse(truncated)
        self.assertEqual(len(results), 4)  # file1.txt, sub/file2.txt (2x) et sub/subsub/file3.txt (1x)
        
        # 2. Limitation à 5 correspondances par fichier (repeated.txt en contient 15)
        success, results, truncated = self.fm.search_text("match_here")
        self.assertTrue(success)
        self.assertTrue(truncated)
        matches_in_repeated = [r for r in results if r["file"] == "repeated.txt"]
        self.assertEqual(len(matches_in_repeated), 5)  # Strictement limité à 5
        
        # 3. Limitation globale à 50 correspondances
        # Créons 12 fichiers avec chacun 5 correspondances (total 60)
        for i in range(12):
            self.create_test_file(f"search_limit_{i}.txt", "target_word\n" * 5)
        success, results, truncated = self.fm.search_text("target_word")
        self.assertTrue(success)
        self.assertTrue(truncated)
        self.assertEqual(len(results), 50)  # Limite globale de 50 atteinte
 
    def test_multi_file_loading_and_compatibility(self):
        print("\n--- Test du chargement multi-fichiers et compatibilité mono-fichier ---")
        
        # 1. Charger file1.txt
        success, msg = self.fm.load_file("file1.txt")
        self.assertTrue(success)
        self.assertEqual(self.fm.current_file_path, str((self.test_dir / "file1.txt").resolve()))
        self.assertIn("file1.txt", self.fm.loaded_files)
        
        # 2. Charger sub/file2.txt (devrait s'ajouter, pas effacer file1.txt)
        success, msg = self.fm.load_file("sub/file2.txt")
        self.assertTrue(success)
        self.assertEqual(self.fm.current_file_path, str((self.test_dir / "sub/file2.txt").resolve()))
        self.assertIn("file1.txt", self.fm.loaded_files)
        self.assertIn("sub/file2.txt", self.fm.loaded_files)
        
        # 3. Fermer le fichier actif (sub/file2.txt).
        # Devrait basculer l'actif vers le dernier fichier restant (file1.txt).
        success, msg = self.fm.close_file("sub/file2.txt")
        self.assertTrue(success)
        self.assertNotIn("sub/file2.txt", self.fm.loaded_files)
        self.assertEqual(self.fm.current_file_path, str((self.test_dir / "file1.txt").resolve()))
        self.assertEqual(self.fm.current_file_content, "Hello world, this is a test file.\nLine 2: python code here.\nLine 3: test helper.\n")
        
        # 4. Fermeture complète
        success, msg = self.fm.close_all_files()
        self.assertTrue(success)
        self.assertEqual(len(self.fm.loaded_files), 0)
        self.assertIsNone(self.fm.current_file_path)
        self.assertIsNone(self.fm.current_file_content)

    def test_context_truncation(self):
        print("\n--- Test des limites de taille et troncatures du contexte IA ---")
        
        # Définition de limites personnalisées pour le test
        self.fm.max_file_chars = 1000
        self.fm.max_global_chars = 800
        
        # 1. Charger le fichier large.txt (15 000 caractères)
        self.fm.load_file("large.txt")
        
        # Le contexte individuel du fichier doit être tronqué
        context = self.fm.get_context_for_ai()
        self.assertIn("[... TRONQUÉ", context)
        
        # Le contexte global combiné doit également respecter max_global_chars
        self.assertIn("[... TRONQUÉ GLOBALEMENT", context)

if __name__ == "__main__":
    unittest.main()
