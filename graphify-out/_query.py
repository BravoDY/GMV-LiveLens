import json, networkx as nx
from networkx.readwrite import json_graph
from pathlib import Path

data = json.loads(Path('graphify-out/graph.json').read_text(encoding='utf-8'))
G = json_graph.node_link_graph(data, edges='links')

scheduler_nodes = []
ocr_nodes = []
for n, d in G.nodes(data=True):
    label = (d.get('label', '') + d.get('id', '')).lower()
    if 'scheduler' in label or 'schedule' in label or '调度' in label:
        scheduler_nodes.append(n)
    if 'ocr' in label:
        ocr_nodes.append(n)

print(f"=== Scheduler 相关节点 ({len(scheduler_nodes)}) ===")
for n in scheduler_nodes[:12]:
    d = G.nodes[n]
    print(f"  {d.get('label', n)}  [src={d.get('source_file','?')}]")

print(f"\n=== OCR 相关节点 ({len(ocr_nodes)}) ===")
for n in ocr_nodes[:12]:
    d = G.nodes[n]
    print(f"  {d.get('label', n)}  [src={d.get('source_file','?')}]")

print(f"\n=== 最短路径（scheduler <-> ocr）===")
found = False
for sn in scheduler_nodes[:3]:
    for on in ocr_nodes[:3]:
        try:
            path = nx.shortest_path(G, sn, on)
            hops = len(path) - 1
            if not found or hops <= 3:
                found = True
                print(f"\n{hops} hops:")
                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    raw = G[u][v]
                    edge = next(iter(raw.values()), {}) if isinstance(G, nx.MultiGraph) else raw
                    rel = edge.get('relation', '?')
                    conf = edge.get('confidence', '?')
                    src = edge.get('source_file', '?')
                    lu = G.nodes[u].get('label', u)
                    lv = G.nodes[v].get('label', v)
                    print(f"  {lu} --[{rel}]--> {lv}  [{conf}] ({src})")
        except nx.NetworkXNoPath:
            pass
        except Exception as e:
            pass

if not found:
    print("\n无直接路径，尝试 BFS 共同邻居...")
    all_ocr_neighbors = set()
    for on in ocr_nodes:
        for nb in G.neighbors(on):
            all_ocr_neighbors.add(nb)
    for sn in scheduler_nodes[:5]:
        for nb in G.neighbors(sn):
            if nb in all_ocr_neighbors:
                raw = G[sn][nb]
                edge = next(iter(raw.values()), {}) if isinstance(G, nx.MultiGraph) else raw
                print(f"  共同邻居: {G.nodes[nb].get('label', nb)} [{edge.get('relation','?')}]")
