"""
callmap.render
==============
Renders a callmap graph as an interactive, draggable HTML page via pyvis and
vis-network. Nodes can be dragged, zoomed, and clicked, with colors grouped by
source file.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pyvis.network import Network

_PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#B279A2", "#E45756",
    "#72B7B2", "#EECA3B", "#FF9DA6", "#9D755D", "#BAB0AC",
]


def render_html(graph: nx.DiGraph, output_path: str = "callmap.html", title: str = "callmap") -> str:
    net = Network(
        height="850px",
        width="100%",
        directed=True,
        notebook=False,
        cdn_resources="in_line",
        bgcolor="#111318",
        font_color="#EAEAEA",
    )
    net.set_options("""
    {
      "nodes": {"shape": "box", "borderWidth": 1, "shadow": false,
                 "font": {"size": 14}},
      "edges": {"arrows": {"to": {"enabled": true, "scaleFactor": 0.6}},
                "smooth": {"type": "dynamic"}, "color": {"opacity": 0.55}},
      "physics": {"solver": "forceAtlas2Based",
                   "forceAtlas2Based": {"gravitationalConstant": -60,
                                          "springLength": 130,
                                          "springConstant": 0.06},
                   "stabilization": {"iterations": 150}},
      "interaction": {"hover": true, "navigationButtons": true,
                        "keyboard": true, "multiselect": true}
    }
    """)

    modules = sorted({data.get("module", "") for _, data in graph.nodes(data=True)})
    color_for = {m: _PALETTE[i % len(_PALETTE)] for i, m in enumerate(modules)}

    for node, data in graph.nodes(data=True):
        module = data.get("module", "")
        label = node.split(".", 1)[1] if "." in node else node
        title_text = f"{node}\\nfile: {data.get('file')}\\nline: {data.get('lineno')}"
        net.add_node(
            node,
            label=label,
            title=title_text,
            color=color_for.get(module, "#888"),
            group=module,
        )

    for src, dst in graph.edges():
        net.add_edge(src, dst)

    output = Path(output_path)
    if output.parent != Path("."):
        output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(net.generate_html(notebook=False), encoding="utf-8")
    return str(output)
