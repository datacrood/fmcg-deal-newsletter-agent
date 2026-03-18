"""Tracks LLM token usage and cost across the pipeline run."""

import threading


class CostTracker:
    """Thread-safe accumulator for LLM usage stats."""

    def __init__(self):
        self._lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0
        self.calls = 0

    def record(self, response) -> None:
        """Extract usage from a LangChain response and accumulate."""
        usage = (response.response_metadata or {}).get("token_usage", {})
        with self._lock:
            self.prompt_tokens += usage.get("prompt_tokens", 0)
            self.completion_tokens += usage.get("completion_tokens", 0)
            self.total_cost += usage.get("cost", 0.0)
            self.calls += 1

    def summary(self) -> str:
        """Return a human-readable cost summary."""
        return (
            f"LLM usage: {self.calls} calls, "
            f"{self.prompt_tokens} prompt + {self.completion_tokens} completion tokens, "
            f"cost: ${self.total_cost:.4f}"
        )


# Single instance shared across the pipeline
tracker = CostTracker()
