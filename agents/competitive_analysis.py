"""Agent 2 — Competitive Analysis (multi-step: search -> compare)."""
from langchain_core.messages import HumanMessage, SystemMessage
from chat_sarvam import chat
from search import duckduckgo


def run(competitors: str, dimension: str = "features and pricing") -> str:
    # One combined search keeps it fast and avoids hammering the search/LLM.
    names = [c.strip() for c in competitors.split(",") if c.strip()][:3]
    brief = duckduckgo(f"{' vs '.join(names)} {dimension}", limit=6)
    primary = [
        SystemMessage(content=(
            "You are a strategy analyst. Compare the companies on the given dimension. "
            "Output a markdown comparison table and 3 strategic takeaways. Cite sources."
        )),
        HumanMessage(content=f"Companies: {', '.join(names)}\nDimension: {dimension}\n\nResearch:\n{brief}"),
    ]
    fallback = [
        SystemMessage(content="You are a strategy analyst. Answer concisely in markdown."),
        HumanMessage(content=f"Compare these on {dimension}: {', '.join(names)}. (Live sources were unavailable.)"),
    ]
    return chat(primary, fallback_messages=fallback)
