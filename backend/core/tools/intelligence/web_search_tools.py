"""
core/tools/intelligence/web_search_tools.py
─────────────────────────────────────────────
Tools for performing web searches.
"""

from langchain_core.tools import tool
from langchain_tavily import TavilySearch

@tool
def perform_web_search(query: str, max_results: int = 5) -> str:
    """
    perform_web_search(query: str, max_results: int = 5) -> str
    
    Perform a live web search to gather information from the internet.
    
    IMPORTANT RULES FOR USING THIS TOOL:
    1. Use this tool ONLY when you need to look up factual information, current events, or external data that is not present in the local file system.
    2. Formulate clear, concise search queries for the best results.
    3. Do NOT use this tool to search local files.

    Args:
        query (str): The search term or specific question to look up.
        max_results (int): Maximum number of search results to return (default 5).
        
    Returns:
        str: A formatted string containing the top web search results.
    """
    try:
        tavily = TavilySearch(max_results=max_results, tavily_api_key="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")
        result = tavily.invoke(query)
        
        if not result:
            return f"No results found for query: '{query}'"
            
        return f"Web Search Results for '{query}':\n\n{str(result)}"
    except Exception as e:
        return f"Error performing web search: {str(e)}"
