import sys
import os
import subprocess
import importlib.util
import urllib.request
import json

try:
    import tkinter as tk
    from tkinter import messagebox
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

REQUIREMENTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")

# Mapping requirements package name to python import name
MANDATORY_DEPS = {
    "ollama": "ollama",
    "Pillow": "PIL",
    # Décommenter la ligne ci-dessous pour tester le popup de dépendance manquante en toute sécurité :
    # "fake_required_package_for_test": "fake_module_name"
}

OPTIONAL_DEPS = {
    "sounddevice": "sounddevice",
    "numpy": "numpy",
    "scipy": "scipy",
    "faster-whisper": "faster_whisper",
    "piper-tts": "piper"
}

def is_module_installed(module_name):
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False

def check_ollama_service(url="http://127.0.0.1:11434"):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            return response.status in (200, 204)
    except Exception:
        return False

def check_ollama_model(model_name="gemma4:latest", url="http://127.0.0.1:11434"):
    try:
        api_url = f"{url}/api/tags"
        req = urllib.request.Request(api_url, method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                models = data.get("models", [])
                for m in models:
                    name = m.get("name", "")
                    if name == model_name or name.split(':')[0] == model_name.split(':')[0]:
                        return True
        return False
    except Exception:
        return False

def check_stable_diffusion(url="http://127.0.0.1:7860"):
    try:
        api_url = f"{url}/sdapi/v1/sd-models"
        req = urllib.request.Request(api_url, method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            return response.status == 200
    except Exception:
        return False

def perform_checks():
    missing_required = []
    for pkg, mod in MANDATORY_DEPS.items():
        if not is_module_installed(mod):
            missing_required.append(pkg)
            
    missing_optional = []
    for pkg, mod in OPTIONAL_DEPS.items():
        if not is_module_installed(mod):
            missing_optional.append(pkg)
            
    # Vérification Ollama
    ollama_ok = check_ollama_service()
    
    # Vérification modèle recommandé
    recommended_model = "gemma4:latest"
    recommended_model_ok = False
    if ollama_ok:
        recommended_model_ok = check_ollama_model(recommended_model)
        
    # Vérification Stable Diffusion
    sd_ok = check_stable_diffusion()
    
    # Détermination des fonctionnalités désactivées
    disabled = []
    if "sounddevice" in missing_optional or "numpy" in missing_optional:
        disabled.extend(["stt", "tts"])
    else:
        if "faster-whisper" in missing_optional:
            disabled.append("stt")
        if "piper-tts" in missing_optional:
            disabled.append("tts")
            
    if not sd_ok:
        disabled.append("sd")
        
    # Construction des messages utilisateur
    messages = []
    if not ollama_ok:
        messages.append("⚠️ Le service local Ollama n'est pas détecté. Lancez Ollama pour discuter avec Anna.")
    elif not recommended_model_ok:
        messages.append(f"💡 Modèle gemma4:latest non détecté. Vous pouvez l'installer avec 'ollama pull {recommended_model}' ou choisir un modèle compatible.")
        
    if not sd_ok:
        messages.append("🎨 Stable Diffusion (AUTOMATIC1111) n'est pas détecté. La génération d'images sera inactive.")
        
    can_start = len(missing_required) == 0
    
    return {
        "can_start": can_start,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "ollama_available": ollama_ok,
        "recommended_model_available": recommended_model_ok,
        "stable_diffusion_available": sd_ok,
        "disabled_features": disabled,
        "user_messages": messages
    }

def run_pip_install_sync():
    try:
        res = subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_PATH])
        return res.returncode == 0
    except Exception as e:
        print(f"Erreur pip: {e}")
        return False

def safe_print_console(text):
    # Remplacer les emojis par des équivalents ASCII sûrs
    replacements = {
        "❌": "[X]",
        "✔": "[OK]",
        "⚠": "[!]",
        "⚠️": "[!]",
        "💡": "[INFO]",
        "🎨": "[IMAGE]",
        "•": "-"
    }
    cleaned = text
    for emoji, ascii_val in replacements.items():
        cleaned = cleaned.replace(emoji, ascii_val)
    try:
        print(cleaned)
    except Exception:
        try:
            encoding = sys.stdout.encoding or 'utf-8'
            print(cleaned.encode(encoding, errors='replace').decode(encoding))
        except Exception:
            pass

