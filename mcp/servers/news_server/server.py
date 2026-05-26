"""
News MCP Server

An MCP server that exposes financial news retrieval and sentiment
signals as tools to connected agents.

Transport: stdio (default).

MCP tools to register:
  - search_news            — full-text news search across sources
  - get_ticker_news        — news filtered to a specific ticker
  - get_earnings_calendar  — upcoming earnings dates

Data providers to integrate:
  - NewsAPI
  - Finnhub
  - Alpha Vantage News endpoint

Implementation checklist:
  [ ] Instantiate FastMCP (or mcp.Server)
  [ ] Register each tool with @server.tool()
  [ ] Implement stdio transport entry point (mcp.run_stdio_async)
"""
