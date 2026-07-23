from pathlib import Path

from denmark_academy.domain import (
    IngestionManifest,
    PaperPairManifest,
    SourceDocumentManifest,
    SourceType,
    TRACKS,
)
from denmark_academy.ingestion.hashing import file_sha256


def build_ingestion_manifest(root_path: Path, parser_version: str) -> IngestionManifest:
    root_path = root_path.resolve()
    warnings: list[str] = []
    learning_materials: list[SourceDocumentManifest] = []
    paper_pairs: list[PaperPairManifest] = []

    for track_slug, track in TRACKS.items():
        track_root = root_path / track_slug.value
        if not track_root.exists():
            warnings.append(f"Missing track directory: {track_root}")
            continue

        learning_dir = track_root / track.learning_material_dir_name
        if learning_dir.exists():
            for pdf in sorted(learning_dir.glob("*.pdf"), key=lambda item: item.name.lower()):
                learning_materials.append(
                    _source_manifest(track_slug, SourceType.LEARNING_MATERIAL, pdf, root_path, parser_version)
                )
        else:
            warnings.append(f"Missing learning material directory: {learning_dir}")

        question_dir = _first_existing(track_root, track.question_dir_names)
        answer_dir = track_root / track.answer_dir_name
        if question_dir is None:
            warnings.append(f"Missing question directory for track: {track_slug.value}")
            continue
        if not answer_dir.exists():
            warnings.append(f"Missing answer directory for track: {track_slug.value}")

        answer_by_stem = {
            answer.stem: answer for answer in sorted(answer_dir.glob("*.pdf"), key=lambda item: item.name.lower())
        }
        for question_pdf in sorted(question_dir.glob("*.pdf"), key=_pdf_sort_key):
            answer_pdf = answer_by_stem.get(question_pdf.stem)
            pair_warnings = []
            if answer_pdf is None:
                pair_warnings.append(f"Missing answer key for {question_pdf.relative_to(root_path)}")

            question_manifest = _source_manifest(
                track_slug,
                SourceType.QUESTION_PAPER,
                question_pdf,
                root_path,
                parser_version,
                paired_source_path=str(answer_pdf.relative_to(root_path)) if answer_pdf else None,
            )
            answer_manifest = (
                _source_manifest(
                    track_slug,
                    SourceType.ANSWER_KEY,
                    answer_pdf,
                    root_path,
                    parser_version,
                    paired_source_path=str(question_pdf.relative_to(root_path)),
                )
                if answer_pdf
                else None
            )
            paper_pairs.append(
                PaperPairManifest(
                    track=track_slug,
                    paper_code=question_pdf.stem,
                    question_pdf=question_manifest,
                    answer_pdf=answer_manifest,
                    validation_warnings=pair_warnings,
                )
            )

    return IngestionManifest(
        root_path=str(root_path),
        parser_version=parser_version,
        learning_materials=learning_materials,
        paper_pairs=paper_pairs,
        warnings=warnings,
    )


def _first_existing(track_root: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = track_root / name
        if candidate.exists():
            return candidate
    return None


def _source_manifest(
    track_slug,
    source_type: SourceType,
    path: Path,
    root_path: Path,
    parser_version: str,
    paired_source_path: str | None = None,
) -> SourceDocumentManifest:
    stat = path.stat()
    return SourceDocumentManifest(
        track=track_slug,
        source_type=source_type,
        source_path=str(path.relative_to(root_path)),
        original_filename=path.name,
        content_sha256=file_sha256(path),
        file_size_bytes=stat.st_size,
        parser_version=parser_version,
        paired_source_path=paired_source_path,
    )


def _pdf_sort_key(path: Path) -> tuple[int, str]:
    try:
        return (int(path.stem), path.name)
    except ValueError:
        return (10_000, path.name)

