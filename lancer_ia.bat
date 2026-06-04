@echo off
:: Se déplacer dans le dossier contenant ce script
cd /d "%~dp0"

:: Lancer l'application en arrière-plan sans fenêtre de console noire (GUI)
start "" pythonw main.py
