import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import emotion_manager

def test_emotions():
    test_cases = {
        "C'est vraiment drôle haha !": "amused",
        "Je suis tellement contente de te voir !": "happy",
        "Wow, c'est une surprise incroyable !": "surprised",
        "C'est intéressant, je vais y réfléchir.": "thoughtful",
        "Je suis désolée, c'est triste.": "sad",
        "J'ai un peu peur, je suis stressée.": "worried",
        "Le ciel est bleu aujourd'hui.": "neutral"
    }
    
    print("--- Test du Système d'Émotions ---")
    all_passed = True
    for text, expected in test_cases.items():
        detected = emotion_manager.detect_emotion(text)
        status = "PASS" if detected == expected else f"FAIL (Got: {detected})"
        print(f"Texte: {text}")
        print(f"Attendu: {expected} | Détecté: {detected} -> {status}")
        if detected != expected:
            all_passed = False
        print("-" * 30)
    
    if all_passed:
        print("Tous les tests ont réussi !")
    else:
        print("Certains tests ont échoué.")

if __name__ == "__main__":
    test_emotions()
