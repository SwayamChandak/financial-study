"""
Shared MCP client helpers.

Utilities for loading MCP server configs and initialising
langchain_mcp_adapters clients for use by agents.

Planned helpers:
  - load_mcp_config(config_path: str) -> dict
      Reads and validates an agent's mcp_config.json.

  - create_mcp_client(server_name: str, config: dict) -> MCPClient
      Spins up a stdio or SSE MCP client for the given server config.

  - get_mcp_tools(agent_config_path: str) -> list[BaseTool]
      Convenience wrapper: load config → start clients → return bound tools.
"""
