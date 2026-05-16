import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import os
from PIL import Image, ImageTk
from file_manager import FileManager
from intent_router import IntentRouter
import emotion_manager
from stt_manager import STTManager
from tts_manager import TTSManager

class AnnaGUI:
    def __init__(self, engine, memory):
        self.engine = engine
        self.memory = memory
        self.files = FileManager()
        self.router = IntentRouter()
        
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

        # Zone Gauche : Avatar Placeholder
        self.left_frame = tk.Frame(self.main_container, bg="#1e1e1e", width=256, height=256, highlightbackground="#333333", highlightthickness=1)
        self.left_frame.pack(side="left", padx=10, pady=10, anchor="n")
        self.left_frame.pack_propagate(False) 
        
        self.avatar_label = tk.Label(self.left_frame, text="Avatar Anna\n(256x256)", bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 12))
        self.avatar_label.place(relx=0.5, rely=0.5, anchor="center")

        # Bouton TTS (Speaker)
        self.tts_button = tk.Button(self.left_frame, text="\ud83d\udd0a Voix", command=self.show_voice_menu, bg="#333333", fg="white", activebackground="#444444", activeforeground="white", relief="flat")
        self.tts_button.pack(side="bottom", pady=(0, 5), fill="x", padx=10)

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

    def _on_stt_ready(self):
        self.root.after(0, lambda: self.mic_button.config(text="\ud83c\udf99\ufe0f", state="normal", fg="white"))

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
            self.mic_button.config(text="\ud83c\udf99\ufe0f", fg="white", state="normal")
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
            self.root.after(2000, lambda: self.tts_button.config(text="\ud83d\udd0a Voix"))

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
            parts = msg.split(' ')
            cmd = parts[0].lower()
            
            if cmd == '/openfile' and len(parts) > 1:
                success, response = self.files.load_file(parts[1])
                self.append_chat("Système", response)
                return
            elif cmd == '/listfiles':
                self.append_chat("Système", self.files.list_files())
                return
            elif cmd == '/closefile' and len(parts) > 1:
                success, response = self.files.close_file(parts[1])
                self.append_chat("Système", response)
                return
            elif cmd == '/reloadfile' and len(parts) > 1:
                success, response = self.files.load_file(parts[1])
                self.append_chat("Système", f"{response} (Rechargé)")
                return
            elif cmd == '/clear':
                self.memory.clear()
                self.append_chat("Système", "Historique effacé.")
                return
            elif cmd == '/help':
                self.show_help()
                return

        # Détection langage naturel pour les fichiers
        if self.handle_file_intent(msg):
            # Si une action système est détectée et exécutée, on arrête le flux ici.
            # L'IA ne répondra pas conversationnellement pour éviter les doublons.
            return

        # Lancer le traitement dans un thread pour ne pas geler l'interface
        threading.Thread(target=self.process_ai_response, args=(msg,), daemon=True).start()

    def process_ai_response(self, user_input):
        # 1. R\u00e9cup\u00e9ration du contexte
        user_summary = self.memory.get_user_info_summary()
        assistant_summary = self.memory.get_assistant_info_summary()
        files_context = self.files.get_context_for_ai()
        assistant_name = self.memory.assistant_profile.get("nom", "Anna")
        
        # 2. Mise \u00e0 jour m\u00e9moire (Message utilisateur)
        self.memory.add_message("user", user_input)
        context = self.memory.get_context()
 
        # 3. Appel IA
        response = self.engine.get_response(
            context, 
            user_summary=user_summary, 
            assistant_summary=assistant_summary,
            assistant_name=assistant_name, 
            files_context=files_context
        )
        
        if not response:
            user_name = self.memory.user_profile.get("prénom", "Louis")
            response = f"Salut {user_name}, je suis là. (Ollama n'a pas renvoyé de texte)"

        # 4. Affichage
        self.root.after(0, lambda: self.append_chat(assistant_name, response))

        # 5. Mise à jour mémoire (Assistant)
        if "Ollama n'a pas renvoyé de texte" not in response:
            self.memory.add_message("assistant", response)

        # 6. Émotions (Nouveau)
        try:
            emotion = emotion_manager.detect_emotion(response)
            self.root.after(0, lambda: self.update_avatar(emotion))
        except Exception as e:
            print(f"Erreur détection émotion: {e}")

        # 7. Extraction en arri\u00e8re-plan (Parall\u00e8le \u00e0 la r\u00e9ponse)
        def background_extraction():
            info = self.engine.extract_fact(user_input)
            if info:
                self.memory.process_extracted_fact(info)
        
        threading.Thread(target=background_extraction, daemon=True).start()

    def run(self):
        self.root.mainloop()
