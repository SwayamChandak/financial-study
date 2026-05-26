"""
Research Agent

Responsible for gathering raw financial data:
  - Fetching market prices, OHLCV data, and company fundamentals
  - Pulling financial news and sentiment signals
  - Retrieving SEC filings and earnings reports

MCP servers used by this agent (see mcp_config.json):
  - market_data_server
  - news_server
  - document_server

Implementation checklist:
  [ ] Bind MCP tools via langchain_mcp_adapters
  [ ] Create a ToolNode or ReAct-style agent with the bound tools
  [ ] Expose a callable that accepts state and returns updated state fields
"""
