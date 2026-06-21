# legion_workspace/config.py
# Tuned for: AMD Ryzen 5 5500 (6C/12T) + MSI GeForce RTX 3050 (8GB VRAM)

OLLAMA_MODEL_MATRIX = {
    "Planner":   "qwen2.5-coder:7b",    # Heavy structural logic maps
    "Builder":   "qwen2.5-coder:7b",    # Code generation syntax engine
    "Reviewer":  "qwen2.5-coder:1.5b",  # Rapid line check parser
    "Chat":      "qwen2.5-coder:1.5b"   # Conversational interface model
}

# Ollama inference and server tunables (merged into API options in main.py)
OLLAMA_PERF = {
    "num_ctx": 4096,             # 4096 fits 7B + 1.5B together in 8GB VRAM
    "num_thread": None,          # None = auto from os.cpu_count() - 1 in main.py
    "num_gpu": 99,               # Offload all layers to RTX 3050
    "temperature": 0.1,
    "keep_alive": "24h",
    "num_parallel": 3,
    "max_loaded_models": 2,      # Keep Chat 1.5B + Builder 7B resident (~5-6GB)
    "flash_attention": True,     # RTX 3050 (Ampere) supports flash attention
}

# Token caps per call type (passed to invoke_generation)
NUM_PREDICT = {
    "chat": 1024,
    "codegen": 4096,
    "review": 512,
    "planning": 2048,
}

# Pipeline retry budgets by execution path
RETRY_LIMITS = {"fast": 2, "standard": 2, "swarm": 3}

# Auto-routing: intents at or below this length (and not complex) use the fast path
SIMPLE_INTENT_MAX_LEN = 200
