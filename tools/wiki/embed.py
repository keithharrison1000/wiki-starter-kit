"""Local embeddings via Ollama. No cloud APIs."""

from __future__ import annotations

DEFAULT_MODEL = "nomic-embed-text"


def get_embedding(text: str, model: str = DEFAULT_MODEL) -> list[float]:
    import ollama

    try:
        resp = ollama.embeddings(model=model, prompt=text)
    except Exception as exc:
        raise RuntimeError(
            "Could not reach Ollama for local embeddings. Install it "
            f"(`brew install ollama`), start it, and pull the model "
            f"(`ollama pull {model}`)."
        ) from exc
    return resp["embedding"]
