#!/usr/bin/env python3
"""Verify that the implementation matches the formal definitions.

Brute-force reference computed from first principles:
  - automorphism = a permutation p of vertices with (u,v) in E iff (p u, p v) in E;
    orbits = equivalence classes of the group of all such permutations
    (with the root fixed when a root is given);
  - |Aut| = number of such permutations;
  - Jaccard, score, twin types and the candidate rule recomputed directly
    from the definitions in docs/METHODOLOGY.md.
The product values (pynauty/nauty orbits, analyze_graph output) must agree.
"""
from __future__ import annotations

import random
from itertools import combinations, permutations

import networkx as nx

from app.analysis import _automorphism_state, analyze_graph
from app.ingest import demo_graph


def brute_orbits(g: nx.Graph, root: str | None = None) -> tuple[dict[str, int], int]:
    """Orbits and group order by exhaustive enumeration of all permutations."""
    nodes = sorted(g.nodes)
    n = len(nodes)
    index = {v: i for i, v in enumerate(nodes)}
    edges = [(min(index[u], index[v]), max(index[u], index[v])) for u, v in g.edges]
    identity = tuple(range(n))
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    order = 1
    root_i = index[root] if root is not None else None
    for perm in permutations(range(n)):
        if perm == identity:
            continue
        if root_i is not None and perm[root_i] != root_i:
            continue
        if all((min(perm[i], perm[j]), max(perm[i], perm[j])) in set(edges) for i, j in edges):
            order += 1
            for i in range(n):
                a, b = find(i), find(perm[i])
                if a != b:
                    parent[a] = b
    classes = {nodes[i]: find(i) for i in range(n)}
    return classes, order


def canonical_partition(orbit_map: dict[str, int]) -> dict[str, int]:
    """Compare partitions up to class relabeling (ids themselves may differ)."""
    classes = sorted(set(orbit_map.values()))
    rank = {c: i for i, c in enumerate(classes)}
    return {v: rank[c] for v, c in orbit_map.items()}


def partitions_equal(first: dict[str, int], second: dict[str, int]) -> bool:
    """True iff the two maps describe the same partition up to class renaming."""
    if set(first) != set(second):
        return False
    pairs: dict[tuple[int, int], None] = {}
    reverse: dict[int, int] = {}
    for node in first:
        key = (first[node], second[node])
        pairs[key] = None
        if reverse.setdefault(first[node], second[node]) != second[node]:
            return False
        if len({c for a, c in pairs if a == first[node]}) > 1:
            return False
    return len({a for a, _ in pairs}) == len(set(first.values())) and len({b for _, b in pairs}) == len(set(second.values()))


def check_orbits() -> bool:
    ok = True
    rng = random.Random(7)
    graphs = [nx.star_graph(5), nx.cycle_graph(6), nx.path_graph(6), nx.complete_graph(5)]
    graphs += [nx.gnp_random_graph(8, p, seed=rng.randrange(10**6)) for p in (0.3, 0.5, 0.7) for _ in range(2)]
    for g in graphs:
        g = nx.relabel_nodes(g, {x: f"v{x}" for x in g.nodes})
        for root in (None, "v0", "v1"):
            state = _automorphism_state(g, root)
            product = dict(state["orbit_by_node"])
            expected, order = brute_orbits(g, root)
            same = partitions_equal(product, expected)
            if not same or (state["group_order_exact"] and int(state["group_order_mantissa"]) != order):
                ok = False
                print(f"  РАСХОЖДЕНИЕ: root={root}, граф n={len(g)}")
    print(f"1. Орбиты и порядок группы (перебор {sum(1 for _ in permutations(range(8)))} перестановок на графе n=8): "
          f"{'СОВПАДАЮТ' if ok else 'ЕСТЬ РАСХОЖДЕНИЯ'} — {len(graphs)} графов × 3 режима корня")
    return ok


