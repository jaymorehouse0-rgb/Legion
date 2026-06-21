# legion_workspace/gui_manager.py
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import os
import sys
import re


class LegionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LEGION WORKSPACE")
        self.root.geometry("900x750")
        self.root.configure(bg="#1e1e1e")

        self.selected_directory = os.path.expanduser("~/Desktop")
        self.execution_mode = "auto"
        self.is_processing = False
        self._stream_line_start = None

        from main import WorkspaceOrchestrator
        self.orchestrator = WorkspaceOrchestrator(gui_callback=self.log_message)

        self._build_ui()
        self.log_message("Legion Control Shell Initialized. Ready for prompt requests.")
        self.log_message("Hardware profile: Ryzen 5 5500 + RTX 3050 (GPU offload, 8GB VRAM tuned)")

    def _build_ui(self):
        header = tk.Label(self.root, text="LEGION", font=("Segoe UI", 22, "bold"), fg="#00ffcc", bg="#1e1e1e")
        header.pack(pady=15)

        dir_frame = tk.Frame(self.root, bg="#2d2d2d", bd=1, relief=tk.SUNKEN)
        dir_frame.pack(fill=tk.X, padx=20, pady=5)

        self.dir_label = tk.Label(
            dir_frame,
            text=f"Target Workspace: {self.selected_directory}",
            font=("Segoe UI", 11), fg="#ffffff", bg="#2d2d2d", anchor="w"
        )
        self.dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=8)

        dir_btn = tk.Button(
            dir_frame, text="Browse", font=("Segoe UI", 11, "bold"),
            bg="#404040", fg="#00ffcc", activebackground="#505050", activeforeground="#00ffcc",
            bd=0, padx=15, command=self._browse_directory
        )
        dir_btn.pack(side=tk.RIGHT, padx=5, pady=5)

        mode_frame = tk.Frame(self.root, bg="#1e1e1e")
        mode_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Label(mode_frame, text="Execution Strategy Matrix:", font=("Segoe UI", 11, "bold"), fg="#ffffff", bg="#1e1e1e").pack(side=tk.LEFT, padx=5)

        self.mode_var = tk.StringVar(value="auto")
        modes = [("Adaptive (Auto)", "auto"), ("Fast Track Single", "force_fast"), ("Parallel Swarm Cluster", "force_swarm")]
        for text, mode_val in modes:
            rb = tk.Radiobutton(
                mode_frame, text=text, variable=self.mode_var, value=mode_val,
                font=("Segoe UI", 11), fg="#bbbbbb", bg="#1e1e1e", activebackground="#1e1e1e", activeforeground="#ffffff",
                selectcolor="#2d2d2d", command=self._update_mode
            )
            rb.pack(side=tk.LEFT, padx=15)

        self.log_display = scrolledtext.ScrolledText(
            self.root, font=("Consolas", 14), bg="#111111", fg="#d4d4d4",
            insertbackground="white", relief=tk.FLAT, bd=0
        )
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.log_display.tag_config("user", foreground="#56b6c2")
        self.log_display.tag_config("legion", foreground="#98c379")
        self.log_display.tag_config("system", foreground="#e5c07b")
        self.log_display.tag_config("success", foreground="#00ffcc", font=("Consolas", 14, "bold"))
        self.log_display.tag_config("warning", foreground="#e06c75")

        input_frame = tk.Frame(self.root, bg="#1e1e1e")
        input_frame.pack(fill=tk.X, padx=20, pady=15)

        self.entry_box = tk.Entry(
            input_frame, font=("Consolas", 13), bg="#2d2d2d", fg="#ffffff",
            insertbackground="white", bd=0, relief=tk.FLAT
        )
        self.entry_box.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 10))
        self.entry_box.bind("<Return>", lambda event: self._submit_request())

        self.submit_btn = tk.Button(
            input_frame, text="EXECUTE", font=("Segoe UI", 12, "bold"),
            bg="#00ffcc", fg="#111111", activebackground="#00cc99", activeforeground="#111111",
            bd=0, padx=25, command=self._submit_request
        )
        self.submit_btn.pack(side=tk.RIGHT, ipady=4)

    def log_message(self, text):
        def append_text():
            self.log_display.config(state=tk.NORMAL)

            if text.startswith("[User]"):
                self.log_display.insert(tk.END, text + "\n", "user")
            elif text.startswith("[Legion]"):
                self.log_display.insert(tk.END, text + "\n", "legion")
            elif text.startswith("SUCCESS") or "SUCCESSFUL" in text:
                self.log_display.insert(tk.END, text + "\n", "success")
            elif "FAILED" in text or "EXHAUSTED" in text:
                self.log_display.insert(tk.END, text + "\n", "warning")
            else:
                self.log_display.insert(tk.END, text + "\n", "system")

            self.log_display.config(state=tk.DISABLED)
            self.log_display.see(tk.END)
        self.root.after(0, append_text)

    def begin_stream_response(self):
        def start():
            self.log_display.config(state=tk.NORMAL)
            self._stream_line_start = self.log_display.index(tk.END)
            self.log_display.insert(tk.END, "[Legion]: ", "legion")
            self.log_display.config(state=tk.DISABLED)
        self.root.after(0, start)

    def append_stream_chunk(self, text):
        def append():
            self.log_display.config(state=tk.NORMAL)
            self.log_display.insert(tk.END, text, "legion")
            self.log_display.config(state=tk.DISABLED)
            self.log_display.see(tk.END)
        self.root.after(0, append)

    def end_stream_response(self):
        def finish():
            self.log_display.config(state=tk.NORMAL)
            self.log_display.insert(tk.END, "\n")
            self.log_display.config(state=tk.DISABLED)
            self.log_display.see(tk.END)
            self._stream_line_start = None
        self.root.after(0, finish)

    def _browse_directory(self):
        dir_path = filedialog.askdirectory(initialdir=self.selected_directory)
        if dir_path:
            self.selected_directory = dir_path
            self.dir_label.config(text=f"Target Workspace: {self.selected_directory}")

    def _update_mode(self):
        self.execution_mode = self.mode_var.get()

    def _submit_request(self):
        prompt = self.entry_box.get().strip()
        if not prompt:
            return
        if self.is_processing:
            messagebox.showwarning("System Busy", "Legion is currently computing. Please wait.")
            return

        self.is_processing = True
        self.entry_box.delete(0, tk.END)

        safe_name = "legion_output.py"
        matched_words = re.findall(r"\b\w+\b", prompt.lower())
        if "app" in matched_words and len(matched_words) > matched_words.index("app") + 1:
            safe_name = f"{matched_words[matched_words.index('app') + 1]}_app.py"
        elif "script" in matched_words and len(matched_words) > matched_words.index("script") + 1:
            safe_name = f"{matched_words[matched_words.index('script') + 1]}_script.py"

        target_file_path = os.path.join(self.selected_directory, safe_name)
        mode = self.execution_mode

        threading.Thread(target=self._async_execute, args=(prompt, target_file_path, mode), daemon=True).start()

    def _async_execute(self, prompt, path, mode):
        is_code_build = any(k in prompt.lower() for k in ["build", "create", "generate", "code me", "write an app", "make a program"])

        try:
            if is_code_build:
                self.log_message(f"COMPILED INTENT INITIALIZED -> Mode: {mode}")
                self.log_message(f"Auto-Target Output Filename: {os.path.basename(path)}")

                success = self.orchestrator.deploy_pipeline(prompt, path, execution_mode=mode)
                if success:
                    self.log_message(f"OPERATION SUCCESSFUL: Output saved to -> {path}")
                else:
                    self.log_message("PIPELINE EXHAUSTED: Build phase failed validation checks.")
            else:
                self.log_message(f"\n[User]: {prompt}")
                chat_model = self.orchestrator.chat.pick_chat_model(prompt)
                self.begin_stream_response()
                try:
                    self.orchestrator.chat.converse_stream(
                        prompt,
                        on_token=self.append_stream_chunk,
                        model=chat_model,
                    )
                finally:
                    self.end_stream_response()
        finally:
            self.is_processing = False


if __name__ == "__main__":
    root = tk.Tk()
    app = LegionGUI(root)
    root.mainloop()
