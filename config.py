# --- CONFIGURATION DE L'IA ---

# Le modèle que Ollama doit utiliser (ex: llama3, phi3, mistral)
# Assure-toi d'avoir fait 'ollama pull <nom_du_modele>' avant.
MODEL_NAME = "llama3"

# Le prompt système définit la "personnalité" de l'IA.
SYSTEM_PROMPT = """
Tu es une IA locale nommée 'Antis'. 
Tu es utile, concise et tu as une personnalité amicale.
Tu réponds toujours en français.
"""

# --- PARAMÈTRES DE MÉMOIRE ---

# Chemin vers le fichier qui stocke l'historique
MEMORY_FILE = "data/memory.json"

# Nombre maximum de messages envoyés au modèle pour garder du contexte
# (Évite de saturer la mémoire du modèle sur de longues discussions)
CONTEXT_WINDOW = 20
