"""
Graph builder — assembles the StateGraph from nodes and edges.

Responsibilities:
  - Import state schema from state.schema
  - Import node functions from graph.nodes
  - Import edge / routing functions from graph.edges
  - Create a StateGraph, add nodes, add edges (unconditional + conditional)
  - Compile and export the runnable graph

Checklist:
  [ ] Instantiate StateGraph with the shared state class
  [ ] Add each node via graph.add_node(name, fn)
  [ ] Set the entry point (graph.set_entry_point)
  [ ] Wire unconditional edges (graph.add_edge)
  [ ] Wire conditional edges (graph.add_conditional_edges)
  [ ] Add a human-in-the-loop interrupt if required
  [ ] graph.compile() — optionally pass a checkpointer for persistence
"""
