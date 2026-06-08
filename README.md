# 🌸 Anna - Votre Assistante IA Personnelle et Locale

Bienvenue dans le projet **Anna** ! 🚀

Anna est une assistante virtuelle intelligente conçue pour fonctionner **directement sur votre ordinateur**, de manière 100% locale. Que vous souhaitiez discuter, générer des images, analyser des documents visuels, piloter votre environnement vocalement ou même déléguer des tâches de création et d'édition de fichiers, Anna est là pour vous accompagner au quotidien.

---

## 🚀 Démarrage rapide (Moins de 2 minutes)

Pour essayer Anna immédiatement :

1. **Installez Python** (version 3.10 ou supérieure) — *pensez à cocher "Add Python to PATH" lors de l'installation sous Windows*.
2. **Installez Git** sur votre ordinateur.
3. **Clonez le dépôt** dans un terminal :
   ```bash
   git clone https://github.com/AnalogShade/ma-propre-ia-locale.git
   cd ma-propre-ia-locale
   ```
4. **Ouvrez le dossier du projet** et lancez l'application :
   * **Sous Windows** : Double-cliquez sur le fichier `lancer_ia.bat` ou lancez `python main.py` dans votre terminal.
   * **Sous macOS / Linux** : Lancez `python main.py` dans votre terminal.
5. **Laissez faire le vérificateur automatique** : Au premier démarrage, s'il manque des modules Python nécessaires, cliquez simplement sur le bouton **Installer dépendances Python** dans la fenêtre qui s'affiche.
6. **Démarrez Anna** !

