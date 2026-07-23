from uuid import UUID

from denmark_academy.lms.repository import Phase2Repository
from denmark_academy.phase2_schemas import ChapterCreate, CourseCreate, LearningUnitCreate, TopicCreate


class CourseSeeder:
    def __init__(self, repository: Phase2Repository | None = None) -> None:
        self.repository = repository or Phase2Repository()

    def seed_from_learning_chunks(self, track: str, publish: bool = False) -> dict:
        status = "published" if publish else "draft"
        with self.repository.connection() as conn:
            course = self.repository.create_course(
                conn,
                CourseCreate(
                    track=track,
                    title="Permanent Residence Course" if track == "pr" else "Danish Citizenship Course",
                    description="Structured course generated from official learning material chunks.",
                    status=status,
                ),
            )
            chunks = conn.execute(
                """
                SELECT dc.*, sd.exam_track_id
                FROM document_chunks dc
                JOIN source_documents sd ON sd.id = dc.source_document_id
                JOIN exam_tracks et ON et.id = sd.exam_track_id
                WHERE et.slug = %s AND sd.source_type = 'learning_material'
                ORDER BY dc.source_document_id, dc.chunk_index
                """,
                (track,),
            ).fetchall()
            chapter_by_title: dict[str, UUID] = {}
            topic_count = 0
            unit_count = 0
            for chunk in chunks:
                chapter_title = chunk["section_title"] or f"Section {len(chapter_by_title) + 1}"
                if chapter_title not in chapter_by_title:
                    chapter = self.repository.create_chapter(
                        conn,
                        ChapterCreate(
                            course_id=course["id"],
                            title=chapter_title[:180],
                            slug=_slugify(chapter_title, len(chapter_by_title) + 1),
                            sort_order=len(chapter_by_title) + 1,
                            status=status,
                        ),
                    )
                    chapter_by_title[chapter_title] = chapter["id"]
                    topic = self.repository.create_topic(
                        conn,
                        TopicCreate(
                            chapter_id=chapter["id"],
                            title="Official material",
                            slug="official-material",
                            sort_order=1,
                            status=status,
                        ),
                    )
                    topic_count += 1
                else:
                    chapter = conn.execute(
                        "SELECT * FROM course_chapters WHERE id = %s", (chapter_by_title[chapter_title],)
                    ).fetchone()
                    topic = conn.execute(
                        "SELECT * FROM course_topics WHERE chapter_id = %s ORDER BY sort_order LIMIT 1",
                        (chapter["id"],),
                    ).fetchone()
                self.repository.create_learning_unit(
                    conn,
                    LearningUnitCreate(
                        course_id=course["id"],
                        chapter_id=chapter["id"],
                        topic_id=topic["id"],
                        source_document_id=chunk["source_document_id"],
                        document_chunk_id=chunk["id"],
                        title=f"Pages {chunk['page_start']}-{chunk['page_end']}",
                        body=chunk["text"],
                        estimated_minutes=max(1, round((chunk["token_count"] or 250) / 180)),
                        sort_order=chunk["chunk_index"] + 1,
                        status=status,
                        metadata={"page_start": chunk["page_start"], "page_end": chunk["page_end"]},
                    ),
                )
                unit_count += 1
            conn.commit()
            return {
                "course_id": str(course["id"]),
                "chapters": len(chapter_by_title),
                "topics": topic_count,
                "learning_units": unit_count,
                "status": status,
            }


def _slugify(value: str, fallback_number: int) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum():
            allowed.append(char)
        elif char in {" ", "-", "_"}:
            allowed.append("-")
    slug = "".join(allowed).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:80] or f"section-{fallback_number}"
