"""
Analysis Agent

Responsible for processing and interpreting raw financial data:
  - Technical analysis (trends, indicators, chart patterns)
  - Fundamental analysis (valuation ratios, earnings quality)
  - Comparative / peer-group analysis
  - Risk assessment

MCP servers used by this agent (see mcp_config.json):
  - market_data_server  (for supplemental data lookups during analysis)

Implementation checklist:
  [ ] Bind MCP tools via langchain_mcp_adapters
  [ ] Create a ReAct or structured-output agent
  [ ] Expose a callable that accepts state and returns updated state fields
"""
