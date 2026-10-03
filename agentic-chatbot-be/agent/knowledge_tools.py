from langchain_core.tools import tool

from agent.knowledge_search import get_backend


def _format_hits(hits, empty_message: str) -> str:
    if not hits:
        return empty_message
    return "\n\n".join(f"(source: {h['source']})\n{h['text']}" for h in hits)


@tool
def search_faq_articles(query: str, domain: str = "general", max_results: int = 5) -> str:
    """Search the FAQ knowledge base for a customer's question.
    Args:
        query: The customer's question or key phrase.
        domain: One of 'ecommerce', 'insurance', or 'general'.
        max_results: Maximum number of matching FAQ entries to return.
    """
    hits = get_backend().retrieve(query, top_k=max_results, domain=domain)
    return _format_hits(hits, "No relevant FAQ entries found.")


@tool
def search_comprehensive_knowledge(query: str, domain: str = "general", max_results: int = 3) -> str:
    """Search across the entire knowledge base (FAQs, policies) at once.
    Use this when you're not sure which specific category the customer's
    question falls into.
    Args:
        query: The customer's question or key phrase.
        domain: One of 'ecommerce', 'insurance', or 'general'.
        max_results: Maximum number of results to return.
    """
    hits = get_backend().retrieve(query, top_k=max_results, domain=domain)
    return _format_hits(hits, "No relevant knowledge base entries found.")


KNOWLEDGE_TOOLS = [search_faq_articles, search_comprehensive_knowledge]
