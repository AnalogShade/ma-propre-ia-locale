import re

SYSTEM_PROMPT_PLANNING = """Tu es un planificateur technique pour l'agent de codage Anna.
Ton rôle est d'analyser la demande de l'utilisateur, d'étudier l'état actuel du workspace et de produire un plan d'action technique clair et concis.

CONSIGNES :
1. Liste les fichiers du workspace concernés par la demande.
2. Identifie les fonctions, classes ou blocs de code clés à inspecter ou modifier.
3. Décris la stratégie de modification étape par étape (ex: 'ajouter verifier_victoire', 'supprimer emojis dans jouer').
4. Sois extrêmement concis et direct. Pas de blabla, de politesses ou de salutations.

Format ton plan sous forme de bloc Markdown collapsible :
<details>
<summary>📋 Plan d'action technique proposé (Clique pour déplier)</summary>

*   **Fichiers ciblés :** [liste des fichiers]
*   **Objectif :** [bref résumé]
*   **Étapes de modification :**
    1.  [Étape 1]
    2.  [Étape 2]
</details>"""

class PlanningAgent:
    @staticmethod
    def generate_plan(engine, context_messages, files_context, user_summary="", assistant_summary="", assistant_name="Anna"):
        """
        Génère un plan technique d'action en interrogeant Ollama avec un prompt système ciblé.
        """
        original_prompt = engine.system_prompt
        engine.system_prompt = SYSTEM_PROMPT_PLANNING
        
        try:
            plan_response = engine.get_response(
                context_messages=context_messages,
                user_summary=user_summary,
                assistant_summary=assistant_summary,
                assistant_name=assistant_name,
                files_context=files_context,
                compressed_context=""
            )
            
            if plan_response and "<think>" in plan_response:
                plan_response = re.sub(r"<think>.*?</think>", "", plan_response, flags=re.DOTALL)
                if "<think>" in plan_response:
                    plan_response = plan_response.split("<think>", 1)[0]
                    
            if not plan_response or not plan_response.strip():
                plan_response = (
                    "<details>\n"
                    "<summary>📋 Plan d'action technique proposé (Clique pour déplier)</summary>\n\n"
                    "*   **Statut :** Planification générique.\n"
                    "</details>"
                )
            
            return plan_response.strip()
        except Exception as e:
            print(f"[PLANNING WARNING] Échec de la génération du plan : {e}")
            return (
                f"<details>\n"
                f"<summary>📋 Plan d'action technique proposé (Clique pour déplier)</summary>\n\n"
                f"*   **Erreur :** Impossible de générer le plan ({e}).\n"
                f"</details>"
            )
        finally:
            engine.system_prompt = original_prompt
