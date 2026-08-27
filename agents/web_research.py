"""Agent 1 — Web Research (multi-step: search -> synthesize)."""
from langchain_core.messages import HumanMessage, SystemMessage
from chat_sarvam import chat
from search import duckduckgo


def run(query: str) -> str:
    sources = duckduckgo(query)
    primary = [
        SystemMessage(content=(
            "You are a research analyst. Using the provided sources, write a tight "
            "markdown report: a one-line summary, then 3-5 bullet findings, each citing "
            "its Source URL inline. If sources are empty, say so plainly."
        )),
        HumanMessage(content=f"Query: {query}\n\nSources:\n{sources}"),
    ]
    fallback = [
        SystemMessage(content="You are a research analyst. Answer concisely in markdown."),
        HumanMessage(content=f"Give a brief, useful overview of: {query}. (Live sources were unavailable.)"),
    ]
    return chat(primary, fallback_messages=fallback)
