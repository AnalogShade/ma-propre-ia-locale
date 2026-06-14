# Manifeste du Projet - Ma Propre IA Locale

Ce document définit les principes de conception, les standards de développement et les lignes directrices pour tout développeur (humain ou agent IA) travaillant sur ce codebase. 

Tout agent de codage IA (comme Antigravity) **doit** lire et respecter scrupuleusement ce manifeste lors de l'exécution de ses tâches.

---

## Principes Fondamentaux

### 1. Approche "LLM-First" (Orientée IA)
* **Lisibilité et clarté statique** : Le code doit être écrit de manière à ce qu'un LLM puisse facilement l'analyser, le comprendre et le modifier sans ambiguïté.
* **Explicite plutôt qu'implicite** : Préférer le typage clair (type hints en Python), les structures de données explicites et éviter la magie ou les abstractions trop dynamiques qui rendent l'analyse statique difficile.
* **Documentation à jour** : Les fonctions importantes doivent avoir des docstrings claires décrivant leurs entrées, sorties et effets secondaires.

### 2. Préservation de l'Existant (Stabilité & Non-régression)
* **Rétrocompatibilité** : Ne jamais introduire de changements destructeurs (breaking changes) sur les fonctionnalités existantes sans validation ou discussion préalable.
* **Intégrité du code** : Préserver tous les commentaires et docstrings existants qui ne sont pas directement liés aux modifications de code en cours.
* **Tests et validation** : Toujours vérifier que le comportement historique de l'application est maintenu après chaque modification.

### 3. Modularité & Séparation des Préoccupations (Separation of Concerns)
* **Responsabilité unique** : Chaque fichier et chaque classe doit avoir une responsabilité unique et bien définie (ex. : gestion du TTS, gestion de l'UI, gestion des émotions, etc.).
* **Découplage** : Minimiser les dépendances directes et l'état global partagé entre les différents modules. Privilégier le passage de paramètres et l'injection de dépendances.
* **Code propre (Clean Code)** : Le code doit être structuré de manière intuitive, ordonnée et facilement maintenable.

### 4. Optimisation avant Mise à l'Échelle (Compute Efficiency)
* **Optimisation des pipelines** : Avant de proposer des solutions matérielles plus lourdes ou de passer à des modèles LLM plus grands/coûteux, s'assurer que le pipeline local (Ollama, STT/TTS, Stable Diffusion, etc.) et les algorithmes actuels sont optimisés.
* **Gestion efficace des ressources** : Minimiser les temps de latence, optimiser la gestion de la mémoire, et éviter les traitements redondants ou les boucles inefficaces.
