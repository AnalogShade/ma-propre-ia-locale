import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import os
from PIL import Image, ImageTk
from stt_manager import STTManager
from tts_manager import TTSManager
from agent_controller import AgentController
import debug_export_service
from config import DEFAULT_ENABLE_COMPRESSED_CONTEXT, DEFAULT_HISTORY_CONTEXT_SIZE


class ConfirmVisionRiskDialog(tk.Toplevel):
    def __init__(self, parent, model_name, model_size_str, gpu_vram_str):
        super().__init__(parent)
        self.title("⚠️ Avertissement de performance")
        self.geometry("450x250")
        self.resizable(False, False)
        self.configure(bg="#1e1e1e")
        self.result = False
        self.dont_warn_again = False
        
        # Centrer par rapport au parent
        self.transient(parent)
        self.grab_set()
        
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 225
            y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 125
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

        label_text = (
            "La taille estimée du modèle est supérieure à la VRAM détectée. "
            "L'analyse d'image pourrait être très lente, échouer, ou faire travailler "
            "fortement votre ordinateur.\n\n"
            f"Modèle actif : {model_name}\n"
            f"Taille estimée du modèle : {model_size_str} Go\n"
            f"VRAM détectée : {gpu_vram_str} Go"
        )
        
        lbl = tk.Label(self, text=label_text, justify="left", bg="#1e1e1e", fg="#e0e0e0", wraplength=410, font=("Arial", 10))
        lbl.pack(padx=20, pady=(20, 10), fill="both", expand=True)
        
        self.var_dont_warn = tk.BooleanVar()
        chk = tk.Checkbutton(
            self, 
            text="Ne plus m'avertir pour ce modèle pendant cette session", 
            variable=self.var_dont_warn,
            bg="#1e1e1e", 
            fg="#e0e0e0", 
            selectcolor="#333333",
            activebackground="#1e1e1e",
            activeforeground="#e0e0e0",
            font=("Arial", 9)
        )
        chk.pack(padx=20, pady=5, anchor="w")
        
        btn_frame = tk.Frame(self, bg="#1e1e1e")
        btn_frame.pack(padx=20, pady=(10, 20), fill="x")
        
        btn_yes = tk.Button(btn_frame, text="Continuer", width=12, command=self.on_yes, bg="#bb86fc", fg="black", activebackground="#9a67db", relief="flat", font=("Arial", 9, "bold"))
        btn_yes.pack(side="right", padx=(10, 0))
        
        btn_no = tk.Button(btn_frame, text="Annuler", width=12, command=self.on_no, bg="#333333", fg="white", activebackground="#444444", relief="flat", font=("Arial", 9))
        btn_no.pack(side="right")
        
        self.protocol("WM_DELETE_WINDOW", self.on_no)
        self.wait_window()

    def on_yes(self):
        self.result = True
        self.dont_warn_again = self.var_dont_warn.get()
        self.destroy()

    def on_no(self):
        self.result = False
        self.destroy()