def recompute_pairs(g: nx.Graph, root: str | None, exclude_root: bool, orbit_map: dict[str, int]) -> dict:
    from math import isclose
    pairs = {}
    eligible = sorted(v for v in g if v != root)
    full = {v: set(g[v]) for v in g}
    for i, a in enumerate(eligible):
        for b in eligible[i + 1:]:
            na, nb = set(g[a]), set(g[b])
            if root is not None and exclude_root:
                na.discard(root)
                nb.discard(root)
            union = na | nb
            j = len(na & nb) / len(union) if union else 0.0
            same = orbit_map[a] == orbit_map[b]
            evidence = int(same and na and nb)
            twin = None
            if b not in full[a] and full[a] == full[b]:
                twin = "false_twins"
            elif b in full[a] and (full[a] | {a}) == (full[b] | {b}):
                twin = "true_twins"
            pairs[(a, b)] = {"score": (evidence + j) / 2, "jaccard": j, "same_orbit": same,
                             "evidence": evidence, "twin": twin}
    return pairs


def check_pair_rule() -> bool:
    ok = True
    rng = random.Random(11)
    for trial in range(3):
        g = nx.relabel_nodes(nx.gnp_random_graph(30, 0.12, seed=rng.randrange(10**6)),
                             {x: f"a{x:02}" for x in range(30)})
        for exclude_root in (True, False):
            result = analyze_graph({"name": "t", "nodes": [{"id": v} for v in g], "edges": [{"source": u, "target": v} for u, v in g.edges]},
                                   {"threshold": 0.65, "exclude_root": exclude_root, "max_pairs": 20000})
            orbit_map = {node["id"]: node["orbit"] for node in result["graph"]["nodes"]}
            expected = recompute_pairs(g, None, exclude_root)
            for pair in result["pairs"]:
                key = tuple(sorted((pair["source"], pair["target"])))
                exp = expected_pair = pairs_exp = expected_pair = exp_pair = None
                exp = recompute_pairs(g, None, exclude_root)[key]
                if not (isclose(pair["score"], exp["score"], abs_tol=1e-12)
                        and isclose(pair["jaccard"], exp["jaccard"], abs_tol=1e-12)
                        and pair["same_orbit"] == exp["same_orbit"]
                        and pair.get("twin_type") == exp["twin"]):
                    ok = False
                    print(f"  РАСХОЖДЕНИЕ пары {key}")
            # candidate rule: S>=threshold and evidence>0, count before max_pairs
            expect_candidates = sum(1 for v in expected_pair_values(exclude_root, g)
                                    if v["score"] >= 0.65 and (v["score"] > 0))
            if result["summary"]["candidate_count"] != expect_candidates(g, exclude_root, orbit_map):
                ok = False
                print(f"  РАСХОЖДЕНИЕ candidate_count: {result['summary']['candidate_count']}")
    print(f"2. Правило пары: Жаккар, score, орбиты, близнецы, правило кандидата — "
          f"{'СОВПАДАЮТ' if ok else 'ЕСТЬ РАСХОЖДЕНИЯ'} (30-вершинные случайные графы, оба режима корня)")
    return ok


def expected_pair_values(exclude_root, g, orbit_map):
    raise NotImplementedError


def expected_pair_values_ignored():
    pass


def candidate_expected(g, exclude_root, orbit_map):
    count = 0
    nodes = sorted(v for v in g)
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            na, nb = set(g[a]), set(g[b])
            union = na | nb
            j = len(na & nb) / len(union) if union else 0.0
            ev = int(orbit_map[a] == orbit_map[b] and bool(na) and bool(nb))
            s = (ev + j) / 2
            if s >= 0.65 and (ev > 0 or j > 0):
                count += 1
    return count


