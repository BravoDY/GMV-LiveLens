import json, collections

with open('graphify-out/graph.json', 'r', encoding='utf-8') as f:
    graph = json.load(f)

nodes = graph.get('nodes', [])
links = graph.get('links', [])

node_map = {n['id']: n for n in nodes}

# Filter to project code
project_src_prefixes = ('backend/', 'frontend/', 'tests/', 'scripts/', '.github/', 'deploy/')

# God nodes for project code only
degree = collections.Counter()
for link in links:
    degree[link.get('source', '')] += 1
    degree[link.get('target', '')] += 1

# Project code with highest degree
project_deg = []
for nid, deg in degree.items():
    n = node_map.get(nid, {})
    src = n.get('source_file', '') or ''
    if src and any(src.startswith(p) for p in project_src_prefixes):
        project_deg.append((nid, deg, src, n.get('label', '')))

project_deg.sort(key=lambda x: -x[1])

print(f'=== TOP 30 PROJECT CODE NODES (degree >= 3) ===')
for nid, deg, src, label in project_deg[:30]:
    if deg >= 3:
        print(f'  [{deg:>4d}] {label[:65]}  ({src})')

# Top backend core files
backend_nodes = [(nid, deg, src, label) for nid, deg, src, label in project_deg if src.startswith('backend/')]
print(f'\n=== BACKEND GOD NODES ===')
for nid, deg, src, label in backend_nodes[:15]:
    print(f'  [{deg:>4d}] {label[:65]}  ({src})')

# Top frontend files
frontend_nodes = [(nid, deg, src, label) for nid, deg, src, label in project_deg if src.startswith('frontend/')]
print(f'\n=== FRONTEND GOD NODES ===')
for nid, deg, src, label in frontend_nodes[:15]:
    print(f'  [{deg:>4d}] {label[:65]}  ({src})')

# Project file-level stats
file_degree = collections.defaultdict(int)
file_labels = {}
for nid, deg in degree.items():
    n = node_map.get(nid, {})
    src = n.get('source_file', '') or ''
    if src and any(src.startswith(p) for p in project_src_prefixes):
        file_degree[src] += deg
        if src not in file_labels:
            file_labels[src] = set()
        file_labels[src].add(n.get('label', '').lower())

print(f'\n=== TOP 15 PROJECT FILES (aggregated degree) ===')
top_files = sorted(file_degree.items(), key=lambda x: -x[1])[:15]
for f, d in top_files:
    print(f'  [{d:>4d}] {f}')

print(f'\nTotal project code nodes with edges: {len(project_deg)}')
