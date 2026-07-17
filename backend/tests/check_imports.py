try:
    from langchain.agents.middleware import SummarizationMiddleware
    print("SummarizationMiddleware found!")
except ImportError:
    print("SummarizationMiddleware NOT found in langchain.agents.middleware")

try:
    from langgraph.checkpoint.memory import MemorySaver
    print("MemorySaver found in langgraph.checkpoint.memory")
except ImportError:
    print("MemorySaver NOT found in langgraph.checkpoint.memory")