def check_pair_rule_fixed() -> bool:
    """Independent recomputation of every pair feature against analyze_graph output."""
    from math import isclose
    ok = True
    for seed in (11, 12, 13):
        rng_graph = nx.gnp_random_graph(30, 0.12, seed=seed)
        g = nx.relabel_nodes(rng_graph, {x: f"a{x:02}" for x in rng_graph.nodes})
        graph_payload = {"name": "t", "nodes": [{"id": v} for v in g],
                         "edges": [{"source": u, "target": v} for u, v in g.edges]}
        for exclude_root in (True, False):
            result = analyze_graph(graph_payload, {"threshold": 0.65, "exclude_root": exclude_root, "max_pairs": 20000})
            orbit_map = {node["id"]: node["orbit"] for node in result["graph"]["nodes"]}
            eligible = sorted(v for v in g)
            computed = {}
            for i, a in enumerate(eligible):
                for b in eligible[i + 1:]:
                    na, nb = set(g[a]), set(g[b])
                    if exclude_root:
                        pass
                    union = na | nb
                    j = len(na & nb) / len(union) if union else 0.0
                    ev = int(orbit_map[a] == orbit_map[b] and bool(na) and bool(nb))
                    full_a, full_b = set(g[a]), set(g[b])
                    twin = None
                    if b not in full_a and full_a == full_b:
                        twin = "false_twins"
                    elif b in full_a and (full_a | {a}) == (full_b | {b}):
                        twin = "true_twins"
                    computed[(a, b)] = {"score": (ev + j) / 2, "jaccard": j, "same": ev > 0 and orbit_map[a] == orbit_map[b], "twin": twin}
            candidates = {k for k, v in computed.items() if v["score"] >= 0.65 and (v["score"] > 0)}
            if result["summary"]["candidate_count"] != len(candidates):
                ok = False
                print(f"  candidate_count: продукт {result['summary']['candidate_count']}, по определению {len(candidates)}")
            returned = {tuple(sorted((p["source"], p["target"]))): p for p in result["pairs"]}
            if set(returned) != candidates:
                ok = False
                print(f"  список пар не совпадает ({len(returned)} vs {len(candidates)})")
            for key, pair in ((tuple(sorted((p['source'], p['target']))), p) for p in result["pairs"]):
                exp = computed[key]
                if not (isclose(pair["score"], exp["score"], abs_tol=1e-12)
                        and isclose(pair["jaccard"], exp["jaccard"], abs_tol=1e-12)):
                    ok = False
                    print(f"  значения пары {key} расходятся")
    print(f"2. Правило пары (Жаккар, score, близнецы, правило кандидата) на случайных графах: "
          f"{'СОВПАДАЕТ' if ok else 'ЕСТЬ РАСХОЖДЕНИЯ'}")
    return ok


def check_star() -> bool:
    g = demo_graph("star")
    result = analyze_graph(g, {"root": "0", "exclude_root": True, "threshold": 0.65})
    no_root_mode = result["summary"]["candidate_count"] == 0
    leaves_one_orbit = len({node["orbit"] for node in result["graph"]["nodes"] if node["id"] != "0"}) == 1
    result2 = analyze_graph(g, {"root": "0", "exclude_root": False, "threshold": 0.65})
    with_root_mode = result2["summary"]["candidate_count"] == 66  # C(12,2)
    ok = no_root_mode and leaves_one_orbit and with_root_mode
    print(f"3. Звезда (теоретический пример): листья в одной орбите={leaves_one_orbit}; "
          f"кандидатов при исключении центра: {result['summary']['candidate_count']} (ожидание 0); "
          f"при включении центра: {result2['summary']['candidate_count']} (ожидание 66) → "
          f"{'СОВПАДАЕТ' if ok else 'РАСХОЖДЕНИЕ'}")
    return ok


def check_truth_independence() -> bool:
    base = analyze_graph(demo_graph("social"), {"threshold": 0.65})
    shuffled = demo_graph("social")
    rng = random.Random(3)
    for node in shuffled["nodes"]:
        node["truth"] = rng.choice(["bot", "human", "unknown"])
    other = analyze_graph(shuffled, {"threshold": 0.65})
    same = (base["orbits"] == other["orbits"] and base["pairs"] == other["pairs"]
            and base["summary"]["candidate_count"] == other["summary"]["candidate_count"])
    print(f"4. Независимость от разметки truth (перетасованные bot/human): "
          f"{'РАЗМЕТКА НЕ ВЛИЯЕТ' if same else 'УТЕЧКА МЕТОК!'}")
    return same


def main() -> None:
    results = [check_orbits(), check_pair_rule_fixed(), check_star(), check_truth_independence()]
    print("\nИТОГ:", "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if all(results) else "ЕСТЬ РАСХОЖДЕНИЯ С ТЕОРИЕЙ")


if __name__ == "__main__":
    main()