def run_console_checker():
    safe_print_console("\n==============================================")
    safe_print_console("   ANNA - VÉRIFICATION DES DÉPENDANCES        ")
    safe_print_console("==============================================")
    
    res = perform_checks()
    
    if res["missing_required"]:
        safe_print_console("\n❌ DÉPENDANCES PYTHON OBLIGATOIRES MANQUANTES :")
        for pkg in res["missing_required"]:
            safe_print_console(f"  - {pkg}")
            
        print("\nVoulez-vous installer les dépendances manquantes via pip ? (o/n) : ", end="")
        sys.stdout.flush()
        try:
            choice = input().strip().lower()
            if choice == 'o':
                safe_print_console("\nInstallation en cours (pip install -r requirements.txt)...")
                if run_pip_install_sync():
                    safe_print_console("✔ Installation terminée avec succès.")
                    res = perform_checks()
                    if res["can_start"]:
                        safe_print_console("Toutes les dépendances obligatoires sont désormais installées.")
                    else:
                        safe_print_console("Erreur : Certaines dépendances obligatoires manquent encore.")
                        return False
                else:
                    safe_print_console("❌ L'installation a échoué.")
                    return False
            else:
                safe_print_console("Lancement annulé.")
                return False
        except (KeyboardInterrupt, EOFError):
            safe_print_console("\nAnnulé.")
            return False
            
    if res["missing_optional"]:
        safe_print_console("\n⚠ DÉPENDANCES PYTHON OPTIONNELLES MANQUANTES (Audio Off) :")
        for pkg in res["missing_optional"]:
            safe_print_console(f"  - {pkg}")
        print("\nVoulez-vous installer ces dépendances optionnelles ? (o/n) : ", end="")
        sys.stdout.flush()
        try:
            choice = input().strip().lower()
            if choice == 'o':
                safe_print_console("\nInstallation en cours...")
                run_pip_install_sync()
                res = perform_checks()
        except (KeyboardInterrupt, EOFError):
            pass

    safe_print_console("\nStatut des services locaux :")
    safe_print_console(f"  - Ollama Service    : {'✔ En ligne' if res['ollama_available'] else '❌ Hors ligne'}")
    if res['ollama_available']:
        safe_print_console(f"  - Modèle gemma4     : {'✔ Détecté' if res['recommended_model_available'] else '⚠ Non détecté'}")
    safe_print_console(f"  - Stable Diffusion  : {'✔ En ligne' if res['stable_diffusion_available'] else '⚠ Hors ligne'}")
    
    if res["user_messages"]:
        safe_print_console("\nNotes :")
        for msg in res["user_messages"]:
            safe_print_console(f"  {msg}")
    safe_print_console("==============================================\n")
    return True

