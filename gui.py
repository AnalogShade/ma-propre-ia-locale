import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import os
from PIL import Image, ImageTk
from file_manager import FileManager
from intent_router import IntentRouter
import emotion_manager

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

        # Zone Gauche : Avatar Placeholder
        self.left_frame = tk.Frame(self.main_container, bg="#1e1e1e", width=256, height=256, highlightbackground="#333333", highlightthickness=1)
        self.left_frame.pack(side="left", padx=10, pady=10, anchor="n")
        self.left_frame.pack_propagate(False) 
        
        self.avatar_label = tk.Label(self.left_frame, text="Avatar Anna\n(256x256)", bg="#1e1e1e", fg="#e0e0e0", font=("Arial", 12))
        self.avatar_label.place(relx=0.5, rely=0.5, anchor="center")

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

        # On place d'abord les boutons à droite pour qu'ils soient prioritaires
        self.help_button = tk.Button(self.input_frame, text=" ? ", command=self.show_help, bg="#444444", fg="white", activebackground="#666666", activeforeground="white", relief="flat", padx=10)
        self.help_button.pack(side="right", fill="y", padx=(5, 0))

        self.send_button = tk.Button(self.input_frame, text="Envoyer", command=self.send_message, bg="#333333", fg="white", activebackground="#444444", activeforeground="white", relief="flat", padx=15)
        self.send_button.pack(side="right", fill="y", padx=(5, 0))

        # Puis la zone de texte qui prend tout le reste de la place
        self.user_input = tk.Text(self.input_frame, font=("Arial", 11), bg="#333333", fg="white", 
                                  insertbackground="white", relief="flat", bd=5, height=3)
        self.user_input.pack(side="left", expand=True, fill="x")
        
        # Bindings
        self.user_input.bind("<Return>", self.handle_return)
        self.user_input.bind("<Shift-Return>", self.handle_shift_return)

        # Message de bienvenue
        self.append_chat("Système", "Bienvenue ! Anna est prête. Clique sur le bouton '?' ou tape /help pour l'aide.")

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
        self.chat_area.insert(tk.END, f"\n{sender} : ", "bold")
        self.chat_area.insert(tk.END, f"{message}\n")
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)
        # Couleurs des tags pour le mode sombre
        self.chat_area.tag_config("bold", font=("Arial", 11, "bold"), foreground="#bb86fc") # Une touche de violet pour les noms

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
        # 1. Récupération du contexte
        user_summary = self.memory.get_user_info_summary()
        files_context = self.files.get_context_for_ai()
        assistant_name = self.memory.assistant_profile.get("nom", "Anna")
        
        # 2. Mise à jour mémoire (Message utilisateur)
        self.memory.add_message("user", user_input)
        context = self.memory.get_context()

        # 3. Appel IA
        response = self.engine.get_response(context, user_summary=user_summary, assistant_name=assistant_name, files_context=files_context)
        
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

        # 7. Extraction (Optionnel dans la GUI pour l'instant)
        info = self.engine.extract_fact(user_input)
        if info and "categorie" in info:
            cat, cle, val = info["categorie"].lower(), info["cle"], info["valeur"]
            if cat == "user_profile": self.memory.update_user_profile(cle, val)
            elif cat == "assistant_profile": self.memory.update_assistant_profile(cle, val)
            else: self.memory.add_fact(cle, val)

    def run(self):
        self.root.mainloop()
