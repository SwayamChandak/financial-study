"""
Node functions for the LangGraph graph.

Each function here corresponds to one node in the StateGraph.
Nodes receive the current state, perform work (call an agent, run a tool,
transform data), and return a partial state dict with updates.

Planned nodes:
  - research_node   — delegates to research_agent to fetch financial data
  - analysis_node   — delegates to analysis_agent to analyse the data
  - portfolio_node  — delegates to portfolio_agent for decision-making
  - report_node     — delegates to report_agent to produce the final report
  - human_review_node — optional interrupt node for human-in-the-loop review
"""
