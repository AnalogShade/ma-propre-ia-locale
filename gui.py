import tkinter as tk
from tkinter import scrolledtext
import threading

class AnnaGUI:
    def __init__(self, engine, memory):
        self.engine = engine
        self.memory = memory
        
        # Fenêtre principale
        self.root = tk.Tk()
        self.root.title("ANNA - IA Locale")
        self.root.geometry("800x600")
        self.root.configure(bg="#2c3e50")

        # Layout principal (Gauche: Avatar | Droite: Chat)
        self.main_container = tk.Frame(self.root, bg="#2c3e50")
        self.main_container.pack(expand=True, fill="both", padx=10, pady=10)

        # Zone Gauche : Avatar Placeholder
        self.left_frame = tk.Frame(self.main_container, bg="#34495e", width=256, height=256)
        self.left_frame.pack(side="left", padx=10, pady=10, anchor="n")
        self.left_frame.pack_propagate(False) # Garde la taille fixe
        
        self.avatar_label = tk.Label(self.left_frame, text="Avatar Anna\n(256x256)", bg="#34495e", fg="white", font=("Arial", 12))
        self.avatar_label.place(relx=0.5, rely=0.5, anchor="center")

        # Zone Droite : Conversation
        self.right_frame = tk.Frame(self.main_container, bg="#2c3e50")
        self.right_frame.pack(side="right", expand=True, fill="both")

        self.chat_area = scrolledtext.ScrolledText(self.right_frame, wrap=tk.WORD, state='disabled', font=("Arial", 11), bg="#ecf0f1", fg="#2c3e50")
        self.chat_area.pack(expand=True, fill="both", padx=5, pady=5)

        # Zone de saisie
        self.input_frame = tk.Frame(self.right_frame, bg="#2c3e50")
        self.input_frame.pack(fill="x", padx=5, pady=5)

        self.user_input = tk.Entry(self.input_frame, font=("Arial", 12))
        self.user_input.pack(side="left", expand=True, fill="x", padx=(0, 10))
        self.user_input.bind("<Return>", lambda e: self.send_message())

        self.send_button = tk.Button(self.input_frame, text="Envoyer", command=self.send_message, bg="#3498db", fg="white", font=("Arial", 10, "bold"))
        self.send_button.pack(side="right")

        # Message de bienvenue
        self.append_chat("Système", "Bienvenue ! Anna est prête.")

    def append_chat(self, sender, message):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, f"\n{sender} : ", "bold")
        self.chat_area.insert(tk.END, f"{message}\n")
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)
        # Ajout d'un tag pour le gras
        self.chat_area.tag_config("bold", font=("Arial", 11, "bold"))

    def send_message(self):
        msg = self.user_input.get().strip()
        if not msg:
            return

        self.append_chat("Vous", msg)
        self.user_input.delete(0, tk.END)

        # Lancer le traitement dans un thread pour ne pas geler l'interface
        threading.Thread(target=self.process_ai_response, args=(msg,), daemon=True).start()

    def process_ai_response(self, user_input):
        # 1. Récupération du contexte
        user_summary = self.memory.get_user_info_summary()
        assistant_name = self.memory.assistant_profile.get("nom", "Anna")
        
        # 2. Mise à jour mémoire (Message utilisateur)
        self.memory.add_message("user", user_input)
        context = self.memory.get_context()

        # 3. Appel IA
        response = self.engine.get_response(context, user_summary=user_summary, assistant_name=assistant_name)
        
        if not response:
            user_name = self.memory.user_profile.get("prénom", "Louis")
            response = f"Salut {user_name}, je suis là. (Ollama n'a pas renvoyé de texte)"

        # 4. Affichage
        self.root.after(0, lambda: self.append_chat(assistant_name, response))

        # 5. Mise à jour mémoire (Assistant)
        if "Ollama n'a pas renvoyé de texte" not in response:
            self.memory.add_message("assistant", response)

        # 6. Extraction (Optionnel dans la GUI pour l'instant)
        info = self.engine.extract_fact(user_input)
        if info and "categorie" in info:
            cat, cle, val = info["categorie"].lower(), info["cle"], info["valeur"]
            if cat == "user_profile": self.memory.update_user_profile(cle, val)
            elif cat == "assistant_profile": self.memory.update_assistant_profile(cle, val)
            else: self.memory.add_fact(cle, val)

    def run(self):
        self.root.mainloop()
