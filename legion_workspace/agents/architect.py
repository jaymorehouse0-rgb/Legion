# legion_workspace/agents/architect.py
import re
from concurrent.futures import ThreadPoolExecutor

from config import NUM_PREDICT


class ArchitectAgent:
    def __init__(self, api_core, planner_model, reviewer_model):
        self.api = api_core
        self.planner_model = planner_model
        self.reviewer_model = reviewer_model

    def deterministic_lint(self, code):
        """Returns a list of deterministic quality issues found in code."""
        issues = []
        patterns = [
            (r"#\s*implement\b", "placeholder comment '# implement'"),
            (r"#\s*todo\b", "TODO comment"),
            (r"\bNotImplementedError\b", "NotImplementedError stub"),
        ]
        for pattern, label in patterns:
            if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                issues.append(label)
        if re.search(r"^\s*pass\s*$", code, re.MULTILINE):
            issues.append("bare pass statement")
        if re.search(
            r"def\s+\w+\s*\([^)]*\)\s*:\s*\n(?:\s*(?:#.*\n))*\s*pass\s*(?:\n|$)",
            code,
        ):
            issues.append("empty pass-only function")
        return issues

    def generate_test_inputs(self, spec_sheet):
        sys_prompt = (
            "You are a QA Automation Test Case Generator. Output realistic sample execution input stream text "
            "separated by commas to simulate runtime code coverage testing. If no interactive inputs are needed, output: 'NONE'."
        )
        return self.api.invoke_generation(
            "Tester", self.reviewer_model, sys_prompt, spec_sheet,
            quiet=True, num_predict=NUM_PREDICT["review"]
        )

    def _spawn_auditor(self, review_type, code, logs, model):
        sys_prompt = (
            f"You are an elite QA Code Auditor specializing in '{review_type}'.\n"
            "Inspect the code and runtime logs carefully. Identify shortcuts, missing features, lazy placeholders, or logic errors. "
            "Provide highly specific, technical engineering feedback on what needs to be fixed. If perfect, reply 'VERIFIED'."
        )
        context = f"--- CODE ---\n{code}\n\n--- RUNTIME LOGS ---\n{logs}"
        return self.api.invoke_generation(
            f"Architect->{review_type}", model, sys_prompt, context,
            quiet=True, num_predict=NUM_PREDICT["review"]
        )

    def evaluate_logic(self, intent, code, logs, blueprint, mode="full"):
        """
        mode: 'none' = deterministic only, 'light' = single 1.5B review, 'full' = parallel 1.5B audits
        """
        lint_issues = self.deterministic_lint(code)
        if lint_issues:
            return "Deterministic lint failures: " + ", ".join(lint_issues)

        if mode == "none":
            return "VERIFIED"

        if mode == "light":
            combined_logs = f"Goal: {intent}\nLogs: {logs}\nEnsure no lazy placeholders exist."
            verdict = self._spawn_auditor(
                "Combined_Review", code, combined_logs, self.reviewer_model
            )
            return verdict

        with ThreadPoolExecutor(max_workers=2) as executor:
            logic_future = executor.submit(
                self._spawn_auditor,
                "Logic_And_Features", code, f"Goal: {intent}\nLogs: {logs}", self.reviewer_model
            )
            quality_future = executor.submit(
                self._spawn_auditor,
                "Completeness_Check", code,
                "Ensure no lazy comments like '# implement here' exist.", self.reviewer_model
            )
            logic_verdict = logic_future.result()
            quality_verdict = quality_future.result()

        if "VERIFIED" in logic_verdict.upper() and "VERIFIED" in quality_verdict.upper():
            return "VERIFIED"

        return (
            f"--- LOGIC AUDIT FINDINGS ---\n{logic_verdict}\n\n"
            f"--- QUALITY AUDIT FINDINGS ---\n{quality_verdict}"
        )