class AnnaGUI:
    def __init__(self, engine, memory, checker_results=None):
        # Démarrage de la capture des flux console (stdout/stderr)
        debug_export_service.setup_terminal_capture()

        self.ctrl = AgentController()
        
        # Liaison dynamique pour conserver la compatibilité des anciens attributs graphiques
        self.engine = self.ctrl.engine
        self.memory = self.ctrl.memory
        self.files = self.ctrl.files
        self.router = self.ctrl.router
        self.editor = self.ctrl.editor
        self.settings = self.ctrl.settings
        self.ignored_models_this_session = set()
        
        # Fenêtre principale
        self.root = tk.Tk()
        self.root.title("ANNA - IA Locale")
        self.root.geometry("800x600")
        self.root.configure(bg="#121212") # Noir profond
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Layout principal (Gauche: Avatar | Droite: Chat)
        self.main_container = tk.Frame(self.root, bg="#121212")
        self.main_container.pack(expand=True, fill="both", padx=10, pady=10)

        # Initialisation STT & TTS
        disabled_features = checker_results.get("disabled_features", []) if checker_results else []
        
        if "stt" not in disabled_features:
            try:
                self.stt_manager = STTManager(
                    on_model_ready=self._on_stt_ready,
                    on_model_error=self._on_stt_error
                )
            except Exception as e:
                print(f"[GUI STT ERROR] {e}")
                self.stt_manager = None
        else:
            self.stt_manager = None

        if "tts" not in disabled_features:
            try:
                self.tts_manager = TTSManager()
            except Exception as e:
                print(f"[GUI TTS ERROR] {e}")
                self.tts_manager = None
        else:
            self.tts_manager = None
        self.msg_counter = 0
        self.current_tts_tag = None
        self.generating = False

        # Zone Gauche : Conteneur invisible pour empiler l'avatar et les contrôles sous-jacents
        self.left_panel = tk.Frame(self.main_container, bg="#121212")
        self.left_panel.pack(side="left", padx=10, pady=10, anchor="n")

        # Zone Gauche : Avatar Placeholder (dans le conteneur gauche)
        self.left_frame = tk.Frame(self.left_panel, bg="#1e1e1e", width=256, height=256, highlightbackground="#333333", highlightthickness=1)
        self.left_frame.pack(side="top", anchor="n")
        self.left_frame.pack_propagate(False) 
        
        self.avatar_label = tk.Label(self.left_frame, text="Avatar Anna\n(256x256)", bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 12))
        self.avatar_label.place(relx=0.5, rely=0.5, anchor="center")

        # Bouton TTS (Speaker)
        self.tts_button = tk.Button(self.left_frame, text="🔊 Voix", command=self.show_voice_menu, bg="#333333", fg="white", activebackground="#444444", activeforeground="white", relief="flat")
        self.tts_button.pack(side="bottom", pady=(0, 5), fill="x", padx=10)

        # Cadre pour le réglage de volume (placé sous l'avatar dans la zone vide)
        self.volume_frame = tk.Frame(self.left_panel, bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1)
        self.volume_frame.pack(side="top", fill="x", pady=(15, 0))

        # Label dynamique pour afficher le niveau du volume avec son icône
        self.volume_label = tk.Label(self.volume_frame, text="🔉 Volume : 50%", bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 10, "bold"))
        self.volume_label.pack(anchor="w", padx=15, pady=(10, 5))

        # Glissière de contrôle du volume (tk.Scale)
        self.volume_scale = tk.Scale(
            self.volume_frame,
            from_=0,
            to=100,
            orient="horizontal",
            bg="#1e1e1e",
            fg="#e0e0e0",
            troughcolor="#333333",
            activebackground="#03dac6",
            highlightthickness=0,
            bd=0,
            showvalue=False,
            command=self.update_volume
        )
        self.volume_scale.pack(fill="x", padx=15, pady=(0, 10))
        self.volume_scale.set(50)  # Correspond au volume 0.5 par défaut

        # Cadre pour la sélection du modèle (placé sous la glissière de volume)
        self.model_frame = tk.Frame(self.left_panel, bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1)
        self.model_frame.pack(side="top", fill="x", pady=(15, 0))

        self.model_label = tk.Label(self.model_frame, text="🤖 Modèle :", bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 10, "bold"))
        self.model_label.pack(anchor="w", padx=15, pady=(10, 5))

        self.model_var = tk.StringVar(self.root)
        self.model_var.set("Détection...")

        # OptionMenu initialisé avec le placeholder
        self.model_dropdown = tk.OptionMenu(self.model_frame, self.model_var, "Détection...")
        self.model_dropdown.config(
            bg="#333333", 
            fg="white", 
            activebackground="#444444", 
            activeforeground="white", 
            relief="flat", 
            highlightthickness=0
        )
        self.model_dropdown["menu"].config(
            bg="#333333", 
            fg="white", 
            activebackground="#03dac6", 
            activeforeground="black", 
            relief="flat"
        )
        self.model_dropdown.pack(fill="x", padx=15, pady=(0, 10))

        # Cadre pour la génération d'images (Stable Diffusion) - MVC
        self.sd_frame = tk.Frame(self.left_panel, bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1)
        self.sd_frame.pack(side="top", fill="x", pady=(15, 0))

        # En-tête avec titre et bouton rouage Setup
        self.sd_header = tk.Frame(self.sd_frame, bg="#1e1e1e")
        self.sd_header.pack(fill="x", padx=15, pady=(10, 5))

        self.sd_label = tk.Label(self.sd_header, text="🎨 Stable Diffusion :", bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 10, "bold"))
        self.sd_label.pack(side="left")

        self.sd_setup_button = tk.Button(
            self.sd_header, 
            text="⚙️", 
            command=self.show_sd_settings_dialog, 
            bg="#333333", 
            fg="white", 
            activebackground="#444444", 
            activeforeground="white", 
            relief="flat",
            bd=0,
            padx=5
        )
        self.sd_setup_button.pack(side="right")

        # Menu déroulant pour le checkpoint
        self.sd_checkpoint_var = tk.StringVar(self.root)
        self.sd_checkpoint_var.set("Chargement...")

        self.sd_checkpoint_dropdown = tk.OptionMenu(self.sd_frame, self.sd_checkpoint_var, "Chargement...")
        self.sd_checkpoint_dropdown.config(
            bg="#333333", 
            fg="white", 
            activebackground="#444444", 
            activeforeground="white", 
            relief="flat", 
            highlightthickness=0
        )
        self.sd_checkpoint_dropdown["menu"].config(
            bg="#333333", 
            fg="white", 
            activebackground="#bb86fc", 
            activeforeground="black", 
            relief="flat"
        )
        self.sd_checkpoint_dropdown.pack(fill="x", padx=15, pady=(0, 10))

        # Bouton principal "Générer une Image"
        self.sd_generate_button = tk.Button(
            self.sd_frame, 
            text="🖼️ Générer une Image", 
            command=self.toggle_image_generation_mode, 
            bg="#333333", 
            fg="white", 
            activebackground="#444444", 
            activeforeground="white", 
            relief="flat",
            font=("Arial", 10, "bold")
        )
        self.sd_generate_button.pack(fill="x", padx=15, pady=(0, 15))

        # Lancement de la détection asynchrone des checkpoints Stable Diffusion
        threading.Thread(target=self._detect_sd_checkpoints_thread, daemon=True).start()

        # Cadre pour les actions d'utilitaires (Copie des logs)
        self.utils_frame = tk.Frame(self.left_panel, bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1)
        self.utils_frame.pack(side="top", fill="x", pady=(15, 0))

        self.copy_logs_button = tk.Button(
            self.utils_frame, 
            text="📋 Copier logs & traces", 
            command=self.copy_logs_to_clipboard, 
            bg="#333333", 
            fg="white", 
            activebackground="#bb86fc", 
            activeforeground="black", 
            relief="flat",
            font=("Arial", 10, "bold")
        )
        self.copy_logs_button.pack(fill="x", padx=15, pady=15)

        # Chargement de l'image d'avatar
        self.load_avatar()

        # Zone Droite : Conversation
        self.right_frame = tk.Frame(self.main_container, bg="#121212")
        self.right_frame.pack(side="right", expand=True, fill="both")

        # Barre d'état en bas de la zone droite
        self.status_frame = tk.Frame(self.right_frame, bg="#121212")
        self.status_frame.pack(side="bottom", fill="x", padx=5, pady=(2, 2))
        self.status_label = tk.Label(self.status_frame, text="Prêt", bg="#121212", fg="#888888", font=("Arial", 9, "italic"), anchor="w")
        self.status_label.pack(side="left")
        
        # Bouton rouage pour la configuration de la mémoire sémantique et du contexte
        self.context_settings_btn = tk.Button(
            self.status_frame,
            text="⚙️",
            command=self.show_context_settings_dialog,
            bg="#121212",
            fg="#888888",
            activebackground="#222222",
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=5
        )
        self.context_settings_btn.pack(side="right")

        # Bouton de mise à jour manuelle
        btn_text = "🔄"
        try:
            btn_text.encode(sys.stdout.encoding or "utf-8")
        except Exception:
            btn_text = "MAJ"

        self.update_check_btn = tk.Button(
            self.status_frame,
            text=btn_text,
            command=self.manual_update_check,
            bg="#121212",
            fg="#888888",
            activebackground="#222222",
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=5
        )
        self.update_check_btn.pack(side="right", padx=(0, 5))

        # Conteneur pour loger le chat et la trace côte à côte
        self.chat_and_trace_container = tk.Frame(self.right_frame, bg="#121212")
        self.chat_and_trace_container.pack(expand=True, fill="both", padx=5, pady=5)

        self.chat_area = scrolledtext.ScrolledText(self.chat_and_trace_container, wrap=tk.WORD, state='disabled', font=("Arial", 11), bg="#1e1e1e", fg="#e0e0e0", insertbackground="white", bd=0)
        self.chat_area.pack(side="left", expand=True, fill="both")

        # Panneau latéral de trace (masqué par défaut)
        self.trace_panel = tk.Frame(self.chat_and_trace_container, bg="#1e1e1e", width=280, highlightbackground="#333333", highlightthickness=1)
        self.trace_panel.pack_propagate(False)
        
        self.trace_title_label = tk.Label(self.trace_panel, text="🔍 Trace du modèle", bg="#1e1e1e", fg="#bb86fc", font=("Arial", 10, "bold"), pady=8)
        self.trace_title_label.pack(fill="x")
        
        self.trace_text_area = scrolledtext.ScrolledText(self.trace_panel, wrap=tk.WORD, state='disabled', font=("Consolas", 9), bg="#121212", fg="#88ff88", insertbackground="white", bd=0)
        self.trace_text_area.pack(expand=True, fill="both", padx=5, pady=5)
        
        # Texte de trace par défaut
        self.trace_text_area.config(state='normal')
        self.trace_text_area.insert(tk.END, "Aucun contenu de trace disponible.")
        self.trace_text_area.config(state='disabled')
        
        self.trace_visible = False

        # Conteneur pour afficher les miniatures des pièces jointes (non packé par défaut)
        self.attachments_frame = tk.Frame(self.right_frame, bg="#121212")

        # Zone de saisie (tk.Text pour permettre le multi-ligne)
        self.input_frame = tk.Frame(self.right_frame, bg="#121212")
        self.input_frame.pack(fill="x", padx=5, pady=5)

        # Boutons à droite
        self.help_button = tk.Button(self.input_frame, text=" ? ", command=self.show_help, bg="#444444", fg="white", activebackground="#666666", activeforeground="white", relief="flat", padx=10)
        self.help_button.pack(side="right", fill="y", padx=(5, 0))

        self.trace_toggle_btn = tk.Button(
            self.input_frame, 
            text="🔍 Trace", 
            command=self.toggle_trace_panel, 
            bg="#333333", 
            fg="white", 
            activebackground="#444444", 
            activeforeground="white", 
            relief="flat", 
            padx=10
        )
        self.trace_toggle_btn.pack(side="right", fill="y", padx=(5, 0))

        self.send_button = tk.Button(self.input_frame, text="Envoyer", command=self.send_message, bg="#333333", fg="white", activebackground="#444444", activeforeground="white", relief="flat", padx=15)
        self.send_button.pack(side="right", fill="y", padx=(5, 0))

        self.mic_button = tk.Button(
            self.input_frame, 
            text="\u23f3", 
            command=self.toggle_recording,
            font=("Segoe UI", 12), 
            bg="#2d2d2d", 
            fg="white", 
            activebackground="#444444", 
            activeforeground="white",
            relief="flat",
            state="disabled"
        )
        self.mic_button.pack(side="right", fill="y", padx=(5, 0))

        # Puis la zone de texte qui prend tout le reste de la place
        self.user_input = tk.Text(self.input_frame, font=("Arial", 11), bg="#333333", fg="white", 
                                  insertbackground="white", relief="flat", bd=5, height=3)
        self.user_input.pack(side="left", expand=True, fill="x")
        
        # Bindings
        self.attachments = []
        self.user_input.bind("<Return>", self.handle_return)
        self.user_input.bind("<Shift-Return>", self.handle_shift_return)
        self.user_input.bind("<Control-v>", self.handle_paste)
        self.user_input.bind("<Control-V>", self.handle_paste)

        # Message de bienvenue
        self.append_chat("Système", "Bienvenue ! Anna est prête. Clique sur le bouton '?' ou tape /help pour l'aide.")

        # Lancement de la détection asynchrone des modèles installés
        threading.Thread(target=self._detect_models_thread, daemon=True).start()

        # Configuration finale selon l'état des dépendances
        if not self.stt_manager:
            self.mic_button.config(text="🎙️ (Off)", state="disabled", fg="#555555")
        if not self.tts_manager:
            self.tts_button.config(text="🔊 (Off)", state="disabled", fg="#555555")
        if checker_results and "sd" in checker_results.get("disabled_features", []):
            self.sd_generate_button.config(text="🖼️ (SD Off)", state="disabled", bg="#222222", fg="#666666")

        # Affichage des alertes système
        if checker_results and checker_results.get("user_messages"):
            for msg in checker_results["user_messages"]:
                self.append_chat("Système", msg)

        # Lancement de la vérification automatique des mises à jour en tâche de fond (respecte la limite des 24h)
        threading.Thread(target=self._check_for_updates_bg, args=(False,), daemon=True).start()

    # =========================================================================
    # SECTION MISE À JOUR : GESTIONNAIRE DE MISES À JOUR
    # =========================================================================

    def manual_update_check(self):
        """Déclenche une vérification manuelle immédiate (force=True)."""
        self.update_check_btn.config(state="disabled")
        self.update_status("Vérification des mises à jour...", active=True)
        threading.Thread(target=self._check_for_updates_bg, args=(True,), daemon=True).start()

    def _check_for_updates_bg(self, is_manual=False):
        import update_manager
        try:
            update_available, remote_version, error_msg, mode = update_manager.check_for_updates(
                self.settings, force=is_manual
            )
            
            if update_available:
                if error_msg == "local_changes":
                    if is_manual:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "Mise à jour impossible",
                            f"Une mise à jour ({remote_version}) est disponible, mais vous avez des modifications "
                            "locales non validées dans votre dépôt Git.\n\nVeuillez les commiter ou les remiser (stash) "
                            "avant de faire la mise à jour."
                        ))
                    self.root.after(0, lambda: self.update_status("Prêt", active=False))
                else:
                    self.root.after(0, lambda: self._prompt_update(remote_version, mode))
            else:
                if error_msg:
                    if is_manual:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "Échec de la vérification",
                            f"Impossible de contacter le serveur de mise à jour :\n{error_msg}"
                        ))
                    self.root.after(0, lambda: self.update_status("Prêt", active=False))
                else:
                    if is_manual:
                        self.root.after(0, lambda: self.update_status("Anna est à jour", active=False))
                        self.root.after(3000, lambda: self.update_status("Prêt", active=False))
                    else:
                        self.root.after(0, lambda: self.update_status("Prêt", active=False))
        except Exception as e:
            if is_manual:
                self.root.after(0, lambda: messagebox.showwarning(
                    "Erreur de mise à jour",
                    f"Une erreur est survenue lors de la vérification :\n{str(e)}"
                ))
            self.root.after(0, lambda: self.update_status("Prêt", active=False))
        finally:
            self.root.after(0, lambda: self.update_check_btn.config(state="normal"))

    def _prompt_update(self, latest_version, mode):
        self.update_status("Mise à jour disponible", active=True)
        ans = messagebox.askyesno(
            "Mise à jour disponible",
            f"Des mises à jour sont disponibles pour votre application (version/commit : {latest_version}).\n"
            "Voulez-vous fermer Anna et lancer la mise à jour maintenant ?"
        )
        if ans:
            self.update_status("Lancement de l'updater...", active=True)
            import update_manager
            update_manager.start_updater(mode)
            self.root.after(100, self.on_close)
        else:
            self.update_status("Prêt", active=False)

    # =========================================================================
    # SECTION AUDIO : GESTION LOCALE DU MICRO (STT) ET DE LA VOIX (TTS)
    # =========================================================================

    def _on_stt_ready(self):
        self.root.after(0, lambda: self.mic_button.config(text="🎙️", state="normal", fg="white"))

    def _on_stt_error(self, err_msg):
        self.root.after(0, lambda: self.mic_button.config(text="\u274c", state="disabled"))

    def toggle_recording(self):
        if not self.stt_manager:
            return
        if not self.stt_manager.is_recording:
            success, msg = self.stt_manager.start_recording(
                on_phrase_transcribed=self._on_phrase_transcribed,
                on_all_done=self._on_all_done
            )
            if success:
                self.mic_button.config(text="🔴", fg="red")
            else:
                print(f"[GUI] Erreur STT: {msg}")
        else:
            self.mic_button.config(text="🔄", fg="yellow", state="disabled")
            self.stt_manager.stop_recording()

    def _on_phrase_transcribed(self, text):
        def update_gui():
            if text:
                current_idx = self.user_input.index(tk.INSERT)
                if current_idx != "1.0":
                    char_before = self.user_input.get(f"{current_idx}-1c", current_idx)
                    if char_before not in (" ", "\n", "\t"):
                        self.user_input.insert(tk.INSERT, " ")
                self.user_input.insert(tk.INSERT, text)
                self.user_input.insert(tk.INSERT, " ")
                self.user_input.see(tk.INSERT)
        self.root.after(0, update_gui)

    def _on_all_done(self):
        def reset_gui():
            self.mic_button.config(text="🎙️", fg="white", state="normal")
        self.root.after(0, reset_gui)

    def show_voice_menu(self):
        if not self.tts_manager:
            messagebox.showwarning("Audio désactivé", "Le service de synthèse vocale (TTS) est indisponible.")
            return
        menu = tk.Menu(self.root, tearoff=0, bg="#333333", fg="white", activebackground="#03dac6", activeforeground="black")
        voices = self.tts_manager.get_voices()
        
        if not voices:
            menu.add_command(label="T\u00e9l\u00e9charger voix FR (upmc-medium)", command=lambda: self.tts_manager.download_default_voice(self._on_tts_download_progress))
        else:
            for v in voices:
                mark = "\u2713 " if v == self.tts_manager.current_voice_name else "  "
                menu.add_command(label=f"{mark}{v}", command=lambda voice=v: self.tts_manager.load_voice(voice))
            
            menu.add_separator()
            menu.add_command(label="Arr\u00eater la lecture", command=self.tts_manager.stop)
            
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        menu.tk_popup(x, y)

    def _on_tts_download_progress(self, msg):
        self.root.after(0, lambda: self.tts_button.config(text=msg))
        if msg == "Voix pr\u00eate.":
            self.root.after(2000, lambda: self.tts_button.config(text="🔊 Voix"))

    def update_volume(self, val):
        """Met à jour le volume dans le TTSManager et actualise le label."""
        volume_pct = int(val)
        volume_float = volume_pct / 100.0
        if self.tts_manager:
            self.tts_manager.volume = volume_float
        
        # Mettre à jour dynamiquement l'icône et le texte
        if volume_pct == 0:
            self.volume_label.config(text="🔇 Volume : Muet")
        elif volume_pct < 30:
            self.volume_label.config(text=f"🔈 Volume : {volume_pct}%")
        elif volume_pct < 70:
            self.volume_label.config(text=f"🔉 Volume : {volume_pct}%")
        else:
            self.volume_label.config(text=f"🔊 Volume : {volume_pct}%")

    def play_tts(self, message, tag_id):
        if not self.tts_manager:
            return
        # Si on clique sur le même message qui est déjà en cours de lecture : on arrête tout
        if self.tts_manager.is_playing and self.current_tts_tag == tag_id:
            self.tts_manager.stop()
            self.current_tts_tag = None
            return

        # On définit le tag immédiatement pour éviter les conditions de course lors de clics rapides
        self.current_tts_tag = tag_id

        def on_start():
            self.root.after(0, lambda: self.tts_button.config(text="🔊 Lecture...", fg="#03dac6"))
            
        def on_finish():
            self.current_tts_tag = None
            self.root.after(0, lambda: self.tts_button.config(text="🔊 Voix", fg="white"))
            
        self.tts_manager.speak(message, on_start=on_start, on_finish=on_finish)

    def load_avatar(self, emotion="neutral"):
        """Cherche une image dans le dossier avatars selon l'émotion et l'affiche."""
        avatar_dir = "avatars"
        img_path = os.path.join(avatar_dir, f"{emotion}.png")

        # Si l'image d'émotion n'existe pas, on tente neutral.png
        if not os.path.exists(img_path):
            img_path = os.path.join(avatar_dir, "neutral.png")
        
        # Si toujours rien, on regarde l'ancien dossier 'avatar' par compatibilité
        if not os.path.exists(img_path):
            old_avatar_dir = "avatar"
            if os.path.exists(old_avatar_dir):
                valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
                images = [f for f in os.listdir(old_avatar_dir) if f.lower().endswith(valid_extensions)]
                if images:
                    img_path = os.path.join(old_avatar_dir, images[0])

        if os.path.exists(img_path):
            try:
                # Ouvrir et redimensionner
                img = Image.open(img_path)
                img = img.resize((256, 256), Image.Resampling.LANCZOS)
                
                # Convertir pour Tkinter
                self.tk_avatar = ImageTk.PhotoImage(img)
                self.avatar_label.config(image=self.tk_avatar, text="")
            except Exception as e:
                print(f"Erreur chargement avatar: {e}")

    def update_avatar(self, emotion):
        """Met à jour l'avatar de manière sécurisée (thread-safe si appelé via after)."""
        self.load_avatar(emotion)

    def toggle_trace_panel(self):
        if self.trace_visible:
            self.trace_panel.pack_forget()
            self.trace_visible = False
            self.trace_toggle_btn.config(bg="#333333", fg="white")
        else:
            # Réorganiser le packing pour donner la priorité de dimension au panneau de trace
            self.chat_area.pack_forget()
            self.trace_panel.pack(side="right", fill="both", padx=(5, 0))
            self.chat_area.pack(side="left", expand=True, fill="both")
            self.trace_visible = True
            self.trace_toggle_btn.config(bg="#bb86fc", fg="black")

    def update_trace_content(self, text):
        try:
            self.trace_text_area.config(state='normal')
            self.trace_text_area.delete("1.0", tk.END)
            if not text or not text.strip():
                self.trace_text_area.insert(tk.END, "Aucun contenu de trace disponible.")
            else:
                self.trace_text_area.insert(tk.END, text)
            self.trace_text_area.config(state='disabled')
            self.trace_text_area.yview(tk.END)
        except Exception:
            pass

    def update_status(self, text, active=True):
        try:
            if active:
                self.status_label.config(text=text, fg="#03dac6")
            else:
                self.status_label.config(text=text, fg="#888888")
        except Exception:
            pass

    def split_response(self, accumulated_text):
        # Sépare la trace de raisonnement <think>...</think> de la réponse finale propre
        if "<think>" in accumulated_text:
            parts = accumulated_text.split("<think>", 1)
            before_think = parts[0]
            rest = parts[1]
            if "</think>" in rest:
                think_parts = rest.split("</think>", 1)
                thinking_text = think_parts[0]
                final_text = before_think + think_parts[1]
            else:
                thinking_text = rest
                final_text = before_think
            return thinking_text, final_text
        else:
            return "", accumulated_text

    def start_streaming_response(self, sender):
        try:
            self.chat_area.config(state='normal')
            assistant_name = self.memory.assistant_profile.get("nom", "Anna")
            if sender == assistant_name:
                self.current_streaming_tag = f"tts_tag_{self.msg_counter}"
                self.msg_counter += 1
                self.chat_area.insert(tk.END, f"\n{sender} : ", ("bold", "clickable_name", self.current_streaming_tag))
            else:
                self.current_streaming_tag = None
                self.chat_area.insert(tk.END, f"\n{sender} : ", "bold")
            self.chat_area.config(state='disabled')
            self.chat_area.yview(tk.END)
            self.is_streamed = True
            self.accumulated_response = ""
            self.printed_final_text_len = 0
        except Exception:
            pass

    def append_streaming_chunk(self, text):
        try:
            self.chat_area.config(state='normal')
            self.chat_area.insert(tk.END, text)
            self.chat_area.config(state='disabled')
            self.chat_area.yview(tk.END)
        except Exception:
            pass

    def finalize_streaming_response(self, full_text):
        try:
            self.chat_area.config(state='normal')
            self.chat_area.insert(tk.END, "\n")
            self.chat_area.config(state='disabled')
            self.chat_area.yview(tk.END)
            
            self.chat_area.tag_config("bold", font=("Arial", 11, "bold"), foreground="#bb86fc")
            self.chat_area.tag_config("clickable_name", foreground="#03dac6", underline=True)
            
            if self.current_streaming_tag:
                self.chat_area.tag_bind(
                    self.current_streaming_tag,
                    "<Button-1>",
                    lambda e, msg=full_text, tid=self.current_streaming_tag: self.play_tts(msg, tid)
                )
        except Exception:
            pass

    def handle_stream_chunk(self, chunk):
        self.accumulated_response += chunk
        
        # Buffering pour intercepter la balise <think> naissante au tout début du flux
        stripped = self.accumulated_response.lstrip()
        if len(stripped) < 7 and "<think>".startswith(stripped):
            # En cours de détection de la balise <think> au démarrage
            return
            
        thinking_text, final_text = self.split_response(self.accumulated_response)
        
        if thinking_text:
            self.update_trace_content(thinking_text)
            
        new_chars = final_text[self.printed_final_text_len:]
        if new_chars:
            self.append_streaming_chunk(new_chars)
            self.printed_final_text_len += len(new_chars)

    def append_chat(self, sender, message):
        self.chat_area.config(state='normal')
        
        assistant_name = self.memory.assistant_profile.get("nom", "Anna")
        
        if sender == assistant_name:
            tag_name = f"tts_tag_{self.msg_counter}"
            self.msg_counter += 1
            self.chat_area.insert(tk.END, f"\n{sender} : ", ("bold", "clickable_name", tag_name))
            
            # Bind the click event to play TTS for this specific message (toggle mode)
            self.chat_area.tag_bind(tag_name, "<Button-1>", lambda e, msg=message, tid=tag_name: self.play_tts(msg, tid))
        else:
            self.chat_area.insert(tk.END, f"\n{sender} : ", "bold")
            
        self.chat_area.insert(tk.END, f"{message}\n")
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)
        # Couleurs des tags pour le mode sombre
        self.chat_area.tag_config("bold", font=("Arial", 11, "bold"), foreground="#bb86fc") # Une touche de violet pour les noms
        self.chat_area.tag_config("clickable_name", foreground="#03dac6", underline=True)

    def append_chat_image(self, image_to_show):
        """Affiche une miniature de l'image insérée dans le fil de discussion."""
        self.chat_area.config(state='normal')
        try:
            # Créer une copie et redimensionner pour l'affichage dans le chat
            img = image_to_show.copy()
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            # Conserver une référence dans l'objet chat_area pour empêcher le garbage collection
            if not hasattr(self, 'chat_photos'):
                self.chat_photos = []
            self.chat_photos.append(photo)
            
            # Label pour afficher l'image
            img_lbl = tk.Label(self.chat_area, image=photo, bg="#1e1e1e", highlightthickness=1, highlightbackground="#333333")
            
            # Insérer une nouvelle ligne et le label
            self.chat_area.insert(tk.END, "\n")
            self.chat_area.window_create(tk.END, window=img_lbl)
            self.chat_area.insert(tk.END, "\n")
        except Exception as e:
            print(f"[GUI ERROR] Impossible d'afficher l'image dans le chat : {e}")
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)

    def handle_return(self, event):
        """Envoie le message sur Entrée simple."""
        self.send_message()
        return "break" # Empêche le saut de ligne par défaut

    def handle_shift_return(self, event):
        """Laisse faire le saut de ligne sur Shift+Entrée."""
        pass

    def handle_paste(self, event=None):
        # 1. Grab image from clipboard
        try:
            from PIL import ImageGrab
            data = ImageGrab.grabclipboard()
        except Exception as e:
            print(f"[GUI WARNING] Échec de la récupération du presse-papiers : {e}")
            return None

        # 2. Check if we actually have image data or file paths containing images
        image_to_attach = None
        file_path = None
        
        if data is None:
            return None # Pas d'image, laisser faire le coller de texte par défaut
            
        if isinstance(data, list):
            # C'est une liste de fichiers copiés (Windows Explorer)
            valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif')
            for path in data:
                if isinstance(path, str) and path.lower().endswith(valid_exts):
                    try:
                        from PIL import Image
                        image_to_attach = Image.open(path)
                        file_path = path
                        break
                    except Exception:
                        pass
        elif hasattr(data, 'verify') or hasattr(data, 'save'):
            # C'est une image PIL directe
            image_to_attach = data
            
        if not image_to_attach:
            return None # Pas d'image valide, laisser faire le coller par défaut
            
        # 3. On a bien une image ! Maintenant, vérifions la compatibilité du modèle
        active_model = self.ctrl.engine.model
        if not self.ctrl.engine.does_model_support_vision(active_model):
            # Avertir l'utilisateur de manière non bloquante
            self.update_status("Erreur : Le modèle actif ne supporte pas la vision.", active=True)
            self.append_chat("Système", f"⚠️ Le modèle sélectionné ({active_model}) ne supporte pas les images. Veuillez basculer vers llama3.2-vision ou un autre modèle vision.")
            return "break" # Intercepter pour empêcher Tkinter de coller des débris textuels
            
        # 4. Le modèle est compatible, on ajoute la pièce jointe
        self.add_attachment(image_to_attach, file_path)
        return "break"

    def add_attachment(self, pil_image, file_path=None):
        from attachments import ImageAttachment
        attachment = ImageAttachment(pil_image, file_path)
        self.attachments.append(attachment)
        print(f"[GUI] Pièce jointe ajoutée : {attachment.get_display_name()}")
        self.update_attachments_ui()

    def update_attachments_ui(self):
        # Supprimer tous les widgets existants dans la zone des miniatures
        for widget in self.attachments_frame.winfo_children():
            widget.destroy()
            
        if not self.attachments:
            self.attachments_frame.pack_forget()
            return
            
        # Afficher le cadre au-dessus de la saisie
        self.attachments_frame.pack(before=self.input_frame, fill="x", padx=5, pady=(0, 5))
        
        # Conserver les références d'images Tkinter pour empêcher le garbage collection
        self.attachment_photos = []
        
        for idx, att in enumerate(self.attachments):
            if att.get_type() == "image":
                thumb_frame = tk.Frame(self.attachments_frame, bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1)
                thumb_frame.pack(side="left", padx=5, pady=2)
                
                try:
                    img_copy = att.image.copy()
                    img_copy.thumbnail((60, 60), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img_copy)
                    self.attachment_photos.append(photo)
                    
                    img_label = tk.Label(thumb_frame, image=photo, bg="#1e1e1e")
                    img_label.pack(side="left", padx=(5, 2), pady=5)
                except Exception as e:
                    print(f"[GUI ERROR] Miniature échouée : {e}")
                    err_lbl = tk.Label(thumb_frame, text="[IMG]", bg="#1e1e1e", fg="white")
                    err_lbl.pack(side="left", padx=(5, 2), pady=5)
                
                disp_name = att.get_display_name()
                if len(disp_name) > 15:
                    disp_name = disp_name[:12] + "..."
                name_lbl = tk.Label(thumb_frame, text=disp_name, bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 9))
                name_lbl.pack(side="left", padx=2, pady=5)
                
                btn_remove = tk.Button(
                    thumb_frame, 
                    text="❌", 
                    command=lambda a=att: self.remove_attachment(a),
                    bg="#1e1e1e", 
                    fg="#cf6679", 
                    activebackground="#333333", 
                    activeforeground="#cf6679",
                    relief="flat", 
                    bd=0,
                    cursor="hand2"
                )
                btn_remove.pack(side="left", padx=(2, 5), pady=5)

    def remove_attachment(self, attachment):
        if attachment in self.attachments:
            self.attachments.remove(attachment)
            attachment.clean()
            self.update_attachments_ui()

    def show_help(self):
        """Affiche la liste des commandes disponibles."""
        help_text = """COMMANDES DISPONIBLES :

Langage Naturel :
- "Ouvre le fichier <chemin>"
- "Ferme le fichier"
- "Recharge le fichier"

Commandes Slash :
/openfile <chemin> : Charger un fichier texte
/listfiles : Voir les fichiers chargés
/closefile <nom> : Fermer un fichier
/reloadfile <nom> : Recharger un fichier modifié
/clear : Effacer l'historique de discussion
/model <nom> : Changer le modèle Ollama
/quit : Quitter l'application

Note : Shift + Entrée pour un saut de ligne."""
        messagebox.showinfo("Aide - Commandes", help_text)

    def handle_file_intent(self, text):
        """Utilise l'IA pour détecter et traiter l'intention via le routeur unifié."""
        result = self.router.process_intent(text, self.files)
        
        if result.get("handled"):
            self.append_chat("Système", result.get("message"))
            return True
            
        # Tâche 4.1 : Notification système pour load_context sans couper le flux
        if result.get("action") == "load_context" and result.get("message"):
            self.append_chat("Système", result.get("message"))
            
        return False

    def set_input_state(self, enabled=True):
        def do_update():
            try:
                state = "normal" if enabled else "disabled"
                self.user_input.config(state=state)
                self.send_button.config(state=state)
                if enabled:
                    self.send_button.config(bg="#333333", fg="white")
                else:
                    self.send_button.config(bg="#222222", fg="#666666")
            except Exception:
                pass
        self.root.after(0, do_update)

    def send_message(self):
        if self.generating:
            return

        msg = self.user_input.get("1.0", tk.END).strip()
        if not msg and not self.attachments:
            return

        # 1. Vérifier la présence d'images
        has_image = any(att.get_type() == "image" for att in self.attachments)

        # 2. Injection texte par défaut si image présente et texte vide
        final_msg = msg
        if has_image and not msg:
            final_msg = "Décris précisément l'image jointe."

        # 3. Vérifier le support vision
        active_model = self.ctrl.engine.model
        if has_image:
            if not self.ctrl.engine.does_model_support_vision(active_model):
                self.update_status("Erreur : Le modèle actif ne supporte pas la vision.", active=True)
                self.append_chat("Système", f"⚠️ Le modèle sélectionné ({active_model}) ne supporte pas les images. Veuillez basculer vers llama3.2-vision ou un autre modèle vision.")
                return

        # 4. Préparer/redimensionner/comprimer l'image
        image_paths = []
        for att in self.attachments:
            if att.get_type() == "image":
                try:
                    path = att.prepare_for_api("data/attachments")
                    image_paths.append(path)
                except Exception as prep_err:
                    self.append_chat("Système", f"⚠️ Erreur de préparation d'image : {prep_err}")
                    return

        # 5. Évaluer le risque avec evaluate_request_risk
        image_infos = []
        for att in self.attachments:
            if att.get_type() == "image":
                image_infos.append({
                    "width": att.final_width,
                    "height": att.final_height,
                    "file_size_kb": att.file_size_kb
                })

        risk_analysis = self.ctrl.engine.evaluate_request_risk(active_model, image_infos=image_infos)
        risk_level = risk_analysis.get("level", "low_risk")

        # 6. Si high_risk, demander confirmation de manière non-destructrice
        if has_image and risk_level == "high_risk":
            if active_model not in self.ignored_models_this_session:
                model_size = risk_analysis.get("model_size_gb")
                gpu_vram = risk_analysis.get("gpu_vram_gb")
                model_size_str = f"{model_size:.1f}" if model_size is not None else "Inconnu"
                gpu_vram_str = f"{gpu_vram:.1f}" if gpu_vram is not None else "Inconnu"
                
                # Utiliser la boîte de dialogue personnalisée
                dialog = ConfirmVisionRiskDialog(self.root, active_model, model_size_str, gpu_vram_str)
                if not dialog.result:
                    # L'utilisateur annule : on ne touche à rien
                    return
                
                if dialog.dont_warn_again:
                    self.ignored_models_this_session.add(active_model)
        
        # 7. Si moderate_risk, mettre à jour le statut
        if has_image and risk_level == "moderate_risk":
            if risk_analysis.get("confidence") == "low":
                self.update_status("⚠️ Performance incertaine : l’analyse peut être lente.", active=True)
            else:
                self.update_status("⚠️ Modèle lourd détecté : l’analyse peut être lente.", active=True)

        # 8. Sauvegarder les pièces jointes à nettoyer
        attachments_to_clean = list(self.attachments)

        # 9. Gestion des commandes spéciales (Fichiers)
        if msg.startswith('/'):
            # Vider la zone de saisie et miniatures pour les commandes slash
            self.user_input.delete("1.0", tk.END)
            self.attachments = []
            self.update_attachments_ui()
            
            slash_result = self.ctrl.process_slash_command(msg)
            if slash_result:
                if slash_result.get("action") == "help":
                    self.show_help()
                elif slash_result.get("action") == "change_model":
                    self.append_chat("Système", slash_result.get("message"))
                    self.model_var.set(self.ctrl.engine.model)
                else:
                    self.append_chat("Système", slash_result.get("message"))
                return

        # Interception de confirmation de génération d'image pour démarrer le polling
        if msg.strip().lower() == "ok" and self.ctrl.image_manager.is_active() and self.ctrl.image_manager.state.get("step") == "waiting_for_confirmation":
            self.sd_generating = True
            self.show_progress_block()
            threading.Thread(target=self._poll_sd_progress_thread, daemon=True).start()

        # 10. Diagnostics dans les logs
        from config import log_diagnostic
        log_diagnostic(
            f"[DIAGNOSTIC ENVOI]\n"
            f"  Modèle actif             : {active_model}\n"
            f"  Présence d'images        : {has_image} ({len(image_paths)} images)\n"
            f"  Texte final envoyé       : {repr(final_msg)}\n"
            f"  Chemins temporaires      : {image_paths}\n"
            f"  Évaluation du risque     : {risk_level} ({risk_analysis.get('reason')})\n"
        )

        # Marquer la génération comme active et désactiver la saisie
        self.generating = True
        self.set_input_state(False)

        # Lancer le traitement dans un thread pour ne pas geler l'interface
        threading.Thread(target=self.process_ai_response, args=(final_msg, image_paths, attachments_to_clean, msg), daemon=True).start()

    def process_ai_response(self, user_input, images=None, attachments_to_clean=None, original_msg=""):
        print(f"\n[DIAGNOSTIC] RAW USER MESSAGE:\n{user_input}\n")
        
        self.is_streamed = False
        self.accumulated_response = ""
        self.printed_final_text_len = 0
        
        # Effacer l'ancien texte de trace et afficher un message d'attente
        self.root.after(0, lambda: self.update_trace_content("Aucun contenu de trace disponible."))
        self.root.after(0, lambda: self.update_status("Préparation du contexte...", active=True))
        
        assistant_name = self.memory.assistant_profile.get("nom", "Anna")
        
        # Callback to clear UI inputs and display user message once the Ollama request starts
        has_started_ui = [False]
        def on_start_callback():
            if has_started_ui[0]:
                return
            has_started_ui[0] = True
            
            def do_start():
                # Affichage dans le chat
                if original_msg:
                    self.append_chat("Vous", original_msg)
                else:
                    self.append_chat("Vous", "[Image jointe]")

                if attachments_to_clean:
                    for att in attachments_to_clean:
                        if att.get_type() == "image":
                            self.append_chat_image(att.image)

                # Vider la zone de saisie et miniatures (bascule temporaire à 'normal' requise si désactivé)
                self.user_input.config(state="normal")
                self.user_input.delete("1.0", tk.END)
                if self.generating:
                    self.user_input.config(state="disabled")
                self.attachments = []
                self.update_attachments_ui()
                
            self.root.after(0, do_start)

        # Callbacks thread-safe via lambda/root.after
        def chunk_callback(chunk):
            def handle_chunk():
                if not self.is_streamed:
                    self.start_streaming_response(assistant_name)
                self.handle_stream_chunk(chunk)
            self.root.after(0, handle_chunk)
            
        def status_callback(status_text):
            self.root.after(0, lambda: self.update_status(status_text, active=True))

        try:
            result = self.ctrl.process_user_message_sync(
                user_input, 
                images=images,
                chunk_callback=chunk_callback,
                status_callback=status_callback,
                on_start_callback=on_start_callback
            )
            
            def display_response_and_diffs():
                self.generating = False
                self.set_input_state(True)
                self.update_status("Prêt", active=False)
                
                # Arrêt propre du thread de progression et retrait du bloc temporaire
                self.sd_generating = False
                self.remove_progress_block()
                
                res_type = result.get("type")
                
                # S'assurer que l'UI est mise à jour (vidée) si la requête a réussi (ou s'est terminée normalement)
                # mais que on_start_callback n'a pas été appelé (ex: intent router sans Ollama)
                if res_type != "error":
                    on_start_callback()
                
                assistant_name = self.memory.assistant_profile.get("nom", "Anna")
                
                # --- INTERCEPTION MODE DE GÉNÉRATION D'IMAGES (TÂCHE 8) ---
                if res_type == "image_parameters_proposal":
                    self.show_image_proposal_block(result.get("content"), result.get("message"))
                    return
                elif res_type == "image_simulation_result":
                    self.show_image_simulation_block(result.get("content"))
                    self.sd_generate_button.config(text="🖼️ Générer une Image", bg="#333333", fg="white")
                    return
                elif res_type == "image_generation_result":
                    self.show_real_image_block(result.get("content"))
                    self.sd_generate_button.config(text="🖼️ Générer une Image", bg="#333333", fg="white")
                    return
                elif res_type == "image_cancelled":
                    self.append_chat("Système", result.get("message"))
                    self.sd_generate_button.config(text="🖼️ Générer une Image", bg="#333333", fg="white")
                    return
                elif res_type == "image_normal_chat":
                    self.append_chat("Système", result.get("message"))
                    return
                
                # --- COMPORTEMENT D'ORIGINE ---
                if res_type == "intent_handled":
                    self.append_chat("Système", result.get("message"))
                    
                elif res_type == "error":
                    title = "ERREUR SYSTÈME"
                    if self.ctrl.image_manager.is_active() or self.sd_generate_button.cget("text") == "🎨 Mode Image Actif":
                        title = "ÉCHEC DE LA GÉNÉRATION"
                        self.sd_generate_button.config(text="🖼️ Générer une Image", bg="#333333", fg="white")
                        self.ctrl.image_manager.cancel_session()
                    
                    self.show_error_block(title, result.get("message"))
                    return
                    
                elif res_type == "ai_response" or res_type == "text":
                    if result.get("system_notification"):
                        self.append_chat("Système", result.get("system_notification"))
                        
                    response = result.get("content")
                    
                    # Si streaming actif, finaliser la mise en forme du chat, sinon append synchrone classique
                    if self.is_streamed:
                        self.finalize_streaming_response(response)
                    else:
                        self.append_chat(assistant_name, response)
                    
                    emotion = result.get("emotion", "neutral")
                    self.update_avatar(emotion)
                    
                    create_blocks = result.get("create_blocks", [])
                    edit_blocks = result.get("edit_blocks", [])
                    
                    all_blocks = []
                    for block in create_blocks:
                        all_blocks.append(("create", block))
                    for block in edit_blocks:
                        all_blocks.append(("edit", block))
                        
                    if len(all_blocks) == 1:
                        # Conserver le comportement d'origine pour un seul bloc
                        b_type, block = all_blocks[0]
                        if b_type == "create":
                            self.show_diff_block(block['file_path'], "create", create_content=block['content'])
                        else:
                            self.show_diff_block(
                                block['file_path'], "edit", 
                                search_content=block['search_content'], 
                                replace_content=block['replace_content'],
                                invalid=block.get('invalid', False),
                                error_message=block.get('error_message', "")
                            )
                    elif len(all_blocks) >= 2:
                        # Cadre conteneur pour regrouper tous les changements
                        container_frame = tk.Frame(self.chat_area, bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1, bd=0, padx=10, pady=10)
                        
                        pending_list = []
                        btn_apply_all = None
                        btn_cancel_all = None
                        
                        # Désactiver automatiquement les boutons globaux s'il n'y a plus aucun bloc pending
                        def update_global_buttons():
                            has_pending = any(b["state"]["status"] == "pending" for b in pending_list)
                            if not has_pending:
                                if btn_apply_all and btn_apply_all.winfo_exists():
                                    btn_apply_all.config(state="disabled")
                                if btn_cancel_all and btn_cancel_all.winfo_exists():
                                    btn_cancel_all.config(state="disabled")
                                    
                        for idx, (b_type, block) in enumerate(all_blocks):
                            # Séparateur entre les blocs
                            if idx > 0:
                                separator = tk.Frame(container_frame, height=1, bg="#333333", bd=0)
                                separator.pack(fill="x", pady=10)
                                
                            if b_type == "create":
                                self.show_diff_block(
                                    block['file_path'], "create", 
                                    create_content=block['content'],
                                    parent_frame=container_frame,
                                    pending_list=pending_list,
                                    on_state_change=update_global_buttons
                                )
                            else:
                                self.show_diff_block(
                                    block['file_path'], "edit", 
                                    search_content=block['search_content'], 
                                    replace_content=block['replace_content'],
                                    invalid=block.get('invalid', False),
                                    error_message=block.get('error_message', ""),
                                    parent_frame=container_frame,
                                    pending_list=pending_list,
                                    on_state_change=update_global_buttons
                                )
                                
                        # Séparateur avant les boutons globaux
                        separator = tk.Frame(container_frame, height=1, bg="#333333", bd=0)
                        separator.pack(fill="x", pady=10)
                        
                        global_btn_frame = tk.Frame(container_frame, bg="#1e1e1e")
                        global_btn_frame.pack(fill="x", pady=(5, 0))
                        
                        def apply_all():
                            if btn_apply_all and btn_apply_all.winfo_exists():
                                btn_apply_all.config(state="disabled")
                            if btn_cancel_all and btn_cancel_all.winfo_exists():
                                btn_cancel_all.config(state="disabled")
                            
                            for b in pending_list:
                                if b["state"]["status"] == "pending":
                                    if not b["invalid"]:
                                        try:
                                            b["apply"]()
                                        except Exception as ex:
                                            print(f"[GUI ERROR] Échec de l'application globale d'un bloc : {ex}")
                                    else:
                                        try:
                                            b["cancel"]()
                                        except Exception as ex:
                                            print(f"[GUI ERROR] Échec de l'invalidation globale d'un bloc : {ex}")
                                            
                        def cancel_all():
                            if btn_apply_all and btn_apply_all.winfo_exists():
                                btn_apply_all.config(state="disabled")
                            if btn_cancel_all and btn_cancel_all.winfo_exists():
                                btn_cancel_all.config(state="disabled")
                                
                            for b in pending_list:
                                if b["state"]["status"] == "pending":
                                    try:
                                        b["cancel"]()
                                    except Exception as ex:
                                        print(f"[GUI ERROR] Échec du rejet global d'un bloc : {ex}")
                                        
                        btn_apply_all = tk.Button(global_btn_frame, text="✓ Tout appliquer", command=apply_all, bg="#03dac6", fg="black", activebackground="#018786", relief="flat", font=("Arial", 9, "bold"), padx=15, pady=5)
                        btn_apply_all.pack(side="left", padx=(0, 10))
                        
                        btn_cancel_all = tk.Button(global_btn_frame, text="✗ Tout rejeter", command=cancel_all, bg="#444444", fg="white", activebackground="#666666", relief="flat", font=("Arial", 9), padx=15, pady=5)
                        btn_cancel_all.pack(side="left")
                        
                        # Insertion du conteneur dans le chat_area
                        self.chat_area.config(state='normal')
                        self.chat_area.insert(tk.END, "\n")
                        self.chat_area.window_create(tk.END, window=container_frame)
                        self.chat_area.insert(tk.END, "\n")
                        self.chat_area.config(state='disabled')
                        self.chat_area.yview(tk.END)
                        
            self.root.after(0, display_response_and_diffs)
        except Exception as e:
            # Vérifier si c'est un timeout d'Ollama (httpx.TimeoutException ou message contenant "timeout")
            is_timeout = False
            try:
                import httpx
                if isinstance(e, httpx.TimeoutException):
                    is_timeout = True
            except ImportError:
                pass
            
            if not is_timeout and "timeout" in str(e).lower():
                is_timeout = True
                
            if is_timeout:
                # Gestion propre du timeout : libérer l'état GUI et informer l'utilisateur
                def handle_timeout():
                    self.generating = False
                    self.set_input_state(True)
                    self.update_status("Prêt", active=False)
                    self.sd_generating = False
                    self.remove_progress_block()
                    self.append_chat("Système", "⚠️ L'analyse d'image a pris trop de temps ou Ollama ne répond plus. Vous pouvez réessayer avec une image plus petite ou un modèle vision plus léger.")
                self.root.after(0, handle_timeout)
            else:
                print(f"[GUI ERROR] Crash dans le traitement de l'IA : {e}")
                self.root.after(0, lambda: self.show_error_block("ERREUR INTERNE", f"Une erreur s'est produite lors du traitement : {e}"))
                self.root.after(0, lambda: self.set_input_state(True))
                self.root.after(0, lambda: self.update_status("Prêt", active=False))
        finally:
            if attachments_to_clean and has_started_ui[0]:
                for att in attachments_to_clean:
                    try:
                        att.clean()
                    except Exception as clean_err:
                        print(f"[GUI WARNING] Échec nettoyage pièce jointe : {clean_err}")

    def _detect_models_thread(self):
        """Thread d'arrière-plan pour détecter les modèles Ollama installés."""
        models = self.engine.get_installed_models()
        self.root.after(0, lambda: self._update_model_dropdown(models))

    def _update_model_dropdown(self, models):
        """Met à jour le widget OptionMenu avec la liste des modèles trouvés."""
        menu = self.model_dropdown["menu"]
        menu.delete(0, "end")
        
        if not models:
            self.model_var.set("Ollama indisponible")
            menu.add_command(label="Ollama indisponible", state="disabled")
            self.model_dropdown.config(state="disabled")
            self.append_chat("Système", "⚠️ Service Ollama non détecté ou aucun modèle installé localement. Vérifie qu'Ollama est bien démarré.")
            return

        self.model_dropdown.config(state="normal")
        
        for model in models:
            menu.add_command(label=model, command=lambda m=model: self.on_model_selected(m))
            
        current_active = self.engine.model
        
        # Recherche d'une correspondance intelligente (ex: "llama3" correspond à "llama3:latest")
        matched_model = None
        if current_active in models:
            matched_model = current_active
        else:
            # Recherche d'un modèle de base identique (sans le tag après les deux-points)
            for m in models:
                if m.split(':')[0] == current_active.split(':')[0]:
                    matched_model = m
                    break
        
        if matched_model:
            self.model_var.set(matched_model)
            # On synchronise le nom exact du modèle avec tags dans l'application
            self.engine.model = matched_model
            self.router.model = matched_model
        else:
            fallback_model = models[0]
            self.model_var.set(fallback_model)
            self.on_model_selected(fallback_model)
            self.append_chat("Système", f"Modèle '{current_active}' non trouvé localement. Repli sur : {fallback_model}")

    def on_model_selected(self, model_name):
        """Callback appelé lors de la sélection d'un modèle."""
        self.model_var.set(model_name)
        self.engine.model = model_name
        self.router.model = model_name
        self.settings.set_setting("selected_model", model_name)
        print(f"[SETTINGS] Modèle configuré à chaud : {model_name}")

    def show_diff_block(self, file_path, block_type, search_content="", replace_content="", create_content="", invalid=False, error_message="", parent_frame=None, pending_list=None, on_state_change=None):
        """
        Crée un cadre Tkinter contenant le diff visuel et les boutons interactifs,
        et l'insère directement dans la zone de chat ou dans un parent_frame.
        """
        # Activer le chat pour insertion
        if not parent_frame:
            self.chat_area.config(state='normal')
        
        # Création du cadre principal du Diff
        if parent_frame:
            diff_frame = tk.Frame(parent_frame, bg="#1e1e1e", bd=0, padx=5, pady=5)
        else:
            diff_frame = tk.Frame(self.chat_area, bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1, bd=0, padx=10, pady=10)
        
        title_text = f"📂 CRÉATION DE FICHIER : {file_path}" if block_type == "create" else f"📂 MODIFICATION DE FICHIER : {file_path}"
        title = tk.Label(diff_frame, text=title_text, bg="#1e1e1e", fg="#bb86fc", font=("Arial", 10, "bold"), anchor="w")
        title.pack(fill="x", pady=(0, 5))
        
        # Zone de texte de Diff
        diff_text = tk.Text(diff_frame, wrap=tk.WORD, font=("Consolas", 10), bg="#2d2d2d", fg="#e0e0e0", bd=0, height=8, width=70)
        diff_text.tag_config("minus", background="#4a1515", foreground="#ff8080")
        diff_text.tag_config("plus", background="#154a15", foreground="#80ff80")
        diff_text.tag_config("info", foreground="#888888")
        
        if block_type == "create":
            for line in create_content.splitlines():
                diff_text.insert(tk.END, f"+ {line}\n", "plus")
        else:
            for line in search_content.splitlines():
                diff_text.insert(tk.END, f"- {line}\n", "minus")
            diff_text.insert(tk.END, "=========================================\n", "info")
            for line in replace_content.splitlines():
                diff_text.insert(tk.END, f"+ {line}\n", "plus")
                
        diff_text.config(state="disabled")
        diff_text.pack(fill="both", expand=True, pady=5)
        
        # Cadre pour les boutons
        btn_frame = tk.Frame(diff_frame, bg="#1e1e1e")
        btn_frame.pack(fill="x", pady=(5, 0))
        
        # Variables de boutons explicites
        btn_apply = None
        btn_cancel = None
        block_state = {"status": "invalid" if invalid else "pending"}
        
        # Label d'erreur dynamique (affiché initialement si invalide, mis à jour si échec d'application)
        error_status_label = tk.Label(btn_frame, text=f"⚠ {error_message}" if invalid else "", bg="#1e1e1e", fg="#ff5555", font=("Arial", 9, "bold"), wraplength=500, justify="left", anchor="w")
        if invalid:
            error_status_label.pack(fill="x", pady=(0, 5))
            
        # Label de statut visuel (ex: Appliqué, Annulé, Échoué)
        status_label = tk.Label(btn_frame, text="", bg="#1e1e1e", font=("Arial", 9, "bold"))
        status_label.pack(side="left", padx=10)
        
        def update_ui_for_status():
            status = block_state["status"]
            if status == "applied":
                status_label.config(text="✓ Appliqué", fg="#80ff80")
                if btn_apply and btn_apply.winfo_exists():
                    btn_apply.config(state="disabled")
                if btn_cancel and btn_cancel.winfo_exists():
                    btn_cancel.config(state="disabled")
            elif status == "cancelled":
                status_label.config(text="✗ Annulé", fg="#888888")
                if btn_apply and btn_apply.winfo_exists():
                    btn_apply.config(state="disabled")
                if btn_cancel and btn_cancel.winfo_exists():
                    btn_cancel.config(state="disabled")
            elif status == "failed":
                status_label.config(text="⚠ Échoué", fg="#ff5555")
                if btn_apply and btn_apply.winfo_exists():
                    btn_apply.config(state="disabled")
                if btn_cancel and btn_cancel.winfo_exists():
                    btn_cancel.config(state="disabled")
            elif status == "invalid":
                status_label.config(text="⚠ Invalide", fg="#ff5555")
            else:
                status_label.config(text="", fg="#e0e0e0")
        
        # État et actions des boutons
        def on_apply():
            if block_state["status"] not in ("pending", "failed"):
                return False
            
            if btn_apply and btn_apply.winfo_exists():
                btn_apply.config(state="disabled")
            if btn_cancel and btn_cancel.winfo_exists():
                btn_cancel.config(state="disabled")
            
            if block_type == "create":
                success, msg = self.editor.create_file(file_path, create_content, working_dir=self.files.working_dir)
                self.append_chat("Système", msg)
                if success:
                    block_state["status"] = "applied"
                    self.files.load_file(file_path)
                else:
                    block_state["status"] = "failed"
                    error_status_label.config(text=f"⚠ {msg}")
                    error_status_label.pack(fill="x", pady=(0, 5))
            else:
                from pathlib import Path
                if not Path(file_path).is_absolute() and self.files.working_dir:
                    abs_path = (Path(self.files.working_dir) / file_path).resolve()
                else:
                    abs_path = Path(file_path).resolve()
                    
                success, msg = self.editor.apply_edit(abs_path, search_content, replace_content)
                self.append_chat("Système", msg)
                if success:
                    block_state["status"] = "applied"
                    self.files.load_file(file_path)
                else:
                    block_state["status"] = "failed"
                    error_status_label.config(text=f"⚠ {msg}")
                    error_status_label.pack(fill="x", pady=(0, 5))
            
            update_ui_for_status()
            if on_state_change:
                on_state_change()
            return success
            
        def on_cancel():
            if block_state["status"] != "pending":
                return
            block_state["status"] = "cancelled"
            
            if btn_apply and btn_apply.winfo_exists():
                btn_apply.config(state="disabled")
            if btn_cancel and btn_cancel.winfo_exists():
                btn_cancel.config(state="disabled")
            if invalid:
                self.append_chat("Système", f"Signalement de '{file_path}' ignoré.")
            else:
                self.append_chat("Système", f"Modification de '{file_path}' annulée.")
            
            update_ui_for_status()
            if on_state_change:
                on_state_change()
            
        action_title = "Créer le fichier" if block_type == "create" else "Appliquer"
        
        if invalid:
            btn_cancel = tk.Button(btn_frame, text="✗ Ignorer", command=on_cancel, bg="#444444", fg="white", activebackground="#666666", relief="flat", font=("Arial", 9), padx=15, pady=5)
            btn_cancel.pack(side="left")
        else:
            btn_apply = tk.Button(btn_frame, text=f"✓ {action_title}", command=on_apply, bg="#03dac6", fg="black", activebackground="#018786", relief="flat", font=("Arial", 9, "bold"), padx=15, pady=5)
            btn_apply.pack(side="left", padx=(0, 10))
            
            btn_cancel = tk.Button(btn_frame, text="✗ Annuler", command=on_cancel, bg="#444444", fg="white", activebackground="#666666", relief="flat", font=("Arial", 9), padx=15, pady=5)
            btn_cancel.pack(side="left")
            
        # Initialiser l'état de l'UI
        update_ui_for_status()
        
        # Enregistrer le bloc dans pending_list s'il est fourni (inclut aussi les invalides avec leur statut actuel)
        if pending_list is not None:
            pending_list.append({
                "state": block_state,
                "apply": on_apply,
                "cancel": on_cancel,
                "invalid": invalid
            })
            
        if parent_frame:
            diff_frame.pack(fill="x", pady=5)
        else:
            # Insertion en tant que fenêtre en ligne dans la chat_area
            self.chat_area.insert(tk.END, "\n")
            self.chat_area.window_create(tk.END, window=diff_frame)
            self.chat_area.insert(tk.END, "\n")
            
            self.chat_area.config(state='disabled')
            self.chat_area.yview(tk.END)

    def _detect_sd_checkpoints_thread(self):
        """Détecte de manière asynchrone les checkpoints Stable Diffusion (locaux ou en ligne)."""
        checkpoints = []
        try:
            # 1. On tente d'interroger le service en ligne si disponible
            if self.ctrl.image_manager.service.is_api_available():
                checkpoints = self.ctrl.image_manager.service.get_online_checkpoints()
        except Exception as e:
            print(f"[GUI WARNING] Échec de l'accès à l'API SD en arrière-plan : {e}")
            
        # 2. Si aucun checkpoint trouvé via l'API, on scanne le dossier local via ImageSettingsManager
        if not checkpoints:
            try:
                checkpoints = self.ctrl.image_manager.settings.scan_checkpoints()
            except Exception as e:
                print(f"[GUI WARNING] Échec du scan local de checkpoints : {e}")
                
        self.root.after(0, lambda: self._update_sd_checkpoint_dropdown(checkpoints))

    def _update_sd_checkpoint_dropdown(self, checkpoints):
        """Met à jour le widget OptionMenu avec la liste des checkpoints trouvés."""
        menu = self.sd_checkpoint_dropdown["menu"]
        menu.delete(0, "end")
        
        if not checkpoints:
            self.sd_checkpoint_var.set("Aucun checkpoint")
            menu.add_command(label="Aucun checkpoint", state="disabled")
            return
            
        for cp in checkpoints:
            menu.add_command(label=cp, command=lambda c=cp: self.on_sd_checkpoint_selected(c))
            
        # Sélection par défaut : dernière sélectionnée ou première disponible
        saved_cp = self.ctrl.image_manager.settings.selected_checkpoint
        if saved_cp and saved_cp in checkpoints:
            self.sd_checkpoint_var.set(saved_cp)
        else:
            first_cp = checkpoints[0]
            self.sd_checkpoint_var.set(first_cp)
            self.ctrl.image_manager.settings.set_selected_checkpoint(first_cp)

    def on_sd_checkpoint_selected(self, checkpoint_name):
        """Callback appelé lors de la sélection d'un checkpoint Stable Diffusion."""
        self.sd_checkpoint_var.set(checkpoint_name)
        self.ctrl.image_manager.settings.set_selected_checkpoint(checkpoint_name)
        print(f"[IMAGE SETTINGS] Checkpoint SD configuré à chaud : {checkpoint_name}")

    def show_sd_settings_dialog(self):
        """Affiche une boîte de dialogue Tkinter (Toplevel) pour configurer les dossiers Stable Diffusion."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Configuration Stable Diffusion")
        dialog.geometry("450x320")
        dialog.configure(bg="#1e1e1e")
        dialog.transient(self.root)
        dialog.grab_set()

        # Rendre le dialogue centré par rapport à la fenêtre parente
        dialog.geometry(f"+{self.root.winfo_x() + 50}+{self.root.winfo_y() + 50}")

        # Labels et Entrées
        tk.Label(dialog, text="⚙️ CONFIGURATION STABLE DIFFUSION", bg="#1e1e1e", fg="#bb86fc", font=("Arial", 11, "bold")).pack(pady=(15, 15))

        # URL API
        tk.Label(dialog, text="URL API de Stable Diffusion (ex: http://127.0.0.1:7860) :", bg="#1e1e1e", fg="#e0e0e0", anchor="w").pack(fill="x", padx=20)
        api_entry = tk.Entry(dialog, bg="#333333", fg="white", insertbackground="white", relief="flat", bd=5)
        api_entry.pack(fill="x", padx=20, pady=(5, 10))
        api_entry.insert(0, self.ctrl.image_manager.settings.api_url)

        # Dossier Installation
        tk.Label(dialog, text="Dossier d'installation Stable Diffusion (optionnel) :", bg="#1e1e1e", fg="#e0e0e0", anchor="w").pack(fill="x", padx=20)
        install_entry = tk.Entry(dialog, bg="#333333", fg="white", insertbackground="white", relief="flat", bd=5)
        install_entry.pack(fill="x", padx=20, pady=(5, 10))
        install_entry.insert(0, self.ctrl.image_manager.settings.install_dir)

        # Dossier Checkpoints
        tk.Label(dialog, text="Dossier des checkpoints Stable Diffusion (optionnel) :", bg="#1e1e1e", fg="#e0e0e0", anchor="w").pack(fill="x", padx=20)
        checkpoints_entry = tk.Entry(dialog, bg="#333333", fg="white", insertbackground="white", relief="flat", bd=5)
        checkpoints_entry.pack(fill="x", padx=20, pady=(5, 10))
        checkpoints_entry.insert(0, self.ctrl.image_manager.settings.checkpoints_dir)

        # Boutons Sauvegarder et Fermer
        btn_frame = tk.Frame(dialog, bg="#1e1e1e")
        btn_frame.pack(fill="x", padx=20, pady=(15, 0))

        def save():
            self.ctrl.image_manager.settings.set_api_url(api_entry.get())
            self.ctrl.image_manager.settings.set_install_dir(install_entry.get())
            self.ctrl.image_manager.settings.set_checkpoints_dir(checkpoints_entry.get())
            
            # Recalculer l'affichage dans le formulaire
            install_entry.delete(0, tk.END)
            install_entry.insert(0, self.ctrl.image_manager.settings.install_dir)
            checkpoints_entry.delete(0, tk.END)
            checkpoints_entry.insert(0, self.ctrl.image_manager.settings.checkpoints_dir)
            
            # Relancer le scan des checkpoints dans un thread
            threading.Thread(target=self._detect_sd_checkpoints_thread, daemon=True).start()
            
            messagebox.showinfo("Succès", "Configuration sauvegardée avec succès !", parent=dialog)
            dialog.destroy()

        save_btn = tk.Button(btn_frame, text="✓ Enregistrer", command=save, bg="#03dac6", fg="black", activebackground="#018786", relief="flat", padx=15, pady=5)
        save_btn.pack(side="left")

        cancel_btn = tk.Button(btn_frame, text="Annuler", command=dialog.destroy, bg="#444444", fg="white", activebackground="#666666", relief="flat", padx=15, pady=5)
        cancel_btn.pack(side="right")

    def show_context_settings_dialog(self):
        """Affiche une boîte de dialogue pour configurer la mémoire et la taille du contexte."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Réglages du Contexte")
        dialog.geometry("450x250")
        dialog.configure(bg="#1e1e1e")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrer par rapport à la fenêtre parente
        dialog.geometry(f"+{self.root.winfo_x() + 100}+{self.root.winfo_y() + 100}")

        # Titre
        tk.Label(dialog, text="⚙️ CONFIGURATION DU CONTEXTE DE L'IA", bg="#1e1e1e", fg="#bb86fc", font=("Arial", 11, "bold")).pack(pady=(15, 15))

        # Slider de taille de contexte
        tk.Label(dialog, text="Nombre de messages récents envoyés mot à mot (contexte chronologique) :", bg="#1e1e1e", fg="#e0e0e0", anchor="w").pack(fill="x", padx=20)
        
        current_size = self.ctrl.settings.get_setting("history_context_size", DEFAULT_HISTORY_CONTEXT_SIZE)
        
        scale = tk.Scale(
            dialog,
            from_=2,
            to=40,
            orient="horizontal",
            bg="#1e1e1e",
            fg="#e0e0e0",
            troughcolor="#333333",
            activebackground="#03dac6",
            highlightthickness=0,
            bd=0,
            showvalue=True
        )
        scale.pack(fill="x", padx=20, pady=(5, 15))
        scale.set(current_size)

        # Case à cocher pour le tampon de contexte compressé
        current_enable = self.ctrl.settings.get_setting("enable_compressed_context", DEFAULT_ENABLE_COMPRESSED_CONTEXT)
        enable_var = tk.BooleanVar(value=current_enable)
        
        chk = tk.Checkbutton(
            dialog,
            text="Activer la compression sémantique du contexte (Mémoire Roulante)",
            variable=enable_var,
            bg="#1e1e1e",
            fg="#e0e0e0",
            selectcolor="#333333",
            activebackground="#1e1e1e",
            activeforeground="white",
            relief="flat",
            bd=0
        )
        chk.pack(anchor="w", padx=20, pady=(0, 15))

        # Boutons Sauvegarder et Fermer
        btn_frame = tk.Frame(dialog, bg="#1e1e1e")
        btn_frame.pack(fill="x", padx=20, pady=(10, 0))

        def save():
            self.ctrl.settings.set_setting("history_context_size", int(scale.get()))
            self.ctrl.settings.set_setting("enable_compressed_context", enable_var.get())
            messagebox.showinfo("Succès", "Configuration du contexte sauvegardée avec succès !", parent=dialog)
            dialog.destroy()

        save_btn = tk.Button(btn_frame, text="✓ Enregistrer", command=save, bg="#03dac6", fg="black", activebackground="#018786", relief="flat", padx=15, pady=5)
        save_btn.pack(side="left")

        cancel_btn = tk.Button(btn_frame, text="Annuler", command=dialog.destroy, bg="#444444", fg="white", activebackground="#666666", relief="flat", padx=15, pady=5)
        cancel_btn.pack(side="right")

    def toggle_image_generation_mode(self):
        """Bascule le mode de génération d'image de façon conversationnelle (LLM-First)."""
        if self.ctrl.image_manager.is_active():
            # 1. Annuler la session dans le contrôleur principal (MVC)
            self.ctrl.image_manager.cancel_session()
            
            # 2. Restaurer l'apparence d'origine du bouton et notifier dans le chat
            self.sd_generate_button.config(text="🖼️ Générer une Image", bg="#333333", fg="white")
            self.append_chat("Système", "[🎨 MODE IMAGE DÉSACTIVÉ] Retour au mode discussion standard.")
        else:
            # 1. Démarrer la session dans le contrôleur principal (MVC)
            self.ctrl.start_image_session()
            
            # 2. Mettre à jour visuellement le bouton et notifier l'utilisateur dans le chat
            self.sd_generate_button.config(text="🎨 Mode Image Actif", bg="#bb86fc", fg="black")
            self.append_chat("Système", "[🎨 MODE IMAGE ACTIVÉ] Décrivez l'image que vous souhaitez générer ci-dessous. (ex: 'Un petit chat astronaute'). Réappuyez sur ce bouton pour désactiver le mode.")

    def show_image_proposal_block(self, proposal, system_message):
        """Affiche une carte de pré-génération stylisée avec tous les paramètres SD, directement dans le chat."""
        self.chat_area.config(state='normal')
        
        # Cadre principal avec bordure violette
        card_frame = tk.Frame(self.chat_area, bg="#1e1e1e", highlightbackground="#bb86fc", highlightthickness=1, bd=0, padx=15, pady=12)
        
        # En-tête
        title = tk.Label(card_frame, text="🎨 PROPOSITION DE PARAMÈTRES IMAGE", bg="#1e1e1e", fg="#bb86fc", font=("Arial", 10, "bold"), anchor="w")
        title.pack(fill="x", pady=(0, 8))
        
        # Détails des paramètres
        details = [
            ("Description :", proposal.get("description_originale", "")),
            ("Style détecté :", proposal.get("style", "Non spécifié")),
            ("Prompt positif :", proposal.get("prompt", "")),
            ("Prompt négatif :", proposal.get("negative_prompt", "")),
            ("Dimensions :", f"{proposal.get('width', 512)} x {proposal.get('height', 512)}"),
            ("Steps :", str(proposal.get("steps", 25))),
            ("CFG Scale :", str(proposal.get("cfg_scale", 7.5))),
            ("Sampler :", proposal.get("sampler", "Euler a")),
            ("Checkpoint :", proposal.get("checkpoint", "Par défaut")),
            ("Seed :", str(proposal.get("seed", -1)))
        ]
        
        for label, val in details:
            row = tk.Frame(card_frame, bg="#1e1e1e")
            row.pack(fill="x", pady=2)
            lbl = tk.Label(row, text=f"• {label} ", bg="#1e1e1e", fg="#03dac6", font=("Arial", 9, "bold"), anchor="w", width=16)
            lbl.pack(side="left")
            val_lbl = tk.Label(row, text=val, bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 9), anchor="w", justify="left", wraplength=450)
            val_lbl.pack(side="left", fill="x", expand=True)

        # Message d'instruction
        msg_lbl = tk.Label(card_frame, text=f"\n💬 {system_message}", bg="#1e1e1e", fg="#a0a0a0", font=("Arial", 9, "italic"), justify="left", wraplength=450)
        msg_lbl.pack(fill="x", pady=(5, 0))
        
        # Insertion dans le chat
        self.chat_area.insert(tk.END, "\n")
        self.chat_area.window_create(tk.END, window=card_frame)
        self.chat_area.insert(tk.END, "\n")
        
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)

    def show_real_image_block(self, result_content):
        """Affiche une carte graphique de génération réelle contenant l'image PNG et ses métadonnées."""
        self.chat_area.config(state='normal')
        
        # 1. Chargement et redimensionnement fluide de l'image via PIL
        image_path = result_content.get("image_path")
        photo = None
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                img.thumbnail((350, 350), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"[GUI ERROR] Erreur lors du rendu de l'image physique : {e}")

        # 2. Création de la carte stylisée (bordure violette pour la génération réelle)
        card_frame = tk.Frame(self.chat_area, bg="#1e1e1e", highlightbackground="#bb86fc", highlightthickness=1, bd=0, padx=15, pady=12)
        
        # En-tête de la carte
        title = tk.Label(card_frame, text="✨ GÉNÉRATION D'IMAGE RÉELLE TERMINÉE ✨", bg="#1e1e1e", fg="#bb86fc", font=("Arial", 10, "bold"), anchor="w")
        title.pack(fill="x", pady=(0, 8))
        
        # 3. Widget d'affichage de l'image (avec sauvegarde de la référence Tkinter)
        if photo:
            img_label = tk.Label(card_frame, image=photo, bg="#1e1e1e")
            img_label.pack(pady=10)
            card_frame.photo = photo  # Prévention stricte du garbage collection
        else:
            err_label = tk.Label(card_frame, text="⚠️ Impossible d'afficher l'image physique.", bg="#1e1e1e", fg="#cf6679", font=("Arial", 10, "italic"))
            err_label.pack(pady=10)

        # 4. Panneau des métadonnées de génération (Seed, Checkpoint, Sampler, etc.)
        details_frame = tk.Frame(card_frame, bg="#1e1e1e")
        details_frame.pack(fill="x", pady=(5, 0))
        
        params = result_content.get("params", {})
        details = [
            ("Prompt Final :", params.get("prompt", "")),
            ("Checkpoint :", params.get("checkpoint", "") or "Par défaut"),
            ("Seed finale :", str(params.get("seed", ""))),
            ("Sampler :", params.get("sampler", "Euler a")),
            ("Steps / CFG :", f"{params.get('steps', 25)} steps / {params.get('cfg_scale', 7.5)} CFG")
        ]
        
        for label, val in details:
            row = tk.Frame(details_frame, bg="#1e1e1e")
            row.pack(fill="x", pady=2)
            lbl = tk.Label(row, text=f"• {label} ", bg="#1e1e1e", fg="#03dac6", font=("Arial", 9, "bold"), anchor="w", width=15)
            lbl.pack(side="left")
            val_lbl = tk.Label(row, text=val, bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 9), anchor="w", justify="left", wraplength=450)
            val_lbl.pack(side="left", fill="x", expand=True)

        # 5. Insertion en tant que fenêtre en ligne dans la chat_area
        self.chat_area.insert(tk.END, "\n")
        self.chat_area.window_create(tk.END, window=card_frame)
        self.chat_area.insert(tk.END, "\n")
        
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)

    def show_progress_block(self):
        """Crée et insère un bloc de progression temporaire et stylisé dans le fil de discussion."""
        self.chat_area.config(state='normal')
        
        # Conteneur principal (Cadre avec bordure cyan)
        self.progress_frame = tk.Frame(self.chat_area, bg="#1e1e1e", highlightbackground="#03dac6", highlightthickness=1, bd=0, padx=15, pady=10)
        
        # Label de statut/progression
        self.progress_label = tk.Label(
            self.progress_frame, 
            text="🎨 Connexion à Stable Diffusion en cours...", 
            bg="#1e1e1e", 
            fg="#03dac6", 
            font=("Arial", 10, "bold")
        )
        self.progress_label.pack(side="left")
        
        # Insertion en tant que fenêtre en ligne dans la chat_area
        self.chat_area.insert(tk.END, "\n")
        self.chat_area.window_create(tk.END, window=self.progress_frame)
        self.chat_area.insert(tk.END, "\n")
        
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)

    def update_progress_block(self, text):
        """Met à jour le texte du bloc de progression de manière thread-safe."""
        if hasattr(self, 'progress_label') and self.progress_label:
            self.root.after(0, lambda: self.progress_label.config(text=text))

    def remove_progress_block(self):
        """Supprime proprement le bloc de progression de l'interface de manière thread-safe."""
        def safe_destroy():
            if hasattr(self, 'progress_frame') and self.progress_frame:
                try:
                    self.progress_frame.destroy()
                except Exception:
                    pass
                self.progress_frame = None
                self.progress_label = None
        self.root.after(0, safe_destroy)

    def _poll_sd_progress_thread(self):
        """Thread compagnon de polling de progression Stable Diffusion en arrière-plan."""
        import time
        print("[SD POLLING] Thread de progression démarré.")
        dots = ""
        while hasattr(self, 'sd_generating') and self.sd_generating:
            try:
                # Cycle des trois petits points : "." -> ".." -> "..." -> "."
                dots = "." * ((len(dots) % 3) + 1)
                
                progress_data = self.ctrl.image_manager.service.get_generation_progress()
                progress = progress_data.get("progress", 0.0)
                eta = progress_data.get("eta", 0.0)
                
                # Mise à jour graphique in-place avec animation des points
                status_text = f"🎨 Génération en cours : {progress}% (Reste env. {eta}s) {dots}"
                self.update_progress_block(status_text)
                
                # Affichage des logs en console pour la validation
                print(f"[SD POLLING] Progress: {progress}% - ETA: {eta}s {dots}")
            except Exception as e:
                print(f"[SD POLLING WARNING] Échec de la récupération : {e}")
            time.sleep(1.0)
        print("[SD POLLING] Thread de progression arrêté.")

    def show_error_block(self, title, message):
        """Affiche un encadré rouge esthétique pour les erreurs critiques dans le chat d'Anna."""
        self.chat_area.config(state='normal')
        
        # Cadre d'erreur rouge profond Material
        card_frame = tk.Frame(self.chat_area, bg="#1e1e1e", highlightbackground="#cf6679", highlightthickness=1, bd=0, padx=15, pady=12)
        
        # En-tête de l'erreur
        header = tk.Label(card_frame, text=f"❌ {title}", bg="#1e1e1e", fg="#cf6679", font=("Arial", 10, "bold"), anchor="w")
        header.pack(fill="x", pady=(0, 5))
        
        # Message explicatif de l'erreur
        msg_lbl = tk.Label(card_frame, text=message, bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 9), anchor="w", justify="left", wraplength=450)
        msg_lbl.pack(fill="x")
        
        # Insertion en ligne
        self.chat_area.insert(tk.END, "\n")
        self.chat_area.window_create(tk.END, window=card_frame)
        self.chat_area.insert(tk.END, "\n")
        
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)

    def show_image_simulation_block(self, result_content):
        """Affiche une carte de simulation finale de génération d'image, avec un placeholder graphique et canvas."""
        self.chat_area.config(state='normal')
        
        # Cadre principal avec bordure cyan
        card_frame = tk.Frame(self.chat_area, bg="#1e1e1e", highlightbackground="#03dac6", highlightthickness=1, bd=0, padx=15, pady=12)
        
        # En-tête
        title = tk.Label(card_frame, text="✨ SIMULATION DE GÉNÉRATION D'IMAGE TERMINÉE ✨", bg="#1e1e1e", fg="#03dac6", font=("Arial", 10, "bold"), anchor="w")
        title.pack(fill="x", pady=(0, 8))
        
        # Canvas simulant l'affichage de l'image
        canvas_width = 300
        canvas_height = 180
        canvas = tk.Canvas(card_frame, width=canvas_width, height=canvas_height, bg="#2d2d2d", highlightthickness=1, highlightbackground="#333333")
        canvas.pack(pady=10)
        
        # On dessine un motif stylisé sur le canvas pour simuler le rendu d'une image
        canvas.create_rectangle(10, 10, canvas_width-10, canvas_height-10, outline="#bb86fc", width=1, dash=(5, 3))
        canvas.create_text(canvas_width/2, canvas_height/2 - 15, text="[ IMAGE SIMULÉE ]", fill="#03dac6", font=("Arial", 10, "bold"))
        prompt_preview = result_content["params"].get("prompt", "")
        if len(prompt_preview) > 35:
            prompt_preview = prompt_preview[:35] + "..."
        canvas.create_text(canvas_width/2, canvas_height/2 + 15, text=prompt_preview, fill="#888888", font=("Arial", 8, "italic"), width=250)

        # Récapitulatif
        details_frame = tk.Frame(card_frame, bg="#1e1e1e")
        details_frame.pack(fill="x", pady=(5, 0))
        
        details = [
            ("Prompt Final :", result_content["params"].get("prompt", "")),
            ("Checkpoint :", result_content["params"].get("checkpoint", "")),
            ("Seed finale :", str(result_content["params"].get("seed", ""))),
            ("Steps :", str(result_content["params"].get("steps", ""))),
            ("Statut :", "SIMULATION UNIQUEMENT (V0 - Prête pour la V1 API WebUI)")
        ]
        
        for label, val in details:
            row = tk.Frame(details_frame, bg="#1e1e1e")
            row.pack(fill="x", pady=2)
            lbl = tk.Label(row, text=f"• {label} ", bg="#1e1e1e", fg="#bb86fc", font=("Arial", 9, "bold"), anchor="w", width=15)
            lbl.pack(side="left")
            val_lbl = tk.Label(row, text=val, bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 9), anchor="w", justify="left", wraplength=450)
            val_lbl.pack(side="left", fill="x", expand=True)
            
        # Insertion dans le chat
        self.chat_area.insert(tk.END, "\n")
        self.chat_area.window_create(tk.END, window=card_frame)
        self.chat_area.insert(tk.END, "\n")
        
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)

    def copy_logs_to_clipboard(self):
        """Récupère et formate les logs & traces, puis les copie dans le presse-papiers."""
        try:
            # 1. Récupération des contenus textuels
            chat_text = self.chat_area.get("1.0", tk.END)
            trace_text = self.trace_text_area.get("1.0", tk.END)
            
            # 2. Récupération des informations de diagnostic
            active_model = getattr(self.engine, "model", None)
            working_dir = getattr(self.files, "working_dir", None)
            current_file = getattr(self.files, "current_file_path", None)
            
            # 3. Formatage de l'export via le service
            export_content = debug_export_service.generate_export_content(
                chat_text=chat_text,
                trace_text=trace_text,
                active_model=active_model,
                working_dir=working_dir,
                current_file=current_file
            )
            
            # 4. Copie dans le presse-papiers Tkinter
            self.root.clipboard_clear()
            self.root.clipboard_append(export_content)
            
            # 5. Indication visuelle temporaire dans la barre de statut
            self.update_status("Logs & traces copiés dans le presse-papiers !", active=True)
            self.root.after(3000, lambda: self.update_status("Prêt", active=False))
        except Exception as e:
            print(f"[ERREUR] Échec de la copie des logs : {e}")
            self.update_status("Erreur lors de la copie des logs !", active=True)
            self.root.after(3000, lambda: self.update_status("Prêt", active=False))

    def on_close(self):
        """Restaure proprement les flux d'origine à la fermeture de la fenêtre."""
        try:
            debug_export_service.restore_terminal_capture()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()
