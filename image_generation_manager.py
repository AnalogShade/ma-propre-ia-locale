from image_settings_manager import ImageSettingsManager
from stable_diffusion_service import StableDiffusionService
from image_prompt_builder import ImagePromptBuilder
from image_param_update_interpreter import ImageParamUpdateInterpreter

class ImageGenerationManager:
    def __init__(self, ai_engine):
        """
        Initialise l'orchestrateur central de la génération d'images.
        """
        self.settings = ImageSettingsManager()
        self.service = StableDiffusionService(self.settings.api_url)
        self.prompt_builder = ImagePromptBuilder(ai_engine)
        self.interpreter = ImageParamUpdateInterpreter(ai_engine)
        
        # État de la session courante
        self.state = {
            "active": False,
            "step": "idle",             # "idle" | "waiting_for_prompt" | "waiting_for_confirmation"
            "current_params": None
        }

    def is_active(self):
        """
        Indique si le mode image est actif pour intercepter les saisies utilisateur.
        """
        return self.state["active"]

    def start_session(self):
        """
        Démarre une nouvelle session interactive de génération d'images.
        """
        self.state["active"] = True
        self.state["step"] = "waiting_for_prompt"
        self.state["current_params"] = None
        # On synchronise l'URL de l'API avec les derniers réglages sauvegardés
        self.service.update_api_url(self.settings.api_url)

    def cancel_session(self):
        """
        Annule la session active et réinitialise complètement l'état.
        """
        self.state["active"] = False
        self.state["step"] = "idle"
        self.state["current_params"] = None

    def process_user_message(self, user_input, engine):
        """
        Traite le message utilisateur selon l'étape de la session courante.
        Redirige les appels vers le PromptBuilder ou l'UpdateInterpreter.
        """
        # Synchronisation à chaud de l'AIEngine actif
        self.prompt_builder.engine = engine
        self.interpreter.engine = engine
        
        step = self.state["step"]
        
        if step == "waiting_for_prompt":
            # --- ÉTAPE 1 : L'utilisateur décrit son idée -> Proposition de prompt initiale ---
            proposal = self.prompt_builder.build_initial_proposal(user_input)
            
            # Injection automatique du checkpoint choisi de manière persistante par défaut si le LLM n'en a pas suggéré
            selected_cp = self.settings.selected_checkpoint
            if selected_cp and not proposal.get("checkpoint"):
                proposal["checkpoint"] = selected_cp
                
            self.state["current_params"] = proposal
            self.state["step"] = "waiting_for_confirmation"
            
            return {
                "type": "image_parameters_proposal",
                "content": proposal,
                "message": "Voici ma proposition de configuration pour votre image. Vous pouvez l'ajuster simplement par la discussion (ex: 'mets le CFG à 6', 'format paysage') ou écrire 'ok' pour lancer la génération simulée."
            }
            
        elif step == "waiting_for_confirmation":
            # --- ÉTAPE 2 : L'utilisateur peaufine les paramètres ou valide ---
            interpretation = self.interpreter.interpret_correction(self.state["current_params"], user_input)
            action = interpretation.get("action", "normal_message")
            
            if action == "update_image_params":
                # On applique de façon sélective les modifications décodées par le LLM
                updates = interpretation.get("updates", {})
                current = self.state["current_params"]
                
                for k, v in updates.items():
                    if k in current:
                        # Conversion de type robuste selon le paramètre
                        if k in ["width", "height", "steps", "seed"]:
                            try:
                                current[k] = int(v)
                            except ValueError:
                                pass
                        elif k == "cfg_scale":
                            try:
                                current[k] = float(v)
                            except ValueError:
                                pass
                        else:
                            current[k] = str(v)
                
                return {
                    "type": "image_parameters_proposal",
                    "content": current,
                    "message": interpretation.get("user_message", "J'ai bien pris en compte vos modifications.")
                }
                
            elif action == "confirm_generation":
                # Validation finale -> Lancement de la génération (Simulation V0)
                final_params = self.state["current_params"]
                
                # Fin de la session active
                self.state["active"] = False
                self.state["step"] = "idle"
                self.state["current_params"] = None
                
                return self.execute_generation(final_params)
                
            elif action == "cancel_generation":
                # Annulation demandée
                self.cancel_session()
                return {
                    "type": "image_cancelled",
                    "message": "Session de génération d'image annulée. Retour au mode chat normal."
                }
                
            elif action == "normal_message":
                # Saisie hors-sujet pendant le mode image
                return {
                    "type": "image_normal_chat",
                    "message": "Nous sommes en mode de génération d'image. Vous pouvez modifier les paramètres proposés (ex: 'CFG à 6', 'aquarelle'), annuler en disant 'annule', ou confirmer la génération en disant 'ok'."
                }

        # Cas d'erreur de repli
        return {
            "type": "error",
            "message": "Étape de génération d'image non valide."
        }

    def execute_generation(self, params):
        """
        Déclenche la génération simulée en V0 via le StableDiffusionService.
        """
        try:
            result = self.service.generate_image(params)
            return {
                "type": "image_simulation_result",
                "content": result,
                "message": "La simulation de génération d'image est terminée avec succès !"
            }
        except Exception as e:
            return {
                "type": "error",
                "message": f"Une erreur s'est produite lors de la génération simulée : {e}"
            }
