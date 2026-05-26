"""
Shared graph state schema.

Define the TypedDict (or Annotated Pydantic model) that is threaded
through every node in the LangGraph StateGraph.

Sections to implement:
  - InputState   — fields provided by the caller at graph invocation
  - AgentState   — fields written/read by agent nodes during execution
  - OutputState  — fields surfaced to the caller on graph completion
"""
