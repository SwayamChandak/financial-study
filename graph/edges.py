"""
Edge / routing logic for the LangGraph graph.

Conditional edge functions inspect the current state and return the name
of the next node to execute.  Unconditional edges are wired directly in
builder.py.

Planned edge functions:
  - route_after_research   — decide whether to go to analysis or back to research
  - route_after_analysis   — decide whether to go to portfolio or straight to report
  - should_end             — determine if the graph has reached a terminal condition
"""
