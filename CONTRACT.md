# Internal integration contract

Python 3.12; FastAPI API + local static HTML/CSS/JS frontend. Run from this directory. Product name: Орбита.

## Graph

`{name: str, nodes: [{id: str, label: str, truth?: "bot"|"human"|"unknown", clone_of?: str}], edges: [{source: str, target: str}], metadata: {source?:str, warnings?:[str], missing_nodes?:[str], root?:str}}`

Undirected simple graph. Node IDs strings, unique. Max 500 nodes and 20000 edges, no silent truncation. Ground truth is for evaluation only, never for scores or coloring partitions. Graph labels can be user input, render as text/escape HTML. Position fields x/y may be appended by analysis.

## Functions assigned to independent modules

`app.ingest.normalize_graph(data: dict) -> dict`
`app.ingest.parse_graph(content: str, filename: str = "graph.csv", name: str = "") -> dict`
`app.ingest.apply_labels(graph: dict, content: str, filename: str = "labels.csv") -> dict`
`app.ingest.demo_graph(demo_id: str = "social") -> dict`
`app.ingest.list_demos() -> list[dict]` with id,name,description.
`app.vk.fetch_vk_graph(user_id: str, token: str, max_friends: int = 80) -> dict`; networking at user request only, never persist tokens.

`app.analysis.analyze_graph(graph: dict, options: dict | None = None) -> dict`
Options: root (str or null), radius (1 or 2 or 3, only applied with root), threshold (0..1, default .65), exclude_root (bool default true: root excluded from compared neighbor sets), max_pairs (default 2000).
Return: `{graph, options, summary, orbits, pairs, warnings, evaluation}`.
summary: node_count, edge_count, density, component_count, orbit_count, nontrivial_orbits, group_order (str), candidate_count (before max_pairs), elapsed_ms.
orbits: [{id:int, nodes:[str], size:int}]. Returned graph nodes should include orbit:int and degree:int, x:float,y:float if feasible.
pairs: [{source:str,target:str,same_orbit:bool,orbit_id:int|null,common_neighbors:[str],jaccard:float,score:float,reasons:[str]}]; sorted by score, IDs tiebreak. Candidate if score >= threshold and has structural evidence, root never compared. Empty neighborhoods are not evidence of similarity. All scientific scoring conventions must be explicit in response/options or docs.
evaluation: null or object with human-readable note plus any actual precision/recall metrics based on complete supplied labels only; never infer missing truth as negative.

`app.experiments.run_experiments(graph: dict, config: dict | None = None) -> dict`
config: clone_count (default3, max10), retention (0..1 default .8), noise_levels (array default [0,.05,.15]), repeats (default3,max5), seed (default42), threshold (default .65), root (str|null), exclude_root (bool default true).
Return `{rows:[{noise,repeat,method,precision,recall,f1,tp,fp,fn,elapsed_ms}], summary:[{noise,method,precision,recall,f1}], config, warnings, example_graph}`. Methods fixed strings `neighbors`,`symmetry`,`combined`. Include control graphs without injected clones as rows with `control:true` and measured false positives, not in main means. Generation reproducible. Same perturbed graph shared across all methods. Do not select threshold based on measured test results.

## API contract (root implements)

- GET /api/health -> {status,version,engine}
- GET /api/demos -> {demos:[...]}
- GET /api/demos/{id} -> Graph
- POST /api/import JSON {content,filename,name?} -> Graph
- POST /api/labels JSON {graph,content,filename} -> Graph
- POST /api/analyze JSON {graph,options} -> Analysis result
- POST /api/experiments JSON {graph,config} -> Experiment result
- POST /api/vk JSON {user_id,token,max_friends} -> Graph
- POST /api/export/json JSON {graph} -> download graph.json
- POST /api/export/csv JSON {analysis} -> download candidates.csv
- POST /api/export/html JSON {analysis,experiments?} -> downloadable standalone HTML report
- POST /api/export/experiments JSON {experiments} -> CSV
- GET /api/projects -> {projects:[{id,name,updated_at,node_count,edge_count}]}
- POST /api/projects JSON {name,graph,options?,analysis?,experiments?} -> {id,name,updated_at}
- GET /api/projects/{id} -> project body
- DELETE /api/projects/{id} -> {ok:true}

Error responses `{detail: "Понятное сообщение"}`. HTTP requests same-origin, app only binds loopback. UI should abort timed-out requests, handle loading/errors/empty and stale results. Local project persistence server-side JSON, explicit save button.
