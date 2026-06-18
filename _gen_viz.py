import json, networkx as nx
from networkx.readwrite import json_graph
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / 'graphify-out'

data = json.loads((DATA_DIR / 'graph.json').read_text(encoding='utf-8'))
G = json_graph.node_link_graph(data, edges='links')

top_n = 300
sorted_nodes = sorted(G.degree, key=lambda x: x[1], reverse=True)
top_ids = {n for n, d in sorted_nodes[:top_n]}

sub_nodes = []
sub_edges = []
for u, v in G.edges():
    if u in top_ids and v in top_ids:
        raw = G[u][v]
        edge = next(iter(raw.values()), {}) if isinstance(G, nx.MultiGraph) else raw
        sub_edges.append({
            'from': u,
            'to': v,
            'label': edge.get('relation', ''),
        })

for nid in top_ids:
    d = G.nodes[nid]
    label = d.get('label', nid)
    if len(label) > 60:
        label = label[:57] + '...'
    sub_nodes.append({
        'id': nid,
        'label': label,
        'title': d.get('source_file', ''),
        'value': min(G.degree(nid), 20),
    })

nodes_json = json.dumps(sub_nodes, ensure_ascii=False)
edges_json = json.dumps(sub_edges, ensure_ascii=False)
total = G.number_of_nodes()

html = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>GMV-LiveLens Knowledge Graph</title>
<script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"></script>
<style>
  body { margin:0; font-family:"Microsoft YaHei",sans-serif; background:#0d1117; }
  #mynetwork { width:100vw; height:100vh; }
  .bar { position:fixed; top:12px; left:16px; color:#8b949e; font-size:13px; z-index:10; }
  .search { position:fixed; top:10px; right:16px; z-index:10; }
  .search input { padding:8px 14px; border-radius:8px; border:1px solid #30363d; background:#161b22; color:#e6edf3; width:260px; font-size:14px; outline:none; }
  .search input:focus { border-color:#58a6ff; }
  .legend { position:fixed; bottom:12px; left:16px; color:#8b949e; font-size:11px; z-index:10; }
</style>
</head>
<body>
<div class="bar">''' + f'GMV-LiveLens · Top {top_n} / {total:,} 节点' + r'''</div>
<div class="search"><input id="search" placeholder="搜索节点..." oninput="doSearch()"></div>
<div class="legend">滚轮缩放 · 拖拽平移 · 点击聚焦 · 搜索过滤</div>
<div id="mynetwork"></div>
<script>
var NODES = ''' + nodes_json + r''';
var EDGES = ''' + edges_json + r''';

var nodes = new vis.DataSet(NODES);
var edges = new vis.DataSet(EDGES);
var container = document.getElementById('mynetwork');
var data = { nodes: nodes, edges: edges };
var options = {
  physics: {
    solver: 'forceAtlas2Based',
    forceAtlas2Based: { gravitationalConstant: -60, centralGravity: 0.008, springLength: 120 },
    stabilization: { iterations: 200 }
  },
  nodes: {
    shape: 'dot',
    size: 8,
    font: { size: 11, color: '#c9d1d9', face: 'Microsoft YaHei' },
    borderWidth: 1,
    borderWidthSelected: 3,
    color: { background: '#58a6ff', border: '#1f6feb', highlight: { background: '#79c0ff', border: '#58a6ff' } }
  },
  edges: {
    arrows: 'to',
    smooth: { type: 'continuous' },
    color: { color: '#30363d', highlight: '#58a6ff', opacity: 0.35 },
    font: { size: 8, color: '#8b949e', strokeWidth: 0, align: 'middle' }
  },
  interaction: { hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true }
};
var network = new vis.Network(container, data, options);

network.on('stabilizationProgress', function(p) {
  document.querySelector('.bar').textContent = 'GMV-LiveLens · 布局中 ' + Math.round(p.iterations/p.total*100) + '%';
});
network.once('stabilizationIterationsDone', function() {
  document.querySelector('.bar').textContent = ''' + f"'GMV-LiveLens · Top {top_n} / {total:,} 节点'" + r''';
});

function doSearch() {
  var q = document.getElementById('search').value.toLowerCase();
  if (!q) { nodes.forEach(function(n) { nodes.update({id:n.id, hidden:false}); }); return; }
  var matched = new Set();
  nodes.forEach(function(n) { if (n.label.toLowerCase().indexOf(q)>=0) matched.add(n.id); });
  var allEdges = edges.get();
  nodes.forEach(function(n) {
    var keep = matched.has(n.id);
    if (!keep) {
      for (var i=0; i<allEdges.length; i++) {
        var e = allEdges[i];
        if ((e.from===n.id && matched.has(e.to)) || (e.to===n.id && matched.has(e.from))) { keep=true; break; }
      }
    }
    nodes.update({id:n.id, hidden:!keep});
  });
}
</script>
</body>
</html>'''

out = DATA_DIR / 'graph_core.html'
out.write_text(html, encoding='utf-8')
print(f'OK -> {out}')
print(f'节点: {len(sub_nodes)}, 边: {len(sub_edges)}')
