# --- CONFIGURATION DE L'IA ---

# Le modèle que Ollama doit utiliser (ex: llama3, phi3, mistral)
# Assure-toi d'avoir fait 'ollama pull <nom_du_modele>' avant.
MODEL_NAME = "llama3"

DEFAULT_NAME = "Antis"

# Le prompt système définit la "personnalité" de l'IA.
SYSTEM_PROMPT = """Tu es {name}, une IA locale utile et amicale. 
Tu réponds toujours en français de manière concise et naturelle.
Utilise la section 'CE QUE TU SAIS SUR L'HUMAIN' pour répondre aux questions sur lui, sans jamais interpréter ou inventer d'informations non présentes."""

# --- PARAMÈTRES DE MÉMOIRE V2 ---

# Historique court terme (Conversation en cours)
HISTORY_FILE = "data/history.json"
MAX_HISTORY = 100 # Nombre de messages max dans l'historique brut

# Profils (Informations stables)
USER_PROFILE_FILE = "data/user_profile.json"
ASSISTANT_PROFILE_FILE = "data/assistant_profile.json"

# Mémoire long terme (Faits extraits)
FACTS_FILE = "data/long_term_facts.json"

# Nombre de messages récents envoyés à l'IA pour le contexte immédiat
CONTEXT_WINDOW = 20
