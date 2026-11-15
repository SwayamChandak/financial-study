"""Generate a combined Mermaid diagram from the compiled LangGraph objects."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from graph.graph_builder import chat_graph, study_graph

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "docs" / "graph.mmd"


def _graph_lines(
    graph: CompiledStateGraph,
    graph_id: str,
) -> tuple[list[str], list[str], list[str]]:
    """Return node, edge, and style lines from LangGraph's Mermaid output."""
    rendered = graph.get_graph().draw_mermaid()
    try:
        graph_start = rendered.splitlines().index("graph TD;") + 1
    except ValueError as exc:
        raise RuntimeError(
            "LangGraph Mermaid output did not contain graph TD;"
        ) from exc

    nodes: list[str] = []
    edges: list[str] = []
    styles: list[str] = []
    for raw_line in rendered.splitlines()[graph_start:]:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("classDef "):
            styles.append(line)
        elif "-->" in line or ".->" in line:
            line = line.replace("__start__", f"{graph_id}_start")
            line = line.replace("__end__", f"{graph_id}_end")
            edges.append(line)
        else:
            if line.startswith("__start__("):
                line = line.replace("__start__(", f"{graph_id}_start(", 1)
            elif line.startswith("__end__("):
                line = line.replace("__end__(", f"{graph_id}_end(", 1)
            nodes.append(line)

    return nodes, edges, styles


def generate_graph_diagram() -> Path:
    """Write the study and chat graphs as grouped Mermaid subgraphs."""
    graph_sections = [
        ("study", "Study graph", study_graph),
        ("chat", "Chat graph", chat_graph),
    ]
    lines = [
        "%% Dashed arrows are conditional routes; labels are routing outcomes.",
        "flowchart TD",
    ]
    style_lines: list[str] = []

    for graph_id, label, graph in graph_sections:
        nodes, edges, styles = _graph_lines(graph, graph_id)
        lines.append(f'  subgraph {graph_id}["{label}"]')
        lines.extend(f"    {node}" for node in nodes)
        lines.extend(f"    {edge}" for edge in edges)
        lines.append("  end")
        style_lines.extend(styles)

    lines.extend(dict.fromkeys(style_lines))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_PATH


if __name__ == "__main__":
    print(generate_graph_diagram())
