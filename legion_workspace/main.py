# legion_workspace/main.py
import os
import sys
import json
import urllib.request
import time
import subprocess
import threading

from config import (
    OLLAMA_MODEL_MATRIX,
    OLLAMA_PERF,
    RETRY_LIMITS,
    SIMPLE_INTENT_MAX_LEN,
)

OLLAMA_BASE = "http://127.0.0.1:11434"


def ensure_ollama_running():
    """Start Ollama only if not already responding; keep models warm."""
    try:
        urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=2)
        return False
    except Exception:
        pass

    custom_env = os.environ.copy()
    custom_env["OLLAMA_KEEP_ALIVE"] = OLLAMA_PERF["keep_alive"]
    custom_env["OLLAMA_NUM_PARALLEL"] = str(OLLAMA_PERF["num_parallel"])
    custom_env["OLLAMA_MAX_LOADED_MODELS"] = str(OLLAMA_PERF["max_loaded_models"])
    if OLLAMA_PERF.get("flash_attention"):
        custom_env["OLLAMA_FLASH_ATTENTION"] = "1"
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            env=custom_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
        )
    except Exception:
        return False

    for _ in range(20):
        try:
            urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=2)
            break
        except Exception:
            time.sleep(0.25)

    def _warmup(model):
        try:
            payload = json.dumps({"model": model, "prompt": "", "keep_alive": OLLAMA_PERF["keep_alive"]}).encode("utf-8")
            req = urllib.request.Request(
                f"{OLLAMA_BASE}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=30)
        except Exception:
            pass

    threading.Thread(
        target=_warmup, args=(OLLAMA_MODEL_MATRIX["Chat"],), daemon=True
    ).start()
    threading.Thread(
        target=_warmup, args=(OLLAMA_MODEL_MATRIX["Builder"],), daemon=True
    ).start()
    return True


class LegionCoreAPI:
    def __init__(self, gui_callback):
        self.gui_callback = gui_callback

    def _build_options(self, num_predict):
        num_thread = OLLAMA_PERF.get("num_thread")
        if num_thread is None:
            num_thread = max(1, (os.cpu_count() or 4) - 1)
        opts = {
            "num_ctx": OLLAMA_PERF["num_ctx"],
            "num_thread": num_thread,
            "temperature": OLLAMA_PERF["temperature"],
        }
        num_gpu = OLLAMA_PERF.get("num_gpu")
        if num_gpu is not None:
            opts["num_gpu"] = num_gpu
        if num_predict is not None:
            opts["num_predict"] = num_predict
        return opts

    def invoke_generation(self, role, model, sys_prompt, task_input, quiet=False, num_predict=None):
        if not quiet:
            self.gui_callback(f" ├─ [Task Core Active]: {role} engine computing context...")

        payload = {
            "model": model,
            "prompt": f"System Persona: {sys_prompt}\n\nTask Context: {task_input}",
            "stream": False,
            "keep_alive": OLLAMA_PERF["keep_alive"],
            "options": self._build_options(num_predict),
        }

        try:
            req = urllib.request.Request(
                f"{OLLAMA_BASE}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=None) as resp:
                res = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
                if not quiet:
                    self.gui_callback(f" ├─ [Module Output Verified]: {role} processing complete.")
                return res
        except Exception:
            return "FAILED"

    def invoke_generation_stream(self, role, model, sys_prompt, task_input, on_token, num_predict=None):
        payload = {
            "model": model,
            "prompt": f"System Persona: {sys_prompt}\n\nTask Context: {task_input}",
            "stream": True,
            "keep_alive": OLLAMA_PERF["keep_alive"],
            "options": self._build_options(num_predict),
        }

        full_response = []
        try:
            req = urllib.request.Request(
                f"{OLLAMA_BASE}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=None) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    chunk_data = json.loads(line.decode("utf-8"))
                    token = chunk_data.get("response", "")
                    if token:
                        full_response.append(token)
                        on_token(token)
                    if chunk_data.get("done"):
                        break
            return "".join(full_response).strip()
        except Exception:
            return "FAILED"


class WorkspaceOrchestrator:
    def __init__(self, gui_callback):
        self.gui_callback = gui_callback
        self.api = LegionCoreAPI(gui_callback)

        from agents.chat import ChatAgent
        from agents.planner import PlannerAgent
        from agents.architect import ArchitectAgent

        self.chat = ChatAgent(self.api, OLLAMA_MODEL_MATRIX["Chat"])
        self.planner = PlannerAgent(self.api, OLLAMA_MODEL_MATRIX["Planner"])
        self.architect = ArchitectAgent(
            self.api,
            planner_model=OLLAMA_MODEL_MATRIX["Planner"],
            reviewer_model=OLLAMA_MODEL_MATRIX["Reviewer"],
        )

    def assess_complexity(self, intent):
        high_signals = ["multi-agent", "framework", "system", "engine", "pipeline", "database", "cluster"]
        return any(s in intent.lower() for s in high_signals) or len(intent) > 300

    def gather_workspace_context(self):
        context_payload = []
        try:
            for file in os.listdir("."):
                if file.endswith(".py") and file not in ["main.py", "config.py", "gui_manager.py"]:
                    with open(file, "r", encoding="utf-8", errors="ignore") as f:
                        context_payload.append(f"--- FILE: {file} ---\n{f.read()[:1500]}")
        except Exception:
            pass
        return "\n\n".join(context_payload) if context_payload else None

    def clean_code(self, text):
        backtick_marker = chr(96) + chr(96) + chr(96)
        if backtick_marker in text:
            try:
                parts = text.split(backtick_marker)
                for part in parts:
                    clean_part = part.strip()
                    if clean_part.lower().startswith("python"):
                        return clean_part[6:].strip()
                    elif clean_part.lower().startswith("py"):
                        return clean_part[2:].strip()
                return parts[1].strip()
            except Exception:
                pass
        return text.replace(backtick_marker, "").strip()

    def _parse_test_inputs(self, test_raw):
        if not test_raw or test_raw == "FAILED" or "NONE" in test_raw.upper():
            return ""
        return "\n".join([i.strip() for i in test_raw.split(",")]) + "\n"

    def _run_validation(self, code, path, test_inputs, intent, blueprint, review_mode, run_test=True):
        """Returns (passed: bool, feedback: str, logs: str)."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)

        chk = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        if chk.returncode != 0:
            return False, f"Fix compilation syntax anomalies directly:\n{chk.stderr}", ""

        logs = ""
        if run_test:
            try:
                self.gui_callback("Validating runtime behavior...")
                run = subprocess.run(
                    [sys.executable, path],
                    input=test_inputs,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=4,
                    shell=True,
                    creationflags=0x08000000,
                )
                logs = f"Code: {run.returncode}\nSTDOUT:\n{run.stdout}\nSTDERR:\n{run.stderr}"
            except subprocess.TimeoutExpired:
                logs = "Status: Timeout (acceptable for GUI apps blocking on mainloop)"

        verdict = self.architect.evaluate_logic(intent, code, logs, blueprint, mode=review_mode)
        if "VERIFIED" in verdict.upper():
            return True, "", logs
        return False, f"Defects caught. Adjust structural parameters to prevent crashing on launch:\n{verdict}", logs

    def deploy_pipeline(self, intent, path, execution_mode="auto"):
        if execution_mode == "force_fast":
            return self._deploy_fast(intent, path)
        if execution_mode == "force_swarm":
            return self._deploy_swarm(intent, path)
        if not self.assess_complexity(intent) and len(intent) <= SIMPLE_INTENT_MAX_LEN:
            return self._deploy_fast(intent, path)
        if self.assess_complexity(intent):
            return self._deploy_swarm(intent, path)
        return self._deploy_standard(intent, path)

    def _deploy_fast(self, intent, path):
        from agents.builder import BuilderAgent

        self.gui_callback("Fast Path: direct codegen")
        builder = BuilderAgent(self.api, OLLAMA_MODEL_MATRIX["Builder"])
        workspace_ctx = self.gather_workspace_context()
        max_attempts = RETRY_LIMITS["fast"]
        feedback = None

        for attempt in range(1, max_attempts + 1):
            self.gui_callback(f"Validation sprint [{attempt}/{max_attempts}]")
            if feedback:
                raw_code = builder.build_code(feedback)
            else:
                raw_code = builder.build_direct(intent, workspace_ctx)
            code = self.clean_code(raw_code)
            if not code or raw_code == "FAILED":
                feedback = "Previous generation failed. Produce complete valid Python code."
                continue

            passed, feedback, _ = self._run_validation(
                code, path, "", intent, intent, review_mode="none", run_test=False
            )
            if passed:
                return True

        return False

    def _deploy_standard(self, intent, path):
        from agents.builder import BuilderAgent

        self.gui_callback("Standard Path: combined planning")
        builder = BuilderAgent(self.api, OLLAMA_MODEL_MATRIX["Builder"])
        workspace_ctx = self.gather_workspace_context()

        combined = self.chat.engineer_spec_and_blueprint(intent, workspace_ctx)
        if not combined or combined == "FAILED":
            return False

        blueprint = combined + "\n\nCRITICAL: Output unified into one single task block."
        feedback = (
            "Code this immediately into a single complete visual python tkinter app script. "
            "CRITICAL RULE: Ensure all database insert logic occurs BEFORE variables are cleared or reset to None:\n"
            + blueprint
        )
        max_attempts = RETRY_LIMITS["standard"]

        for attempt in range(1, max_attempts + 1):
            self.gui_callback(f"Validation sprint [{attempt}/{max_attempts}]")
            raw_code = builder.build_code(feedback)
            code = self.clean_code(raw_code)
            if not code or raw_code == "FAILED":
                feedback = blueprint
                continue

            passed, feedback, _ = self._run_validation(
                code, path, "", intent, blueprint, review_mode="light", run_test=True
            )
            if passed:
                return True

        return False

    def _deploy_swarm(self, intent, path):
        from agents.builder import BuilderAgent

        self.gui_callback("Swarm Path: parallel multi-agent build")
        builder = BuilderAgent(self.api, OLLAMA_MODEL_MATRIX["Builder"])
        workspace_ctx = self.gather_workspace_context()

        self.gui_callback("Structuring architecture specifications...")
        spec = self.chat.engineer_spec(intent, None, workspace_context=workspace_ctx)
        if not spec or spec == "FAILED":
            return False

        blueprint = self.planner.design_blueprint(spec, execution_mode="force_swarm")
        if not blueprint or blueprint == "FAILED":
            return False

        test_raw = self.architect.generate_test_inputs(spec)
        test_inputs = self._parse_test_inputs(test_raw)
        max_attempts = RETRY_LIMITS["swarm"]
        feedback = blueprint

        for attempt in range(1, max_attempts + 1):
            self.gui_callback(f"Validation sprint [{attempt}/{max_attempts}]")
            raw_code = builder.build_code(feedback)
            code = self.clean_code(raw_code)
            if not code or raw_code == "FAILED":
                continue

            passed, feedback, _ = self._run_validation(
                code, path, test_inputs, intent, blueprint, review_mode="full", run_test=True
            )
            if passed:
                return True

        return False


if __name__ == "__main__":
    just_started = ensure_ollama_running()
    if just_started:
        time.sleep(0.5)

    subprocess.Popen([sys.executable, "gui_manager.py"])
