import unittest
import sys
import os

# Ajouter le chemin racine du projet pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory_retriever import MemoryRetriever, extract_keywords
from config import CORE_MEMORY_IDS

class TestMemoryRetriever(unittest.TestCase):
    def setUp(self):
        self.retriever = MemoryRetriever()
        # Mock des sources de mémoire
        self.memory_sources = {
            "user_profile": {
                "nom": "Louis",
                "prénom": "Louis",
                "goûts": "fichier chérie",
                "linguistic_preference": "Louis prefers using 'tu'"
            },
            "assistant_profile": {
                "nom": "Anna",
                "cheveux": "bleus",
                "couleur_cheveux": "bleus"
            },
            "facts": {
                "overwatch": {
                    "value": "Louis adore jouer à Overwatch le week-end.",
                    "count": 2
                },
                "vaisselle": {
                    "value": "Louis a fait la vaisselle hier soir.",
                    "count": 1
                },
                "tres_frequent": {
                    "value": "Un fait répété très souvent par l'utilisateur.",
                    "count": 10  # Doit être plafonné à 5
                }
            }
        }

    def test_extract_keywords(self):
        # Test de la tokenisation et du filtrage
        text = "Bonjour Louis ! Est-ce que tu as fini de faire la vaisselle ?"
        kw = extract_keywords(text)
        # Louis et vaisselle doivent être conservés. "tu", "est", "de", "la", "faire" doivent être filtrés.
        self.assertIn("louis", kw)
        self.assertIn("vaisselle", kw)
        self.assertNotIn("tu", kw)
        self.assertNotIn("est", kw)
        self.assertNotIn("la", kw)

    def test_normalize_memories(self):
        # Test que les profils et faits sont correctement normalisés
        fiches = self.retriever._normalize_memories(self.memory_sources)
        ids = [f["id"] for f in fiches]
        
        # Vérifier la présence des IDs attendus
        self.assertIn("user_profile_nom", ids)
        self.assertIn("assistant_profile_cheveux", ids)
        self.assertIn("long_term_facts_overwatch", ids)
        
        # Vérifier le plafonnement de count à 5 pour l'importance
        tres_frequent_fiche = next(f for f in fiches if f["id"] == "long_term_facts_tres_frequent")
        self.assertEqual(tres_frequent_fiche["importance"], 5)
        
        # Vérifier la présence des tags générés
        nom_fiche = next(f for f in fiches if f["id"] == "user_profile_nom")
        self.assertIn("louis", nom_fiche["tags"])
        self.assertIn("user", nom_fiche["tags"])

    def test_retrieve_core_memory(self):
        # Vérifier que les fiches CORE permanentes sont toujours incluses
        res = self.retriever.retrieve("Salut !", self.memory_sources)
        injected_ids = [f["id"] for f in res.injected_facts]
        
        for cid in CORE_MEMORY_IDS:
            self.assertIn(cid, injected_ids)

    def test_retrieve_scoring_relevance(self):
        # Si on parle d'Overwatch
        res = self.retriever.retrieve("As-tu envie de faire une partie de Overwatch ?", self.memory_sources)
        injected_ids = [f["id"] for f in res.injected_facts]
        
        # Le fait overwatch doit être injecté dynamiquement
        self.assertIn("long_term_facts_overwatch", injected_ids)
        
        # Trouver la fiche overwatch dans les détails de debug pour valider son score
        overwatch_debug = next(d for d in res.debug_details if d["id"] == "long_term_facts_overwatch")
        # Le mot-clé est "overwatch".
        # 1. Correspondance de tag "overwatch" -> +3
        # 2. Présence dans le texte "Overwatch" -> +2
        # 3. Catégorie long_term_facts ("tu/toi" n'est pas dans les mots-clés de catégorie pour long_term_facts, mais "je/moi/me/mon/ma/mes" non plus. Attends, y a-t-il un pronom ?)
        # La phrase de test contient "tu/toi" mais la catégorie est long_term_facts (Louis), donc pas de bonus catégorie.
        # 4. Importance -> +2 (count)
        # Score attendu : 3 (tag) + 2 (texte) + 2 (importance) = 7
        self.assertEqual(overwatch_debug["score"], 7)

    def test_guardrail_no_lexical_no_importance(self):
        # S'il n'y a aucun mot-clé correspondant, aucun fait non-CORE ne doit être injecté,
        # même s'il a une importance élevée (comme "tres_frequent" qui a count=10 -> importance=5).
        res = self.retriever.retrieve("La météo de demain sera-t-elle pluvieuse ?", self.memory_sources)
        injected_ids = [f["id"] for f in res.injected_facts]
        
        # Seulement les fiches CORE permanentes doivent être là
        dynamic_injected = [fid for fid in injected_ids if fid not in CORE_MEMORY_IDS]
        self.assertEqual(len(dynamic_injected), 0)

if __name__ == "__main__":
    unittest.main()
