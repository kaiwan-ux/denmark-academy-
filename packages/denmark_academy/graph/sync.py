from uuid import UUID

from denmark_academy.graph.repository import GraphRepository
from denmark_academy.graph.schemas import GraphNodeUpsert, GraphRelationshipUpsert


class GraphSyncService:
    def __init__(self, repository: GraphRepository | None = None) -> None:
        self.repository = repository or GraphRepository()

    def sync_track(self, track: str) -> dict:
        with self.repository.connection() as conn:
            concepts = conn.execute(
                """
                SELECT c.*, et.slug AS track_slug FROM learning_concepts c
                JOIN exam_tracks et ON et.id = c.exam_track_id
                WHERE et.slug=%s
                """,
                (track,),
            ).fetchall()
            nodes = 0
            relationships = 0
            for concept in concepts:
                self.repository.upsert_node(conn, GraphNodeUpsert(graph_scope='knowledge', node_type='Concept', stable_key=f"concept:{concept['id']}", label=concept['name'], track=track, source_table='learning_concepts', source_id=concept['id'], properties={'slug': concept['slug'], 'description': concept['description']}))
                nodes += 1
                if concept['topic_id']:
                    topic_key = f"topic:{concept['topic_id']}"
                    self.repository.upsert_node(conn, GraphNodeUpsert(graph_scope='knowledge', node_type='Topic', stable_key=topic_key, label='Topic', track=track, source_table='course_topics', source_id=concept['topic_id']))
                    self.repository.upsert_relationship(conn, GraphRelationshipUpsert(graph_scope='knowledge', relationship_type='TOPIC_CONTAINS_CONCEPT', from_stable_key=topic_key, to_stable_key=f"concept:{concept['id']}"))
                    relationships += 1
                if concept['parent_concept_id']:
                    self.repository.upsert_relationship(conn, GraphRelationshipUpsert(graph_scope='knowledge', relationship_type='CONCEPT_RELATED_TO_CONCEPT', from_stable_key=f"concept:{concept['parent_concept_id']}", to_stable_key=f"concept:{concept['id']}", confidence=80))
                    relationships += 1
            links = conn.execute(
                """
                SELECT l.*, et.slug AS track_slug FROM question_concept_links l
                JOIN exam_tracks et ON et.id = l.exam_track_id
                WHERE et.slug=%s AND l.official_question_id IS NOT NULL
                """,
                (track,),
            ).fetchall()
            for link in links:
                q = conn.execute('SELECT * FROM official_questions WHERE id=%s', (link['official_question_id'],)).fetchone()
                if not q:
                    continue
                q_key = f"official_question:{q['id']}"
                c_key = f"concept:{link['concept_id']}"
                self.repository.upsert_node(conn, GraphNodeUpsert(graph_scope='knowledge', node_type='OfficialQuestion', stable_key=q_key, label=q['stem'][:120], track=track, source_table='official_questions', source_id=q['id'], properties={'question_number': q['question_number'], 'correct_choice': q['correct_choice']}))
                self.repository.upsert_relationship(conn, GraphRelationshipUpsert(graph_scope='knowledge', relationship_type='CONCEPT_TESTED_BY_QUESTION', from_stable_key=c_key, to_stable_key=q_key, weight=float(link['weight'])))
                nodes += 1
                relationships += 1
            conn.commit()
            return {'track': track, 'nodes_upserted': nodes, 'relationships_upserted': relationships}

    def sync_student(self, user_id: UUID, track: str) -> dict:
        with self.repository.connection() as conn:
            self.repository.upsert_node(conn, GraphNodeUpsert(graph_scope='student_learning', node_type='Student', stable_key=f'student:{user_id}', label=f'Student {user_id}', track=track, user_id=user_id, source_table='users', source_id=user_id))
            mastery = conn.execute(
                """
                SELECT m.*, c.name FROM student_concept_mastery m
                JOIN learning_concepts c ON c.id = m.concept_id
                JOIN exam_tracks et ON et.id = m.exam_track_id
                WHERE m.user_id=%s AND et.slug=%s
                """,
                (user_id, track),
            ).fetchall()
            rels = 0
            for row in mastery:
                concept_key = f"concept:{row['concept_id']}"
                student_key = f"student:{user_id}"
                rel_type = 'STUDENT_MASTERED_CONCEPT' if float(row['mastery_score']) >= 70 else 'STUDENT_WEAK_AT_CONCEPT'
                self.repository.upsert_relationship(conn, GraphRelationshipUpsert(graph_scope='cross_graph', relationship_type=rel_type, from_stable_key=student_key, to_stable_key=concept_key, weight=float(row['mastery_score']), confidence=float(row['confidence_score']), properties={'attempts': row['attempts']}))
                rels += 1
            conn.commit()
            return {'user_id': str(user_id), 'track': track, 'relationships_upserted': rels}
