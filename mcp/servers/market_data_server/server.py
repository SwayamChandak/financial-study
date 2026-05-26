"""
Market Data MCP Server

An MCP server that exposes live and historical market data as tools
and/or resources to connected agents.

Transport: stdio (default) — can be switched to SSE for remote access.

MCP tools to register:
  - get_current_price      — real-time quote for a ticker
  - get_ohlcv              — historical OHLCV bars
  - get_company_overview   — company metadata
  - get_financial_ratios   — valuation and quality ratios

Data providers to integrate (configure via environment variables):
  - Alpha Vantage  (ALPHA_VANTAGE_API_KEY)
  - Polygon.io     (POLYGON_API_KEY)
  - yfinance       (no key required, rate-limited)

Implementation checklist:
  [ ] Instantiate FastMCP (or mcp.Server)
  [ ] Register each tool with @server.tool()
  [ ] Implement stdio transport entry point (mcp.run_stdio_async)
"""
