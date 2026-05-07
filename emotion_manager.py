def detect_emotion(text):
    """
    Détecte une émotion simple à partir d'une liste de mots-clés dans le texte.
    
    Émotions v1 :
    - amused: rire, haha, ahaha, drôle, amusant
    - happy: contente, heureuse, ravie, super
    - surprised: wow, oh, surprise, étonnée
    - thoughtful: je pense, intéressant, réfléchir
    - sad: triste, désolée
    - worried: peur, inquiète, stressée
    - neutral: sinon
    """
    if not text:
        return "neutral"
        
    text_lower = text.lower()
    
    # Détection par priorité ou ordre simple
    if any(word in text_lower for word in ["rire", "haha", "ahaha", "drôle", "amusant"]):
        return "amused"
    elif any(word in text_lower for word in ["contente", "heureuse", "ravie", "super"]):
        return "happy"
    elif any(word in text_lower for word in ["wow", "oh", "surprise", "étonnée"]):
        return "surprised"
    elif any(word in text_lower for word in ["je pense", "intéressant", "réfléchir"]):
        return "thoughtful"
    elif any(word in text_lower for word in ["triste", "désolée"]):
        return "sad"
    elif any(word in text_lower for word in ["peur", "inquiète", "stressée"]):
        return "worried"
    
    return "neutral"