if HAS_TKINTER:
    class DependencyCheckerGUI:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("Anna - Vérification de l'environnement")
            self.root.geometry("620x560")
            self.root.configure(bg="#121212")
            self.root.resizable(False, False)
            
            # Centrer la fenêtre
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f'+{x}+{y}')
            
            self.can_proceed = False
            self.results = perform_checks()
            
            self.build_ui()
            self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
            
        def build_ui(self):
            # En-tête
            header_frame = tk.Frame(self.root, bg="#121212")
            header_frame.pack(fill="x", padx=20, pady=15)
            
            title_label = tk.Label(
                header_frame, 
                text="ANNA - Vérification de l'environnement", 
                font=("Arial", 14, "bold"), 
                bg="#121212", 
                fg="#bb86fc"
            )
            title_label.pack(anchor="w")
            
            subtitle_label = tk.Label(
                header_frame, 
                text="Composants nécessaires et services locaux détectés au démarrage", 
                font=("Arial", 9, "italic"), 
                bg="#121212", 
                fg="#888888"
            )
            subtitle_label.pack(anchor="w", pady=(2, 0))
            
            # Zone principale
            self.main_frame = tk.Frame(self.root, bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1)
            self.main_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
            
            # Liste
            self.list_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
            self.list_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            self.refresh_list_ui()
            
            # Zone de logs
            self.log_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
            self.log_text = tk.Text(
                self.log_frame, 
                font=("Consolas", 8), 
                bg="#121212", 
                fg="#88ff88", 
                height=6, 
                state="disabled", 
                relief="flat"
            )
            self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 15))
            
            # Pied de page (boutons)
            footer_frame = tk.Frame(self.root, bg="#121212")
            footer_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 20))
            
            self.btn_install = tk.Button(
                footer_frame, 
                text="📥 Installer dépendances Python", 
                font=("Arial", 10, "bold"), 
                bg="#bb86fc", 
                fg="#121212", 
                activebackground="#c79cfd", 
                activeforeground="#121212",
                relief="flat",
                command=self.start_installation,
                padx=12,
                pady=6,
                cursor="hand2"
            )
            
            if self.results["missing_required"] or self.results["missing_optional"]:
                self.btn_install.pack(side="left")
                
            self.btn_start = tk.Button(
                footer_frame, 
                text="🚀 Démarrer Anna", 
                font=("Arial", 10, "bold"), 
                bg="#03dac6", 
                fg="#121212", 
                activebackground="#04f3dd", 
                activeforeground="#121212",
                relief="flat",
                command=self.start_app,
                padx=18,
                pady=6,
                cursor="hand2"
            )
            self.btn_start.pack(side="right", padx=5)
            
            self.btn_quit = tk.Button(
                footer_frame, 
                text="Quitter", 
                font=("Arial", 10), 
                bg="#333333", 
                fg="white", 
                activebackground="#444444", 
                activeforeground="white",
                relief="flat",
                command=self.quit_app,
                padx=12,
                pady=6,
                cursor="hand2"
            )
            self.btn_quit.pack(side="right")
            
            if not self.results["can_start"]:
                self.btn_start.config(state="disabled", bg="#2c4c49", fg="#666666")
                
        def refresh_list_ui(self):
            for widget in self.list_frame.winfo_children():
                widget.destroy()
                
            self.results = perform_checks()
            
            row = 0
            
            # Dépendances Python Obligatoires
            lbl_cat1 = tk.Label(self.list_frame, text="Bibliothèques Python Obligatoires :", font=("Arial", 10, "bold"), bg="#1e1e1e", fg="#bb86fc")
            lbl_cat1.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 5))
            row += 1
            
            for pkg, mod in MANDATORY_DEPS.items():
                installed = is_module_installed(mod)
                status_text = "✔ Installé" if installed else "❌ Manquant"
                color = "#03dac6" if installed else "#cf6679"
                
                lbl_name = tk.Label(self.list_frame, text=f"  • {pkg}", font=("Arial", 9), bg="#1e1e1e", fg="#e0e0e0")
                lbl_name.grid(row=row, column=0, sticky="w", pady=2)
                
                lbl_status = tk.Label(self.list_frame, text=status_text, font=("Arial", 9, "bold"), bg="#1e1e1e", fg=color)
                lbl_status.grid(row=row, column=1, sticky="w", padx=25, pady=2)
                row += 1
                
            # Dépendances Python Optionnelles
            lbl_cat2 = tk.Label(self.list_frame, text="Bibliothèques Python Optionnelles (Audio STT/TTS) :", font=("Arial", 10, "bold"), bg="#1e1e1e", fg="#bb86fc")
            lbl_cat2.grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 5))
            row += 1
            
            for pkg, mod in OPTIONAL_DEPS.items():
                installed = is_module_installed(mod)
                status_text = "✔ Installé" if installed else "⚠ Absent (Audio désactivé)"
                color = "#03dac6" if installed else "#ffb74d"
                
                lbl_name = tk.Label(self.list_frame, text=f"  • {pkg}", font=("Arial", 9), bg="#1e1e1e", fg="#e0e0e0")
                lbl_name.grid(row=row, column=0, sticky="w", pady=2)
                
                lbl_status = tk.Label(self.list_frame, text=status_text, font=("Arial", 9, "bold"), bg="#1e1e1e", fg=color)
                lbl_status.grid(row=row, column=1, sticky="w", padx=25, pady=2)
                row += 1
                
            # Outils et Services externes
            lbl_cat3 = tk.Label(self.list_frame, text="Services locaux & Modèles (Optionnels au lancement) :", font=("Arial", 10, "bold"), bg="#1e1e1e", fg="#bb86fc")
            lbl_cat3.grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 5))
            row += 1
            
            # Service Ollama
            ollama_ok = self.results["ollama_available"]
            ollama_status = "✔ En ligne" if ollama_ok else "⚠ Hors ligne (Mode dégradé)"
            ollama_color = "#03dac6" if ollama_ok else "#ffb74d"
            lbl_oll_name = tk.Label(self.list_frame, text="  • Service Ollama (127.0.0.1:11434)", font=("Arial", 9), bg="#1e1e1e", fg="#e0e0e0")
            lbl_oll_name.grid(row=row, column=0, sticky="w", pady=2)
            lbl_oll_status = tk.Label(self.list_frame, text=ollama_status, font=("Arial", 9, "bold"), bg="#1e1e1e", fg=ollama_color)
            lbl_oll_status.grid(row=row, column=1, sticky="w", padx=25, pady=2)
            row += 1
            
            # Modèle conseillé
            if ollama_ok:
                model_ok = self.results["recommended_model_available"]
                model_status = "✔ Détecté" if model_ok else "⚠ Absent (pull gemma4 recommandé)"
                model_color = "#03dac6" if model_ok else "#ffb74d"
                lbl_mod_name = tk.Label(self.list_frame, text="  • Modèle gemma4:latest", font=("Arial", 9), bg="#1e1e1e", fg="#e0e0e0")
                lbl_mod_name.grid(row=row, column=0, sticky="w", pady=2)
                lbl_mod_status = tk.Label(self.list_frame, text=model_status, font=("Arial", 9, "bold"), bg="#1e1e1e", fg=model_color)
                lbl_mod_status.grid(row=row, column=1, sticky="w", padx=25, pady=2)
                row += 1
                
            # Stable Diffusion
            sd_ok = self.results["stable_diffusion_available"]
            sd_status = "✔ En ligne" if sd_ok else "⚠ Hors ligne (Génération Off)"
            sd_color = "#03dac6" if sd_ok else "#ffb74d"
            lbl_sd_name = tk.Label(self.list_frame, text="  • Stable Diffusion (127.0.0.1:7860)", font=("Arial", 9), bg="#1e1e1e", fg="#e0e0e0")
            lbl_sd_name.grid(row=row, column=0, sticky="w", pady=2)
            lbl_sd_status = tk.Label(self.list_frame, text=sd_status, font=("Arial", 9, "bold"), bg="#1e1e1e", fg=sd_color)
            lbl_sd_status.grid(row=row, column=1, sticky="w", padx=25, pady=2)
            row += 1
            
        def start_installation(self):
            self.btn_install.config(state="disabled")
            self.btn_start.config(state="disabled")
            self.log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
            
            self.write_log("Démarrage de l'installation via pip...\n")
            
            import threading
            
            def run_install():
                try:
                    process = subprocess.Popen(
                        [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_PATH],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    
                    for line in process.stdout:
                        self.write_log(line)
                        
                    process.wait()
                    
                    if process.returncode == 0:
                        self.root.after(0, self.on_install_success)
                    else:
                        self.root.after(0, lambda: self.on_install_fail(f"Code de retour : {process.returncode}"))
                except Exception as e:
                    self.root.after(0, lambda: self.on_install_fail(str(e)))
                    
            threading.Thread(target=run_install, daemon=True).start()
            
        def write_log(self, text):
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, text)
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
            
        def on_install_success(self):
            self.write_log("\n✔ Dépendances Python installées avec succès !\n")
            self.refresh_list_ui()
            
            if self.results["can_start"]:
                self.btn_start.config(state="normal", bg="#03dac6", fg="#121212")
                
            self.btn_install.pack_forget()
            
        def on_install_fail(self, error_msg):
            self.write_log(f"\n❌ Échec de l'installation : {error_msg}\n")
            self.refresh_list_ui()
            self.btn_install.config(state="normal")
            
            if self.results["can_start"]:
                self.btn_start.config(state="normal", bg="#03dac6", fg="#121212")
                
        def start_app(self):
            self.can_proceed = True
            self.root.destroy()
            
        def quit_app(self):
            self.can_proceed = False
            self.root.destroy()
            sys.exit(0)

def run_checker(is_console=False):
    # Lancement d'une première vérification rapide
    results = perform_checks()
    
    # S'il y a des paquets Python obligatoires OU optionnels manquants, on affiche le vérificateur
    if results["missing_required"] or results["missing_optional"]:
        if is_console or not HAS_TKINTER:
            proceed = run_console_checker()
            if not proceed:
                return None
            return perform_checks()
        else:
            gui = DependencyCheckerGUI()
            gui.root.mainloop()
            if not gui.can_proceed:
                return None
            return perform_checks()
    else:
        # Lancement rapide si tout est déjà installé
        return results
