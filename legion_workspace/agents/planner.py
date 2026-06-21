# legion_workspace/agents/planner.py

from config import NUM_PREDICT


class PlannerAgent:
    def __init__(self, api_interface, model_name):
        self.api = api_interface
        self.model = model_name

    def design_blueprint(self, specification_text, execution_mode="auto"):
        # 1. FORCE FAST TRACK BYPASS
        if execution_mode == "force_fast":
            sys_prompt = (
                "You are a master software architect. Output a direct, single-block technical blueprint "
                "for the requested application immediately. Do not write side-commentary."
            )
            return self.api.invoke_generation(
                "Single Planner", self.model, sys_prompt, specification_text,
                num_predict=NUM_PREDICT["planning"],
            )
            
        # 2. DETERMINE IF SWARM IS NEEDED (Complexity check or Forced Swarm)
        is_complex = "multi-agent" in specification_text.lower() or len(specification_text) > 500
        use_swarm = execution_mode == "force_swarm" or (execution_mode == "auto" and is_complex)

        if use_swarm:
            print("🗂️ [Planner Manager] Complex spec sheet or Swarm override detected. Allocating sub-planners...")
            
            sys_prompt = (
                "You are the Lead Swarm Architect. Break down this technical specification sheet into exactly 3 sequential, "
                "independent technical milestones for development. Label them clearly as 'Step 1', 'Step 2', and 'Step 3'. "
                "Each step must contain detailed layout parameters so a sub-agent can code it independently without knowing about the other steps. "
                "Separate each step with two newlines (\\n\\n)."
            )
            return self.api.invoke_generation(
                "Swarm Planner", self.model, sys_prompt, specification_text,
                num_predict=NUM_PREDICT["planning"],
            )
            
        # 3. STANDARD AUTO FALLBACK (Simple task, single block)
        print("📝 [Planner Manager] Standard project scope detected. Generating unified layout mapping...")
        sys_prompt = (
            "You are a software architect. Provide a cohesive structural roadmap blueprint for building this application. "
            "Keep the design integrated as a single task flow."
        )
        return self.api.invoke_generation(
            "Standard Planner", self.model, sys_prompt, specification_text,
            num_predict=NUM_PREDICT["planning"],
        )