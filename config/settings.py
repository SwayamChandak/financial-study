"""
Application settings.

Load environment variables (via python-dotenv) and expose typed
settings used across the project.

Sections to implement:
  - LLMSettings       — model names, temperature, max tokens
  - APIKeySettings    — financial data provider keys
  - GraphSettings     — recursion limits, checkpointer config
  - MCPSettings       — transport type, server startup timeouts

Usage pattern (to implement):
    from config.settings import settings
    model = ChatOpenAI(model=settings.llm.model_name, ...)
"""
