"""
Layer 7 — Event Graph Builder.

In-memory directed graph for consolidating accepted pairs/groups into
connected event clusters and arb baskets for Phase 4.
No external graph library — uses dict-of-sets.
"""

from __future__ import annotations

from collections import defaultdict

from algorithm.Phase_3.models import Phase3Decision, RelationshipType, Verdict


class EventGraph:
    """
    Directed graph where nodes are market_ids and edges represent
    validated relationships from Phase 3 decisions.
    """

    def __init__(self) -> None:
        # adjacency: market_id -> set of neighbour market_ids
        self._adj: dict[str, set[str]] = defaultdict(set)
        # edge metadata: (market_id_a, market_id_b) -> decision metadata
        self._edges: dict[tuple[str, str], dict[str, object]] = {}
        # all market ids seen
        self._nodes: set[str] = set()

    def add_accepted_pair(self, decision: Phase3Decision) -> None:
        """Add an accepted candidate pair to the graph."""
        if decision.verdict != Verdict.ACCEPT:
            return
        if not decision.outcome_mapping or not decision.arb_compatibility:
            return

        # Extract market ids from candidate_id (format: "mkt_a_id:mkt_b_id")
        # Engine sets this; fall back to parsing
        parts = decision.candidate_id.split(":", 1)
        if len(parts) != 2:
            return
        id_a, id_b = parts[0], parts[1]

        self._nodes.add(id_a)
        self._nodes.add(id_b)
        self._adj[id_a].add(id_b)
        self._adj[id_b].add(id_a)

        edge_key = (id_a, id_b)
        self._edges[edge_key] = {
            "relationship_type": decision.relationship_type,
            "confidence": decision.confidence,
            "arb_structure": (
                decision.arb_compatibility.arb_structure
                if decision.arb_compatibility
                else None
            ),
            "legs": (
                decision.arb_compatibility.legs
                if decision.arb_compatibility
                else []
            ),
        }

    def get_event_clusters(self) -> list[set[str]]:
        """Return connected components (event clusters) as sets of market_ids."""
        visited: set[str] = set()
        clusters: list[set[str]] = []

        for node in self._nodes:
            if node not in visited:
                cluster: set[str] = set()
                self._bfs(node, visited, cluster)
                clusters.append(cluster)

        return clusters

    def _bfs(self, start: str, visited: set[str], cluster: set[str]) -> None:
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            cluster.add(node)
            queue.extend(self._adj[node] - visited)

    def get_arb_baskets(self) -> list[dict[str, object]]:
        """
        Return groups of market pairs ready for Phase 4.
        Each basket contains market ids and leg metadata.
        """
        baskets: list[dict[str, object]] = []
        for (id_a, id_b), meta in self._edges.items():
            if meta.get("legs"):
                baskets.append({
                    "market_id_a": id_a,
                    "market_id_b": id_b,
                    "relationship_type": meta["relationship_type"],
                    "arb_structure": meta["arb_structure"],
                    "confidence": meta["confidence"],
                    "legs": meta["legs"],
                })
        return baskets

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)
