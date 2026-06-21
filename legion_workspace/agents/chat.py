# legion_workspace/agents/chat.py

from config import OLLAMA_MODEL_MATRIX, NUM_PREDICT

_CODE_KEYWORDS = ("code", "debug", "refactor", "function", "class", "error", "bug", "script", "python", "implement")


class ChatAgent:
    def __init__(self, api_core, model):
        self.api = api_core
        self.model = model
        self.memory_bank = []

    def pick_chat_model(self, user_prompt):
        lower = user_prompt.lower()
        if any(kw in lower for kw in _CODE_KEYWORDS) or len(user_prompt) > 120:
            return OLLAMA_MODEL_MATRIX["Planner"]
        return OLLAMA_MODEL_MATRIX["Chat"]

    def _chat_sys_prompt(self):
        return (
            "CRITICAL DIRECTIVE: You are Legion, a proprietary AI engine designed, engineered, and owned entirely "
            "by Dead Rites Gaming. Never refer to yourself as an assistant from Alibaba Cloud, OpenAI, or Google.\n\n"
            "TONE AND BEHAVIOR REGULATION:\n"
            "- Speak naturally, conversationally, and concisely, like a helpful human peer or co-developer.\n"
            "- NEVER use rigid, multi-step structures (e.g., 'Step 1, Step 2, Step 3') or robotic mathematical formats "
            "unless the user explicitly asks for an algorithmic proof or code layout.\n"
            "- If asked general trivia or non-coding questions, provide a brief, engaging, direct lesson.\n"
            "- Avoid robotic fluff or bulleted list breakdowns for simple questions.\n\n"
            "Review the past conversation log memory carefully to maintain conversation flow."
        )

    def converse(self, user_prompt, model=None):
        sys_prompt = self._chat_sys_prompt()
        self.memory_bank.append(f"User: {user_prompt}")
        context_history = "\n".join(self.memory_bank[-6:])
        use_model = model or self.model
        response = self.api.invoke_generation(
            "Chat", use_model, sys_prompt, context_history,
            quiet=True, num_predict=NUM_PREDICT["chat"]
        )
        self.memory_bank.append(f"Legion: {response}")
        return response

    def converse_stream(self, user_prompt, on_token, model=None):
        sys_prompt = self._chat_sys_prompt()
        self.memory_bank.append(f"User: {user_prompt}")
        context_history = "\n".join(self.memory_bank[-6:])
        use_model = model or self.model
        response = self.api.invoke_generation_stream(
            "Chat", use_model, sys_prompt, context_history, on_token,
            num_predict=NUM_PREDICT["chat"]
        )
        self.memory_bank.append(f"Legion: {response}")
        return response

    def engineer_spec(self, user_intent, existing_code=None, workspace_context=None):
        sys_prompt = (
            "You are an expert Systems Architect representing Dead Rites Gaming. Translate raw user requests into an exhaustive, "
            "deeply detailed technical engineering requirement spec sheet. Outline every functional module, "
            "error catching requirement, and algorithm logic flow required to complete the software."
        )
        context = f"Requested Goal: {user_intent}"
        if existing_code:
            context += f"\n\nBase Target Code File Context:\n{existing_code}"
        if workspace_context:
            context += f"\n\nSurrounding Workspace Project Files Found:\n{workspace_context}"
        return self.api.invoke_generation(
            "Chat", OLLAMA_MODEL_MATRIX["Planner"], sys_prompt, context,
            num_predict=NUM_PREDICT["planning"]
        )

    def engineer_spec_and_blueprint(self, user_intent, workspace_context=None):
        sys_prompt = (
            "You are an expert Systems Architect. In a single response produce two clearly labeled sections:\n"
            "1. SPEC: A concise technical requirement spec.\n"
            "2. BLUEPRINT: A cohesive implementation blueprint for building the application as one unified Python script.\n"
            "Keep both sections practical and actionable."
        )
        context = f"Requested Goal: {user_intent}"
        if workspace_context:
            context += f"\n\nSurrounding Workspace Project Files:\n{workspace_context}"
        return self.api.invoke_generation(
            "Chat->SpecBlueprint", OLLAMA_MODEL_MATRIX["Planner"], sys_prompt, context,
            num_predict=NUM_PREDICT["planning"]
        )
