"""
Report Agent

Responsible for producing the final structured output:
  - Narrative investment thesis
  - Summary tables (valuation, performance, risk)
  - Formatted Markdown or PDF report

MCP servers used by this agent (see mcp_config.json):
  - document_server  (reading templates, writing output documents)

Implementation checklist:
  [ ] Bind MCP tools via langchain_mcp_adapters
  [ ] Create a structured-output / formatting agent
  [ ] Expose a callable that accepts state and returns updated state fields
"""
