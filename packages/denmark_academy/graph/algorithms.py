from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relationship_type: str
    weight: float = 1.0


class GraphAlgorithmEngine:
    def shortest_path(self, edges: list[GraphEdge], start: str, goal: str) -> list[str]:
        adjacency = self._adjacency(edges)
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            node, path = queue.popleft()
            if node == goal:
                return path
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, [*path, neighbor]))
        return []

    def prerequisites(self, edges: list[GraphEdge], concept: str) -> list[str]:
        reverse = defaultdict(list)
        for edge in edges:
            if edge.relationship_type in {'CONCEPT_RELATED_TO_CONCEPT', 'PREREQUISITE_FOR'}:
                reverse[edge.target].append(edge.source)
        return self._walk(reverse, concept)

    def downstream_mistake_causes(self, edges: list[GraphEdge], weak_scores: dict[str, float]) -> list[dict[str, Any]]:
        adjacency = self._adjacency(edges)
        scored = []
        for concept, weakness in weak_scores.items():
            downstream = self._walk(adjacency, concept)
            impact = weakness * max(1, len(downstream))
            scored.append({'concept': concept, 'downstream_count': len(downstream), 'impact_score': round(impact, 2)})
        return sorted(scored, key=lambda item: item['impact_score'], reverse=True)

    def centrality(self, edges: list[GraphEdge]) -> dict[str, float]:
        degree = defaultdict(float)
        for edge in edges:
            degree[edge.source] += edge.weight
            degree[edge.target] += edge.weight
        if not degree:
            return {}
        max_degree = max(degree.values()) or 1
        return {node: round(value / max_degree * 100, 2) for node, value in degree.items()}

    def communities(self, edges: list[GraphEdge]) -> list[list[str]]:
        adjacency = self._adjacency(edges)
        visited = set()
        groups = []
        for node in adjacency:
            if node in visited:
                continue
            group = self._walk(adjacency, node, include_start=True)
            visited.update(group)
            groups.append(group)
        return groups

    def concept_similarity(self, left_neighbors: set[str], right_neighbors: set[str]) -> float:
        if not left_neighbors and not right_neighbors:
            return 0
        return round(len(left_neighbors & right_neighbors) / len(left_neighbors | right_neighbors) * 100, 2)

    def learning_sequence(self, concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(concepts, key=lambda c: (c.get('mastery', 0), -c.get('importance', 0), c.get('difficulty_rank', 2)))

    def _adjacency(self, edges: list[GraphEdge]) -> dict[str, list[str]]:
        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            adjacency[edge.source].append(edge.target)
        return adjacency

    def _walk(self, adjacency: dict[str, list[str]], start: str, include_start: bool = False) -> list[str]:
        visited = set()
        output = [start] if include_start else []
        queue = deque([start])
        visited.add(start)
        while queue:
            node = queue.popleft()
            for neighbor in adjacency.get(node, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                output.append(neighbor)
                queue.append(neighbor)
        return output
