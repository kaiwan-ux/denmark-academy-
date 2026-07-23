from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from denmark_academy.config import get_settings
from denmark_academy.graph.algorithms import GraphEdge
from denmark_academy.graph.schemas import GraphExploreRequest, GraphNodeUpsert, GraphRelationshipUpsert


class GraphRepository:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.database_url = self.settings.database_url

    def connection(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=self.settings.database_connect_timeout_seconds,
        )

    def track_id(self, conn, track: str | None) -> UUID | None:
        if not track:
            return None
        row = conn.execute('SELECT id FROM exam_tracks WHERE slug=%s', (track,)).fetchone()
        if not row:
            raise ValueError(f'Unknown exam track: {track}')
        return row['id']

    def upsert_node(self, conn, payload: GraphNodeUpsert) -> dict:
        row = conn.execute(
            """
            INSERT INTO graph_nodes (graph_scope, node_type, source_table, source_id, exam_track_id, user_id, stable_key, label, properties)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (stable_key)
            DO UPDATE SET label=EXCLUDED.label, properties=graph_nodes.properties || EXCLUDED.properties, updated_at=now()
            RETURNING *
            """,
            (payload.graph_scope, payload.node_type, payload.source_table, payload.source_id, self.track_id(conn, payload.track), payload.user_id, payload.stable_key, payload.label, Jsonb(payload.properties)),
        ).fetchone()
        return dict(row)

    def upsert_relationship(self, conn, payload: GraphRelationshipUpsert) -> dict:
        from_node = conn.execute('SELECT id FROM graph_nodes WHERE stable_key=%s', (payload.from_stable_key,)).fetchone()
        to_node = conn.execute('SELECT id FROM graph_nodes WHERE stable_key=%s', (payload.to_stable_key,)).fetchone()
        if not from_node or not to_node:
            raise ValueError('Both graph nodes must exist before creating relationship')
        row = conn.execute(
            """
            INSERT INTO graph_relationships (graph_scope, relationship_type, from_node_id, to_node_id, weight, confidence, properties)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (relationship_type, from_node_id, to_node_id)
            DO UPDATE SET weight=EXCLUDED.weight, confidence=EXCLUDED.confidence, properties=graph_relationships.properties || EXCLUDED.properties
            RETURNING *
            """,
            (payload.graph_scope, payload.relationship_type, from_node['id'], to_node['id'], payload.weight, payload.confidence, Jsonb(payload.properties)),
        ).fetchone()
        return dict(row)

    def explore(self, conn, request: GraphExploreRequest) -> dict[str, list[dict]]:
        clauses = []
        params: list[Any] = []
        if request.track:
            clauses.append('n.exam_track_id = %s')
            params.append(self.track_id(conn, request.track))
        if request.user_id:
            clauses.append('(n.user_id = %s OR n.user_id IS NULL)')
            params.append(request.user_id)
        if request.query:
            clauses.append('(n.label ILIKE %s OR n.stable_key ILIKE %s)')
            params.extend([f'%{request.query}%', f'%{request.query}%'])
        if request.node_types:
            clauses.append('n.node_type = ANY(%s)')
            params.append(request.node_types)
        if request.root_stable_key:
            clauses.append('(n.stable_key = %s OR EXISTS (SELECT 1 FROM graph_relationships r JOIN graph_nodes root ON root.id = r.from_node_id WHERE root.stable_key = %s AND r.to_node_id = n.id))')
            params.extend([request.root_stable_key, request.root_stable_key])
        where = 'WHERE ' + ' AND '.join(clauses) if clauses else ''
        nodes = [dict(row) for row in conn.execute(f'SELECT n.* FROM graph_nodes n {where} ORDER BY n.created_at DESC LIMIT %s', [*params, request.limit]).fetchall()]
        node_ids = [node['id'] for node in nodes]
        if not node_ids:
            return {'nodes': [], 'relationships': []}
        rel_clauses = ['(from_node_id = ANY(%s) OR to_node_id = ANY(%s))']
        rel_params: list[Any] = [node_ids, node_ids]
        if request.relationship_types:
            rel_clauses.append('relationship_type = ANY(%s)')
            rel_params.append(request.relationship_types)
        rels = [dict(row) for row in conn.execute(f"SELECT * FROM graph_relationships WHERE {' AND '.join(rel_clauses)} LIMIT %s", [*rel_params, request.limit * 2]).fetchall()]
        return {'nodes': nodes, 'relationships': rels}

    def edges(self, conn, track: str | None = None, user_id: UUID | None = None) -> list[GraphEdge]:
        clauses = []
        params: list[Any] = []
        if track:
            clauses.append('(a.exam_track_id = %s OR a.exam_track_id IS NULL)')
            params.append(self.track_id(conn, track))
        if user_id:
            clauses.append('(a.user_id = %s OR a.user_id IS NULL)')
            params.append(user_id)
        where = 'WHERE ' + ' AND '.join(clauses) if clauses else ''
        rows = conn.execute(
            f"""
            SELECT a.stable_key AS source, b.stable_key AS target, r.relationship_type, r.weight
            FROM graph_relationships r
            JOIN graph_nodes a ON a.id = r.from_node_id
            JOIN graph_nodes b ON b.id = r.to_node_id
            {where}
            """,
            params,
        ).fetchall()
        return [GraphEdge(row['source'], row['target'], row['relationship_type'], float(row['weight'])) for row in rows]

    def node_detail(self, conn, stable_key: str, user_id: UUID | None = None) -> dict:
        node = conn.execute('SELECT * FROM graph_nodes WHERE stable_key=%s', (stable_key,)).fetchone()
        if not node:
            raise ValueError('Graph node not found')
        rels = [dict(row) for row in conn.execute('SELECT * FROM graph_relationships WHERE from_node_id=%s OR to_node_id=%s', (node['id'], node['id'])).fetchall()]
        related = [dict(row) for row in conn.execute(
            """
            SELECT n.* FROM graph_nodes n
            JOIN graph_relationships r ON r.to_node_id = n.id OR r.from_node_id = n.id
            WHERE (r.from_node_id=%s OR r.to_node_id=%s) AND n.node_type='Concept' AND n.id <> %s
            LIMIT 10
            """,
            (node['id'], node['id'], node['id']),
        ).fetchall()]
        return {'node': dict(node), 'relationships': rels, 'related_concepts': related, 'recommended_next_concept': related[0] if related else None}
