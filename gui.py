import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import os
from PIL import Image, ImageTk
from stt_manager import STTManager
from tts_manager import TTSManager
from agent_controller import AgentController

class AnnaGUI:
    def __init__(self, engine, memory):
        self.ctrl = AgentController()
        
        # Liaison dynamique pour conserver la compatibilité des anciens attributs graphiques
        self.engine = self.ctrl.engine
        self.memory = self.ctrl.memory
        self.files = self.ctrl.files
        self.router = self.ctrl.router
        self.editor = self.ctrl.editor
        self.settings = self.ctrl.settings
        
        # Fenêtre principale
        self.root = tk.Tk()
        self.root.title("ANNA - IA Locale")
        self.root.geometry("800x600")
        self.root.configure(bg="#121212") # Noir profond

        # Layout principal (Gauche: Avatar | Droite: Chat)
        self.main_container = tk.Frame(self.root, bg="#121212")
        self.main_container.pack(expand=True, fill="both", padx=10, pady=10)

        # Initialisation STT & TTS
        self.stt_manager = STTManager(
            on_model_ready=self._on_stt_ready,
            on_model_error=self._on_stt_error
        )
        self.tts_manager = TTSManager()
        self.msg_counter = 0
        self.current_tts_tag = None

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

        # Chargement de l'image d'avatar
        self.load_avatar()

        # Zone Droite : Conversation
        self.right_frame = tk.Frame(self.main_container, bg="#121212")
        self.right_frame.pack(side="right", expand=True, fill="both")

        self.chat_area = scrolledtext.ScrolledText(self.right_frame, wrap=tk.WORD, state='disabled', font=("Arial", 11), bg="#1e1e1e", fg="#e0e0e0", insertbackground="white", bd=0)
        self.chat_area.pack(expand=True, fill="both", padx=5, pady=5)

        # Zone de saisie (tk.Text pour permettre le multi-ligne)
        self.input_frame = tk.Frame(self.right_frame, bg="#121212")
        self.input_frame.pack(fill="x", padx=5, pady=5)

        # On place d'abord les boutons \u00e0 droite pour qu'ils soient prioritaires
        self.help_button = tk.Button(self.input_frame, text=" ? ", command=self.show_help, bg="#444444", fg="white", activebackground="#666666", activeforeground="white", relief="flat", padx=10)
        self.help_button.pack(side="right", fill="y", padx=(5, 0))

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
        self.user_input.bind("<Return>", self.handle_return)
        self.user_input.bind("<Shift-Return>", self.handle_shift_return)

        # Message de bienvenue
        self.append_chat("Système", "Bienvenue ! Anna est prête. Clique sur le bouton '?' ou tape /help pour l'aide.")

        # Lancement de la détection asynchrone des modèles installés
        threading.Thread(target=self._detect_models_thread, daemon=True).start()

    # =========================================================================
    # SECTION AUDIO : GESTION LOCALE DU MICRO (STT) ET DE LA VOIX (TTS)
    # =========================================================================

    def _on_stt_ready(self):
        self.root.after(0, lambda: self.mic_button.config(text="🎙️", state="normal", fg="white"))

    def _on_stt_error(self, err_msg):
        self.root.after(0, lambda: self.mic_button.config(text="\u274c", state="disabled"))

    def toggle_recording(self):
        if not self.stt_manager.is_recording:
            success, msg = self.stt_manager.start_recording()
            if success:
                self.mic_button.config(text="\ud83d\udd34", fg="red")
            else:
                print(f"[GUI] Erreur STT: {msg}")
        else:
            self.mic_button.config(text="\ud83d\udd04", fg="yellow", state="disabled")
            self.stt_manager.stop_recording_and_transcribe(self._on_transcription_done)

    def _on_transcription_done(self, text):
        def update_gui():
            self.mic_button.config(text="🎙️", fg="white", state="normal")
            if text:
                self.user_input.insert(tk.END, text + " ")
        self.root.after(0, update_gui)

    def show_voice_menu(self):
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

    def handle_return(self, event):
        """Envoie le message sur Entrée simple."""
        self.send_message()
        return "break" # Empêche le saut de ligne par défaut

    def handle_shift_return(self, event):
        """Laisse faire le saut de ligne sur Shift+Entrée."""
        pass

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

    def send_message(self):
        msg = self.user_input.get("1.0", tk.END).strip()
        if not msg:
            return

        self.user_input.delete("1.0", tk.END)
        
        # Affichage immédiat du message de l'utilisateur pour un ordre naturel
        self.append_chat("Vous", msg)

        # Gestion des commandes spéciales (Fichiers)
        if msg.startswith('/'):
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

        # Lancer le traitement dans un thread pour ne pas geler l'interface
        threading.Thread(target=self.process_ai_response, args=(msg,), daemon=True).start()

    def process_ai_response(self, user_input):
        print(f"\n[DIAGNOSTIC] RAW USER MESSAGE:\n{user_input}\n")
        
        # Délégation de tout le traitement métier (Intentions, IA, émotions, diffs) au contrôleur unifié
        result = self.ctrl.process_user_message_sync(user_input)
        
        def display_response_and_diffs():
            # Arrêt propre du thread de progression et retrait du bloc temporaire
            self.sd_generating = False
            self.remove_progress_block()
            
            res_type = result.get("type")
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
                # Réinitialisation sécurisée de l'interface en cas de crash durant le mode image
                if self.ctrl.image_manager.is_active() or self.sd_generate_button.cget("text") == "🎨 Mode Image Actif":
                    self.sd_generate_button.config(text="🖼️ Générer une Image", bg="#333333", fg="white")
                    self.ctrl.image_manager.cancel_session()
                
                # Rendu graphique sous forme d'un magnifique encadré rouge
                self.show_error_block("ÉCHEC DE LA GÉNÉRATION", result.get("message"))
                return
                
            elif res_type == "ai_response" or res_type == "text":
                # Affichage sémantique du chargement de fichier
                if result.get("system_notification"):
                    self.append_chat("Système", result.get("system_notification"))
                    
                response = result.get("content")
                self.append_chat(assistant_name, response)
                
                # Mise à jour émotionnelle de l'avatar
                emotion = result.get("emotion", "neutral")
                self.update_avatar(emotion)
                
                # Parsing et rendu visuel interactif des diffs
                create_blocks = result.get("create_blocks", [])
                edit_blocks = result.get("edit_blocks", [])
                
                for block in create_blocks:
                    self.show_diff_block(block['file_path'], "create", create_content=block['content'])
                for block in edit_blocks:
                    self.show_diff_block(block['file_path'], "edit", search_content=block['search_content'], replace_content=block['replace_content'])
                    
        self.root.after(0, display_response_and_diffs)

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

    def show_diff_block(self, file_path, block_type, search_content="", replace_content="", create_content=""):
        """
        Crée un cadre Tkinter contenant le diff visuel et les boutons interactifs,
        et l'insère directement dans la zone de chat.
        """
        # Activer le chat pour insertion
        self.chat_area.config(state='normal')
        
        # Création du cadre principal du Diff
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
        
        # État et actions des boutons
        def on_apply():
            btn_apply.config(state="disabled")
            btn_cancel.config(state="disabled")
            
            if block_type == "create":
                success, msg = self.editor.create_file(file_path, create_content, working_dir=self.files.working_dir)
                self.append_chat("Système", msg)
                if success:
                    self.files.load_file(file_path)
            else:
                from pathlib import Path
                if not Path(file_path).is_absolute() and self.files.working_dir:
                    abs_path = (Path(self.files.working_dir) / file_path).resolve()
                else:
                    abs_path = Path(file_path).resolve()
                    
                success, msg = self.editor.apply_edit(abs_path, search_content, replace_content)
                self.append_chat("Système", msg)
                if success:
                    self.files.load_file(file_path)
                    
        def on_cancel():
            btn_apply.config(state="disabled")
            btn_cancel.config(state="disabled")
            self.append_chat("Système", f"Modification de '{file_path}' annulée.")
            
        action_title = "Créer le fichier" if block_type == "create" else "Appliquer"
        btn_apply = tk.Button(btn_frame, text=f"✓ {action_title}", command=on_apply, bg="#03dac6", fg="black", activebackground="#018786", relief="flat", font=("Arial", 9, "bold"), padx=15, pady=5)
        btn_apply.pack(side="left", padx=(0, 10))
        
        btn_cancel = tk.Button(btn_frame, text="✗ Annuler", command=on_cancel, bg="#444444", fg="white", activebackground="#666666", relief="flat", font=("Arial", 9), padx=15, pady=5)
        btn_cancel.pack(side="left")
        
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

    def run(self):
        self.root.mainloop()
