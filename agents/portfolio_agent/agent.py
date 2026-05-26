"""
Portfolio Agent

Responsible for translating analysis into actionable portfolio decisions:
  - Asset allocation recommendations
  - Buy / hold / sell signals
  - Position sizing and risk management
  - Rebalancing suggestions

MCP servers used by this agent (see mcp_config.json):
  - market_data_server  (current prices for position sizing)

Implementation checklist:
  [ ] Bind MCP tools via langchain_mcp_adapters
  [ ] Create a structured-output agent that emits typed decisions
  [ ] Expose a callable that accepts state and returns updated state fields
"""