*Pour aller plus loin et débloquer toutes les fonctionnalités (IA de discussion, voix, génération d'images), consultez les sections détaillées ci-dessous.*

---

## 1. Présentation du projet

### 🤔 Qu'est-ce qu'Anna ?
Anna est un compagnon virtuel intelligent sous forme d'application de bureau. Elle allie la puissance des grands modèles de langage (LLM), de la vision par ordinateur, de la reconnaissance vocale et de la génération d'images pour vous offrir une interface d'interaction complète et autonome. 

### 🎯 Les objectifs d'Anna
L'objectif principal d'Anna est de rendre l'IA avancée accessible à tous, sans dépendance à des abonnements payants ou à des connexions internet permanentes. Anna est conçue pour être :
* **Pratique** : Elle s'intègre à votre espace de travail et peut manipuler des fichiers sur demande.
* **Humaine** : Elle possède un avatar et une personnalité chaleureuse avec laquelle vous pouvez interagir à l'écrit comme à l'oral.
* **Modulaire** : Elle s'adapte à vos ressources matérielles en activant ou désactivant ses modules selon ce qui est installé sur votre PC.

### 🛡️ Nos principes fondamentaux
* **100% Locale** : Tout s'exécute sur votre machine. Vos données de discussion, vos images et vos fichiers ne transitent jamais par des serveurs tiers.
* **Confidentialité absolue** : Pas de pistage, pas de collecte de données, respect total de votre vie privée.
* **Open Source** : Le code est transparent, auditable et ouvert aux contributions pour grandir grâce à la communauté.
* **Résilience** : Pas de plantage si un composant externe (comme un micro ou un GPU puissant) est absent. Anna s'adapte !

---

## 2. Fonctionnalités actuelles

Voici ce qu'Anna est capable de faire aujourd'hui :

* **💬 Conversation naturelle et intelligente** : Dialogue fluide et contextuel avec des modèles d'IA locaux.
* **🎙️ Reconnaissance vocale (STT - Speech-to-Text)** : Parlez à Anna avec votre micro (propulsé localement par Whisper).
* **🗣️ Synthèse vocale (TTS - Text-to-Speech)** : Anna lit ses réponses à haute voix avec une intonation naturelle (propulsé localement par Piper TTS).
* **📂 Gestion et édition de fichiers** : Anna peut analyser, modifier ou créer des fichiers de code ou de texte dans son dossier de travail, sous votre validation.
* **👁️ Support multimodal (Vision)** : Capacité d'analyser des images et d'en décrire le contenu (avec des modèles compatibles).
* **🎨 Génération d'images** : Création d'illustrations à partir de vos descriptions textuelles (via Stable Diffusion).
* **⚙️ Vérification automatique des dépendances** : Un outil intelligent s'occupe de valider votre environnement au démarrage.
* **📉 Mode dégradé adaptatif** : L'application désactive proprement les fonctionnalités associées aux composants matériels ou logiciels manquants sans bloquer le lancement global.

---

## 3. Prérequis

Pour qu'Anna fonctionne au maximum de ses capacités, vous aurez besoin de quelques éléments installés sur votre ordinateur.

### 🛠️ Obligatoire
Ces deux outils sont indispensables pour lancer le projet de base :
1. **Python (version 3.10 ou supérieure)** : Le langage de programmation dans lequel est écrit Anna.
   * *⚠️ Très important sous Windows :* Lors de l'installation de Python, pensez à cocher la case **"Add Python to PATH"** (Ajouter Python au PATH) sur le premier écran de l'installateur.
2. **Git** : Permet de récupérer le projet et de le mettre à jour facilement.

### 🌟 Optionnel mais recommandé
Ces composants permettent de débloquer tout le potentiel d'Anna :
1. **Ollama** : Le logiciel qui permet de faire tourner le modèle de langage localement.
   * Téléchargeable gratuitement sur [ollama.com](https://ollama.com).
2. **Le modèle gemma4:latest** :
   * Une fois Ollama installé et lancé, ouvrez un terminal et tapez `ollama pull gemma4:latest` pour télécharger le modèle recommandé.
3. **AUTOMATIC1111 Stable Diffusion WebUI** :
   * Nécessaire pour la génération d'images. Stable Diffusion doit être configuré pour accepter les requêtes externes (voir la section [Dépannage](#6-dépannage)).

> [!NOTE]
> Si Ollama ou Stable Diffusion ne sont pas détectés au démarrage, Anna désactivera simplement la discussion par IA ou la génération d'images, mais démarrera tout de même. Vous pourrez utiliser les autres outils disponibles.

---

## 4. Installation

Suivez ces étapes simples pour installer Anna sur votre machine :

### Étape 1 : Cloner le dépôt
Ouvrez un terminal (ou une invite de commande sous Windows) et exécutez la commande suivante pour télécharger les fichiers du projet :
```bash
git clone https://github.com/AnalogShade/ma-propre-ia-locale.git
cd ma-propre-ia-locale
```

### Étape 2 : Lancement automatique et installation des modules Python
Vous n'avez pas besoin d'installer manuellement toutes les dépendances Python via de longues lignes de commande. Anna intègre un vérificateur de dépendances automatique.

* **Sous Windows** : Double-cliquez simplement sur le fichier `lancer_ia.bat`.
* **Sous macOS / Linux (ou via Terminal)** : Exécutez la commande suivante :
  ```bash
  python main.py
  ```

### 🤖 Comment fonctionne l'installation automatique ?
Au premier démarrage, Anna va analyser votre système. S'il manque des bibliothèques Python requises (comme `ollama` ou `Pillow`), une fenêtre intuitive va s'ouvrir :
1. Elle listera les éléments manquants.
2. Il vous suffira de cliquer sur le bouton **📥 Installer dépendances Python**.
3. Anna téléchargera et configurera tout à votre place en arrière-plan. Une fois l'opération terminée, le bouton **🚀 Démarrer Anna** deviendra cliquable !

---

## 5. Premier lancement

Lorsque vous lancez Anna pour la première fois, voici ce à quoi vous devez vous attendre :

1. **Vérification d'environnement** : Une petite fenêtre de diagnostic apparaît pour inspecter votre installation (bibliothèques Python obligatoires, modules audio optionnels, connexion à Ollama et Stable Diffusion).
2. **Détection des services locaux** :
   * **Ollama** : Si Ollama est ouvert en arrière-plan, Anna s'y connecte instantanément.
   * **Modèle recommandé** : Anna vérifie si le modèle d'IA conseillé (`gemma4:latest`) est présent.
   * **Stable Diffusion** : Anna vérifie s'il est en ligne et prêt à recevoir des demandes de génération de visuels.
3. **Messages d'avertissement non bloquants** :
   Si certains services ou dépendances optionnelles (comme le microphone) ne sont pas détectés, des messages d'information avec un symbole ⚠️ s'afficheront. Pas d'inquiétude ! L'application vous laissera cliquer sur **Démarrer Anna** pour lancer l'assistant dans un **mode dégradé** (les boutons d'enregistrement micro ou de génération d'images seront simplement indisponibles).

---

## 6. Dépannage (FAQ)

### ❌ Anna ne démarre pas du tout (erreur de commande Python)
* **Cause** : Python n'est pas installé ou n'a pas été ajouté au PATH de votre système d'exploitation lors de son installation.
* **Solution** : Téléchargez à nouveau Python depuis le site officiel. Lancez l'installateur, choisissez "Modifier" ou réinstallez, et veillez à cocher la case **"Add Python to PATH"**.

### ⚠️ Le service Ollama n'est pas détecté
* **Cause** : Le logiciel Ollama n'est pas actif en arrière-plan sur votre PC.
* **Solution** : Lancez Ollama depuis vos applications installées. Vous devez voir l'icône de la tête d'Ollama apparaître dans votre barre des tâches (en bas à droite sous Windows). Une fois l'icône visible, relancez Anna.

### 💡 Le modèle gemma4:latest est marqué absent
* **Cause** : Ollama tourne correctement, mais vous n'avez pas encore téléchargé le modèle recommandé.
* **Solution** : Ouvrez un terminal (invite de commande) et tapez la commande suivante :
  ```bash
  ollama pull gemma4:latest
  ```
  *(Note : Vous pouvez utiliser d'autres modèles en les téléchargeant via Ollama et en les sélectionnant ensuite dans les réglages d'Anna)*.

### 🎙️ Le micro ne fonctionne pas / La synthèse vocale est désactivée
* **Cause** : Les bibliothèques audio nécessaires n'ont pas pu s'installer (généralement en raison de l'absence d'outils de compilation C++ sous Windows pour les modules lourds comme `sounddevice` ou `piper-tts`).
* **Solution** : Anna désactive l'audio pour éviter tout plantage. Vous pouvez continuer à l'utiliser en mode texte. Pour résoudre ce problème, assurez-vous d'avoir installé les [Build Tools pour Visual Studio](https://visualstudio.microsoft.com/fr/visual-cpp-build-tools/) avec l'option de développement en C++, puis cliquez sur réinstaller les dépendances.

### 🎨 Stable Diffusion est marqué hors ligne
* **Cause** : AUTOMATIC1111 n'est pas lancé, ou l'option API n'a pas été activée dans ses paramètres de lancement.
* **Solution** : Pour qu'Anna puisse communiquer avec Stable Diffusion, vous devez ajouter l'option `--api` lors du lancement de votre WebUI. Modifiez votre fichier `webui-user.bat` (sous Windows) pour y inclure cette option :
  ```batch
  set COMMANDLINE_ARGS=--api
  ```
  Lancez ensuite Stable Diffusion, attendez qu'il soit accessible dans votre navigateur, puis relancez Anna.

---

## 7. Structure du projet

Pour vous aider à naviguer dans le code, voici une description simplifiée des fichiers clés :

* 📄 **[main.py](file:///c:/Users/Utilisateur/Documents/Dev/ma%20propre%20ia%20locale/main.py)** : Le point d'entrée central du programme. C'est lui qui orchestre la vérification préliminaire des dépendances, puis décide de lancer l'interface graphique ou le mode console.
* 📄 **[dependency_checker.py](file:///c:/Users/Utilisateur/Documents/Dev/ma%20propre%20ia%20locale/dependency_checker.py)** : Le gardien de votre environnement. Il s'assure que tout est prêt à tourner et gère le téléchargement automatique des modules Python manquants via une interface simple.
* 📄 **[gui.py](file:///c:/Users/Utilisateur/Documents/Dev/ma%20propre%20ia%20locale/gui.py)** : Gère toute l'interface visuelle (fenêtres, chat, boutons, animations de l'avatar et gestion de vos préférences).
* 📄 **[ai_engine.py](file:///c:/Users/Utilisateur/Documents/Dev/ma%20propre%20ia%20locale/ai_engine.py)** : Le cerveau conversationnel. Il gère l'envoi des messages, des fichiers et des images à Ollama pour obtenir des réponses cohérentes.
* 📄 **[stt_manager.py](file:///c:/Users/Utilisateur/Documents/Dev/ma%20propre%20ia%20locale/stt_manager.py)** : Le module d'écoute. Il s'occupe d'enregistrer votre voix et de la traduire instantanément en texte.
* 📄 **[tts_manager.py](file:///c:/Users/Utilisateur/Documents/Dev/ma%20propre%20ia%20locale/tts_manager.py)** : La voix d'Anna. Il convertit le texte produit par l'IA en une voix fluide et parlée.

---

## 8. Contribution

Vous souhaitez contribuer à l'amélioration d'Anna ? Votre aide est la bienvenue ! 💖

* **Signaler un bug** : Si vous rencontrez un dysfonctionnement, vous pouvez ouvrir une *Issue* sur GitHub pour le signaler en décrivant précisément le problème (et en joignant le fichier de diagnostic `data/diagnostic.log` si disponible).
* **Proposer une amélioration** : Si vous souhaitez proposer des modifications de code ou ajouter une fonctionnalité, vous pouvez soumettre vos modifications en ouvrant une *Pull Request*.

---

## 9. Licence

Ce projet est distribué sous la **Licence MIT**. 

Cela signifie que vous êtes entièrement libre de copier, modifier, distribuer et utiliser ce logiciel, que ce soit à des fins personnelles ou professionnelles, à la seule condition de conserver la mention de la licence d'origine.

---
*Fait avec ❤️ pour rendre l'IA locale simple et accessible à tous.*
