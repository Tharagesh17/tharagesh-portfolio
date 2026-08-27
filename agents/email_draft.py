"""Agent 4 — Email Drafting."""
from langchain_core.messages import HumanMessage, SystemMessage
from chat_sarvam import chat


def run(context: str, tone: str = "professional") -> str:
    primary = [
        SystemMessage(content=(
            f"You write clear, {tone} emails. Return only the email body, no preamble, "
            "no subject line, no quotes."
        )),
        HumanMessage(content=f"Context / bullet points:\n{context}"),
    ]
    fallback = [
        SystemMessage(content="You write clear professional emails. Return only the body."),
        HumanMessage(content=f"Draft a {tone} email from these points:\n{context}"),
    ]
    return chat(primary, temperature=0.4, fallback_messages=fallback)
