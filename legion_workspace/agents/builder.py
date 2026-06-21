# legion_workspace/agents/builder.py
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import NUM_PREDICT, OLLAMA_PERF


class BuilderAgent:
    def __init__(self, api_core, model):
        self.api = api_core
        self.model = model

    def build_direct(self, user_intent, workspace_context=None):
        """One-shot codegen from user intent — fast path."""
        sys_prompt = (
            "You are an Elite Software Engineer. Write the complete, production-ready Python application "
            "described by the user. Output the full executable script wrapped inside markdown triple backticks. "
            "No placeholders, no truncation."
        )
        context = f"User Request: {user_intent}"
        if workspace_context:
            context += f"\n\nSurrounding Workspace Project Files:\n{workspace_context}"
        return self.api.invoke_generation(
            "Builder->Direct", self.model, sys_prompt, context,
            quiet=True, num_predict=NUM_PREDICT["codegen"]
        )

    def _spawn_micro_worker(self, specific_component, component_blueprint):
        sys_prompt = (
            f"You are a specialized Micro-Agent tasked ONLY with building the '{specific_component}' asset module.\n"
            "Write the absolute final, fully-implemented Python code for this specific module. "
            "Do NOT write any introduction text, placeholder comments, or empty structures. No truncation allowed. "
            "Return raw Python code directly without markdown text wrapper decoration."
        )
        return self.api.invoke_generation(
            f"Builder->MicroWorker({specific_component})", self.model, sys_prompt, component_blueprint,
            quiet=True, num_predict=NUM_PREDICT["codegen"]
        )

    def build_code(self, blueprint):
        has_steps = any(marker in blueprint.lower() for marker in ["step 1", "step 2", "step 3"])

        if not has_steps or len(blueprint) < 1000:
            sys_prompt = (
                "You are an Elite Software Engineer. Code the absolute final, complete production Python application "
                "requested in the blueprint. Output the full executable script wrapped inside markdown triple backticks."
            )
            return self.api.invoke_generation(
                "Builder", self.model, sys_prompt, blueprint,
                quiet=True, num_predict=NUM_PREDICT["codegen"]
            )

        milestones = []
        for i in range(1, 4):
            pattern = rf"(?i)Step\s*{i}.*?(?=Step\s*{i+1}|$)"
            match = re.search(pattern, blueprint, re.DOTALL)
            if match:
                milestones.append(match.group(0).strip())

        if not milestones:
            milestones = [block.strip() for block in blueprint.split("\n\n") if len(block.strip()) > 50][:3]

        assembled_results = {}

        with ThreadPoolExecutor(max_workers=OLLAMA_PERF["num_parallel"]) as executor:
            future_to_module = {}
            for index, step in enumerate(milestones, start=1):
                component_name = f"Module_Part_{index}"
                future = executor.submit(self._spawn_micro_worker, component_name, step)
                future_to_module[future] = component_name

            for future in as_completed(future_to_module):
                component_name = future_to_module[future]
                try:
                    assembled_results[component_name] = future.result()
                except Exception:
                    pass

        ordered_blocks = [
            assembled_results[f"Module_Part_{i}"]
            for i in range(1, len(milestones) + 1)
            if f"Module_Part_{i}" in assembled_results
        ]

        master_compilation_prompt = (
            "You are the Lead Integration Engineer. Below are separate blocks of functional code written by your sub-teams.\n\n"
            "CRITICAL INTEGRATION LAWS:\n"
            "1. Stitch them together into a single, cohesive, working standalone Python file.\n"
            "2. Deduplicate all library imports and place them uniformly at the top of the file.\n"
            "3. Resolve scope references; ensure global variables, database logic, or structural instances interface seamlessly.\n"
            "4. Return the complete, fully realized script wrapped inside markdown triple backticks. Do not use placeholders or lazy comments.\n\n"
            f"--- CODE PARTS SUBMITTED ---\n" + "\n\n".join(ordered_blocks)
        )

        return self.api.invoke_generation(
            "Builder->Assembler", self.model, master_compilation_prompt, "Unify files cleanly.",
            quiet=True, num_predict=NUM_PREDICT["codegen"]
        )
