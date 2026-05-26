"""
Document MCP Server

An MCP server for reading and writing structured documents:
  - Fetching and parsing SEC EDGAR filings (10-K, 10-Q, 8-K)
  - Extracting text from PDF financial reports
  - Reading/writing Markdown report templates and outputs

Transport: stdio (default).

MCP tools to register:
  - fetch_sec_filing       — download a filing by CIK + form type
  - parse_pdf              — extract text from a local or remote PDF
  - read_document          — read a local Markdown / text file
  - write_document         — write content to a local file

Implementation checklist:
  [ ] Instantiate FastMCP (or mcp.Server)
  [ ] Register each tool with @server.tool()
  [ ] Implement stdio transport entry point (mcp.run_stdio_async)
"""
