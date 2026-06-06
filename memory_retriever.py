import re
from config import MAX_RETRIEVED_FACTS, MIN_MEMORY_SCORE, CORE_MEMORY_IDS

STOP_WORDS = {
    # Mots vides en français
    "le", "la", "les", "de", "un", "une", "des", "est", "son", "ses", "ton", "tes", "je", 
    "tu", "il", "elle", "nous", "vous", "ils", "elles", "mon", "ma", "mes", "ta", "sa", 
    "dans", "sur", "avec", "par", "pour", "en", "qui", "que", "quoi", "dont", "où", 
    "mais", "ou", "et", "donc", "or", "ni", "car", "a", "à", "y", "ne", "pas", "se", 
    "ce", "cet", "cette", "ces", "du", "au", "aux", "parce", "qu", "d", "l", "s", "t", 
    "m", "n", "c", "j", "qu'un", "qu'une", "qu'il", "qu'elle", "ont", "sont",
    # Mots vides en anglais
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "to", "for", "in", "on", 
    "at", "by", "with", "from", "of", "about", "as", "into", "like", "through", "after",
}

def extract_keywords(text):
    """
    Extrait les mots-clés uniques et normalisés d'une chaîne de caractères,
    en supprimant la ponctuation et les mots vides.
    """
    if not text:
        return set()
    # Remplacer les caractères non-alphanumériques par des espaces
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    words = cleaned.split()
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}

class RetrievedContext:
    def __init__(self, injected_facts, ignored_count, keywords_detected, debug_details):
        self.injected_facts = injected_facts
        self.ignored_count = ignored_count
        self.keywords_detected = keywords_detected
        self.debug_details = debug_details

class MemoryRetriever:
    def __init__(self):
        pass

    def _normalize_memories(self, memory_sources):
        """
        Convertit les dictionnaires du MemoryManager (user_profile, assistant_profile, facts)
        en une liste de fiches mémoire normalisées et structurées.
        """
        fiches = []
        
        # 1. Profil Utilisateur
        user_profile = memory_sources.get("user_profile", {})
        for k, v in user_profile.items():
            tags = extract_keywords(k) | extract_keywords(str(v)) | {"user", k.lower()}
            fiches.append({
                "id": f"user_profile_{k}",
                "category": "user_profile",
                "tags": list(tags),
                "importance": 1,
                "text": f"Son {k} est {v}"
            })
            
        # 2. Profil Assistant (Anna)
        assistant_profile = memory_sources.get("assistant_profile", {})
        for k, v in assistant_profile.items():
            tags = extract_keywords(k) | extract_keywords(str(v)) | {"assistant", k.lower()}
            fiches.append({
                "id": f"assistant_profile_{k}",
                "category": "assistant_profile",
                "tags": list(tags),
                "importance": 1,
                "text": f"Ton/Ta {k} : {v}"
            })
            
        # 3. Faits à long terme
        facts = memory_sources.get("facts", {})
        for k, v in facts.items():
            val_text = v.get("value", "")
            count = v.get("count", 1)
            # Garde-fou 1 : Plafonnement de l'importance
            importance = min(count, 5)
            tags = extract_keywords(k) | extract_keywords(val_text) | {"fact"}
            fiches.append({
                "id": f"long_term_facts_{k}",
                "category": "long_term_facts",
                "tags": list(tags),
                "importance": importance,
                "text": val_text
            })
            
        return fiches

    def retrieve(self, user_message, memory_sources):
        """
        Analyse le message utilisateur, calcule la pertinence de chaque fiche mémoire
        et retourne le contexte sélectionné.
        """
        # Étape 1 : Normalisation
        fiches = self._normalize_memories(memory_sources)
        
        # Étape 2 : Extraction des mots-clés du message utilisateur
        query_keywords = extract_keywords(user_message)
        query_lower = user_message.lower()
        
        # Étape 3 : Scoring avec garde-fous
        scored_fiches = []
        debug_details = []
        
        for f in fiches:
            # Ne pas scorer les fiches CORE permanentes (elles sont traitées à part)
            if f["id"] in CORE_MEMORY_IDS:
                continue
                
            lexical_score = 0
            reasons = []
            
            # +3 par mot-clé correspondant à un tag
            matched_tags = []
            for kw in query_keywords:
                if kw in f["tags"]:
                    lexical_score += 3
                    matched_tags.append(kw)
            if matched_tags:
                reasons.append(f"tags: {', '.join(matched_tags)}")
                
            # +2 par mot-clé présent dans le texte
            text_words = set(re.sub(r"[^\w\s]", " ", f["text"].lower()).split())
            matched_text = []
            for kw in query_keywords:
                if kw in text_words:
                    lexical_score += 2
                    matched_text.append(kw)
            if matched_text:
                reasons.append(f"texte: {', '.join(matched_text)}")
                
            # +1 si catégorie liée
            category_bonus = False
            query_words = set(re.sub(r"[^\w\s]", " ", query_lower).split())
            if f["category"] == "assistant_profile":
                if any(w in query_words for w in ["tu", "toi", "te", "ton", "tes", "anna"]):
                    lexical_score += 1
                    category_bonus = True
            elif f["category"] in ("user_profile", "long_term_facts"):
                if any(w in query_words for w in ["je", "moi", "me", "mon", "ma", "mes", "louis"]):
                    lexical_score += 1
                    category_bonus = True
            if category_bonus:
                reasons.append(f"catégorie {f['category']}")
                
            # Garde-fou 2 : Pas d'importance appliquée si score lexical est nul
            if lexical_score > 0:
                final_score = lexical_score + f["importance"]
                reasons.append(f"importance: +{f['importance']}")
            else:
                final_score = 0
                
            if final_score >= MIN_MEMORY_SCORE:
                scored_fiches.append((final_score, f, reasons))
                
        # Trier par score décroissant, puis par importance
        scored_fiches.sort(key=lambda x: (x[0], x[1]["importance"]), reverse=True)
        
        # Sélectionner les N meilleures fiches dynamiques
        selected_dynamic = scored_fiches[:MAX_RETRIEVED_FACTS]
        
        # Étape 4 : Extraction du noyau permanent de base (Core Memory)
        core_fiches = [f for f in fiches if f["id"] in CORE_MEMORY_IDS]
        
        # Assembler la liste finale (Core + Dynamic)
        injected_facts = list(core_fiches)
        for score, f, reasons in selected_dynamic:
            injected_facts.append(f)
            debug_details.append({
                "id": f["id"],
                "score": score,
                "reasons": reasons
            })
            
        # Nombre de faits ignorés
        ignored_count = len(fiches) - len(injected_facts)
        
        return RetrievedContext(
            injected_facts=injected_facts,
            ignored_count=ignored_count,
            keywords_detected=list(query_keywords),
            debug_details=debug_details
        )
