from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, field_validator

from denmark_academy.config import get_settings
from denmark_academy.current_affairs.service import CurrentAffairsService

router = APIRouter(prefix="/api/v1", tags=["account"])
settings = get_settings()

MODULES = {
    "reading_material",
    "knowledge_mcqs",
    "ai_generated_mcqs",
    "chapter_practice",
    "past_papers",
    "current_affairs",
    "danish_values",
    "practice_questions",
    "ai_chat",
    "notes",
    "mock_exam",
}
RESUMABLE_MODULES = MODULES - {"mock_exam"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=1024)
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class SignupRequest(Credentials):
    display_name: str = Field(min_length=2, max_length=100)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.strip().split())


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=100)
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=1000)
    preferred_track: Literal["pr", "citizenship"] | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=100)


class LearningStateRequest(BaseModel):
    state_key: str = Field(default="default", min_length=1, max_length=160)
    route: str = Field(min_length=1, max_length=1000)
    entity_id: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=300)
    completion_percent: float = Field(default=0, ge=0, le=100)
    state: dict[str, Any] = Field(default_factory=dict)
    completed: bool = False


class AttemptRequest(BaseModel):
    module: str
    question_id: str = Field(min_length=1, max_length=500)
    session_key: str | None = Field(default=None, max_length=500)
    selected_choice: str | None = Field(default=None, max_length=100)
    correct_choice: str | None = Field(default=None, max_length=100)
    is_correct: bool
    topic: str | None = Field(default=None, max_length=300)
    track: str | None = Field(default=None, max_length=100)
    time_spent_seconds: int = Field(default=0, ge=0, le=86400)
    client_attempt_id: str | None = Field(default=None, max_length=300)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BookmarkRequest(BaseModel):
    module: str
    entity_id: str = Field(min_length=1, max_length=500)
    title: str | None = Field(default=None, max_length=300)
    route: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NoteRequest(BaseModel):
    module: str
    entity_id: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=100000)
    route: str | None = Field(default=None, max_length=1000)
    anchor: dict[str, Any] = Field(default_factory=dict)




class ChapterCompleteRequest(BaseModel):
    track: Literal["pr", "citizenship"]
    chapter_key: str = Field(min_length=1, max_length=500)
    chapter_title: str = Field(min_length=1, max_length=500)
    page_number: int = Field(ge=1)
    total_chapters: int = Field(gt=0, le=1000)
    route: str = Field(default="/reader/demo", min_length=1, max_length=1000)
class ActivityRequest(BaseModel):
    module: str
    activity_type: str = Field(min_length=1, max_length=100)
    duration_seconds: int = Field(default=0, ge=0, le=86400)
    route: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompletedMockRequest(BaseModel):
    track: str = Field(min_length=1, max_length=100)
    score: int = Field(ge=0)
    total_questions: int = Field(gt=0, le=500)
    correct_answers: int = Field(default=0, ge=0)
    incorrect_answers: int = Field(default=0, ge=0)
    duration_seconds: int = Field(default=0, ge=0, le=86400)
    answers: list[dict[str, Any]] = Field(default_factory=list)
    insights: dict[str, Any] = Field(default_factory=dict)


def db():
    return psycopg.connect(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout_seconds,
        row_factory=dict_row,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return "$".join([
        "scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P),
        base64.urlsafe_b64encode(salt).decode().rstrip("="),
        base64.urlsafe_b64encode(digest).decode().rstrip("="),
    ])


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        hashlib.scrypt(password.encode("utf-8"), salt=b"denmark-academy", n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
        return False
    try:
        kind, n, r, p, salt, expected = encoded.split("$")
        if kind != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64decode(salt),
            n=int(n), r=int(r), p=int(p), dklen=len(_b64decode(expected)),
        )
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "display_name": row.get("display_name") or row["email"].split("@")[0],
        "first_name": row.get("first_name"),
        "last_name": row.get("last_name"),
        "avatar_url": row.get("avatar_url"),
        "preferred_track": row.get("preferred_track"),
        "timezone": row.get("timezone") or "Europe/Copenhagen",
        "role": row["role"],
        "created_at": row["created_at"],
        "last_login_at": row.get("last_login_at"),
    }


def validate_module(module: str, *, resumable: bool = False) -> str:
    module = module.strip().lower()
    valid = RESUMABLE_MODULES if resumable else MODULES
    if module not in valid:
        raise HTTPException(status_code=400, detail="Unknown learning module")
    return module


def create_session(conn, user_id: UUID, remember_me: bool, request: Request) -> tuple[str, datetime]:
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + (timedelta(days=30) if remember_me else timedelta(hours=24))
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    candidate_ip = forwarded or (request.client.host if request.client else None)
    try:
        ip_address = str(ipaddress.ip_address(candidate_ip)) if candidate_ip else None
    except ValueError:
        ip_address = None
    conn.execute(
        """
        INSERT INTO auth_sessions(user_id, token_hash, remember_me, user_agent, ip_address, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (user_id, token_hash(raw), remember_me, request.headers.get("user-agent", "")[:1000], ip_address, expires_at),
    )
    return raw, expires_at


def current_account(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    raw = authorization.split(" ", 1)[1].strip()
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    with db() as conn:
        row = conn.execute(
            """
            SELECT u.*, s.id AS session_id, s.expires_at AS session_expires_at
            FROM auth_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > now()
            """,
            (token_hash(raw),),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")
        conn.execute("UPDATE auth_sessions SET last_seen_at=now() WHERE id=%s", (row["session_id"],))
        conn.commit()
    return row


@router.post("/auth/signup", status_code=201)
def signup(payload: SignupRequest, request: Request, background_tasks: BackgroundTasks) -> dict[str, Any]:
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE email=%s", (payload.email,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        row = conn.execute(
            """
            INSERT INTO users(email, password_hash, role, display_name)
            VALUES (%s, %s, 'student', %s)
            RETURNING *
            """,
            (payload.email, hash_password(payload.password), payload.display_name),
        ).fetchone()
        raw, expires_at = create_session(conn, row["id"], payload.remember_me, request)
        conn.execute(
            "INSERT INTO account_security_events(user_id, event_type) VALUES (%s, 'account.created')",
            (row["id"],),
        )
        conn.commit()
    background_tasks.add_task(CurrentAffairsService().ensure_priority_pool)
    return {"user": public_user(row), "session_token": raw, "expires_at": expires_at}


@router.post("/auth/login")
def login(payload: Credentials, request: Request, background_tasks: BackgroundTasks) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=%s", (payload.email,)).fetchone()
        now = datetime.now(timezone.utc)
        if row and row.get("locked_until") and row["locked_until"] > now:
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")
        verified = verify_password(payload.password, row.get("password_hash") if row else None)
        if not row or not verified:
            if row:
                failures = int(row.get("failed_login_count") or 0) + 1
                locked = now + timedelta(minutes=15) if failures >= 5 else None
                conn.execute(
                    "UPDATE users SET failed_login_count=%s, locked_until=%s WHERE id=%s",
                    (failures, locked, row["id"]),
                )
                conn.commit()
            raise HTTPException(status_code=401, detail="Invalid email or password")
        conn.execute(
            "UPDATE users SET failed_login_count=0, locked_until=NULL, last_login_at=now(), updated_at=now() WHERE id=%s",
            (row["id"],),
        )
        raw, expires_at = create_session(conn, row["id"], payload.remember_me, request)
        row["last_login_at"] = now
        conn.commit()
    background_tasks.add_task(CurrentAffairsService().ensure_priority_pool)
    return {"user": public_user(row), "session_token": raw, "expires_at": expires_at}


@router.get("/auth/me")
def me(user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    return {"user": public_user(user)}


@router.post("/auth/logout", status_code=204)
def logout(user: dict[str, Any] = Depends(current_account)) -> None:
    with db() as conn:
        conn.execute("UPDATE auth_sessions SET revoked_at=now() WHERE id=%s", (user["session_id"],))
        conn.commit()


@router.post("/auth/change-password")
def change_password(payload: ChangePasswordRequest, user: dict[str, Any] = Depends(current_account)) -> dict[str, str]:
    with db() as conn:
        account = conn.execute(
            "SELECT password_hash FROM users WHERE id=%s FOR UPDATE",
            (user["id"],),
        ).fetchone()
        if not account or not verify_password(payload.current_password, account.get("password_hash")):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if hmac.compare_digest(payload.current_password, payload.new_password):
            raise HTTPException(status_code=400, detail="New password must be different from the current password")
        conn.execute(
            "UPDATE users SET password_hash=%s, failed_login_count=0, locked_until=NULL, updated_at=now() WHERE id=%s",
            (hash_password(payload.new_password), user["id"]),
        )
        conn.execute(
            "UPDATE auth_sessions SET revoked_at=now() WHERE user_id=%s AND id<>%s AND revoked_at IS NULL",
            (user["id"], user["session_id"]),
        )
        conn.execute(
            "INSERT INTO account_security_events(user_id, event_type) VALUES (%s, 'password.changed')",
            (user["id"],),
        )
        conn.commit()
    return {"message": "Password updated successfully"}

@router.patch("/profile")
def update_profile(payload: ProfileUpdateRequest, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    if not values:
        return {"user": public_user(user)}
    clean: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip() or None
        clean[key] = value
    assignments = ", ".join(f"{key}=%s" for key in clean)
    with db() as conn:
        row = conn.execute(
            f"UPDATE users SET {assignments}, updated_at=now() WHERE id=%s RETURNING *",
            (*clean.values(), user["id"]),
        ).fetchone()
        conn.commit()
    return {"user": public_user(row)}


@router.get("/progress/states")
def list_states(user: dict[str, Any] = Depends(current_account)) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM user_learning_states WHERE user_id=%s ORDER BY last_activity_at DESC",
            (user["id"],),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/progress/states/{module}")
def get_state(module: str, state_key: str = "default", user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    module = validate_module(module, resumable=True)
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM user_learning_states WHERE user_id=%s AND module=%s AND state_key=%s",
            (user["id"], module, state_key),
        ).fetchone()
    return {"state": dict(row) if row else None}


@router.put("/progress/states/{module}")
def save_state(module: str, payload: LearningStateRequest, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    module = validate_module(module, resumable=True)
    completed_at = datetime.now(timezone.utc) if payload.completed or payload.completion_percent >= 100 else None
    with db() as conn:
        row = conn.execute(
            """
            INSERT INTO user_learning_states(
              user_id,module,state_key,route,entity_id,title,completion_percent,state,completed_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(user_id,module,state_key) DO UPDATE SET
              route=excluded.route, entity_id=excluded.entity_id, title=excluded.title,
              completion_percent=excluded.completion_percent, state=excluded.state,
              last_activity_at=now(), completed_at=excluded.completed_at
            RETURNING *
            """,
            (user["id"], module, payload.state_key, payload.route, payload.entity_id, payload.title, payload.completion_percent, Jsonb(payload.state), completed_at),
        ).fetchone()
        conn.commit()
    return dict(row)


@router.post("/progress/attempts", status_code=201)
def save_attempt(payload: AttemptRequest, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    module = validate_module(payload.module)
    with db() as conn:
        if payload.client_attempt_id:
            existing = conn.execute(
                "SELECT * FROM user_question_attempts WHERE user_id=%s AND client_attempt_id=%s",
                (user["id"], payload.client_attempt_id),
            ).fetchone()
            if existing:
                return dict(existing)
        row = conn.execute(
            """
            INSERT INTO user_question_attempts(
              user_id,module,question_id,session_key,selected_choice,correct_choice,is_correct,
              topic,track,time_spent_seconds,metadata,client_attempt_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """,
            (user["id"], module, payload.question_id, payload.session_key, payload.selected_choice, payload.correct_choice, payload.is_correct, payload.topic, payload.track, payload.time_spent_seconds, Jsonb(payload.metadata), payload.client_attempt_id),
        ).fetchone()
        conn.execute(
            "INSERT INTO user_activity_log(user_id,module,activity_type,duration_seconds,metadata) VALUES (%s,%s,'question_answered',%s,%s)",
            (user["id"], module, payload.time_spent_seconds, Jsonb({"question_id": payload.question_id, "correct": payload.is_correct})),
        )
        conn.commit()
    return dict(row)


@router.get("/progress/attempts/seen")
def seen_questions(module: str, track: str | None = None, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    module = validate_module(module)
    with db() as conn:
        if track is None:
            rows = conn.execute(
                "SELECT DISTINCT question_id FROM user_question_attempts WHERE user_id=%s AND module=%s",
                (user["id"], module),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT question_id FROM user_question_attempts WHERE user_id=%s AND module=%s AND track=%s",
                (user["id"], module, track),
            ).fetchall()
    return {"question_ids": [row["question_id"] for row in rows]}


@router.delete("/progress/attempts/seen", status_code=204)
def clear_seen_questions(module: str, track: str | None = None, user: dict[str, Any] = Depends(current_account)) -> None:
    module = validate_module(module)
    with db() as conn:
        if track is None:
            conn.execute("DELETE FROM user_question_attempts WHERE user_id=%s AND module=%s", (user["id"], module))
        else:
            conn.execute("DELETE FROM user_question_attempts WHERE user_id=%s AND module=%s AND track=%s", (user["id"], module, track))
        conn.commit()

@router.post("/progress/activity", status_code=201)
def activity(payload: ActivityRequest, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    module = validate_module(payload.module)
    with db() as conn:
        row = conn.execute(
            """
            INSERT INTO user_activity_log(user_id,module,activity_type,duration_seconds,route,metadata)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING *
            """,
            (user["id"], module, payload.activity_type, payload.duration_seconds, payload.route, Jsonb(payload.metadata)),
        ).fetchone()
        conn.commit()
    return dict(row)


@router.get("/progress/bookmarks")
def list_bookmarks(user: dict[str, Any] = Depends(current_account)) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM saved_bookmarks WHERE user_id=%s ORDER BY created_at DESC", (user["id"],)).fetchall()
    return [dict(row) for row in rows]


@router.post("/progress/bookmarks")
def save_bookmark(payload: BookmarkRequest, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    module = validate_module(payload.module)
    with db() as conn:
        row = conn.execute(
            """
            INSERT INTO saved_bookmarks(user_id,module,entity_id,title,route,metadata)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT(user_id,module,entity_id) DO UPDATE SET title=excluded.title, route=excluded.route, metadata=excluded.metadata
            RETURNING *
            """,
            (user["id"], module, payload.entity_id, payload.title, payload.route, Jsonb(payload.metadata)),
        ).fetchone()
        conn.commit()
    return dict(row)


@router.delete("/progress/bookmarks/{bookmark_id}", status_code=204)
def delete_bookmark(bookmark_id: UUID, user: dict[str, Any] = Depends(current_account)) -> None:
    with db() as conn:
        conn.execute("DELETE FROM saved_bookmarks WHERE id=%s AND user_id=%s", (bookmark_id, user["id"]))
        conn.commit()


@router.get("/progress/notes")
def list_notes(user: dict[str, Any] = Depends(current_account)) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM saved_notes WHERE user_id=%s ORDER BY updated_at DESC", (user["id"],)).fetchall()
    return [dict(row) for row in rows]


@router.post("/progress/notes")
def save_note(payload: NoteRequest, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    module = validate_module(payload.module)
    with db() as conn:
        row = conn.execute(
            """
            INSERT INTO saved_notes(user_id,module,entity_id,body,route,anchor)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT(user_id,module,entity_id) DO UPDATE SET
              body=excluded.body, route=excluded.route, anchor=excluded.anchor, updated_at=now()
            RETURNING *
            """,
            (user["id"], module, payload.entity_id, payload.body, payload.route, Jsonb(payload.anchor)),
        ).fetchone()
        conn.commit()
    return dict(row)


@router.delete("/progress/notes/entity/{module}/{entity_id}", status_code=204)
def delete_note_by_entity(module: str, entity_id: str, user: dict[str, Any] = Depends(current_account)) -> None:
    module = validate_module(module)
    with db() as conn:
        conn.execute(
            "DELETE FROM saved_notes WHERE user_id=%s AND module=%s AND entity_id=%s",
            (user["id"], module, entity_id),
        )
        conn.commit()

@router.delete("/progress/notes/{note_id}", status_code=204)
def delete_note(note_id: UUID, user: dict[str, Any] = Depends(current_account)) -> None:
    with db() as conn:
        conn.execute("DELETE FROM saved_notes WHERE id=%s AND user_id=%s", (note_id, user["id"]))
        conn.commit()


@router.post("/progress/mock-exams/completed", status_code=201)
def save_completed_mock(payload: CompletedMockRequest, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            """
            INSERT INTO completed_mock_exams(
              user_id,track,score,total_questions,correct_answers,incorrect_answers,duration_seconds,answers,insights
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """,
            (user["id"], payload.track, payload.score, payload.total_questions, payload.correct_answers, payload.incorrect_answers, payload.duration_seconds, Jsonb(payload.answers), Jsonb(payload.insights)),
        ).fetchone()
        conn.execute(
            "INSERT INTO user_activity_log(user_id,module,activity_type,duration_seconds,route,metadata) VALUES (%s,'mock_exam','mock_completed',%s,'/exam-simulator',%s)",
            (user["id"], payload.duration_seconds, Jsonb({"score": payload.score, "total": payload.total_questions, "track": payload.track})),
        )
        conn.commit()
    return dict(row)


@router.get("/progress/mock-exams")
def completed_mocks(user: dict[str, Any] = Depends(current_account)) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM completed_mock_exams WHERE user_id=%s ORDER BY completed_at DESC",
            (user["id"],),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/progress/chapters")
def completed_chapters(track: str | None = None, user: dict[str, Any] = Depends(current_account)) -> list[dict[str, Any]]:
    with db() as conn:
        if track:
            rows = conn.execute(
                "SELECT * FROM completed_reading_chapters WHERE user_id=%s AND track=%s ORDER BY completed_at",
                (user["id"], track),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM completed_reading_chapters WHERE user_id=%s ORDER BY completed_at",
                (user["id"],),
            ).fetchall()
    return [dict(row) for row in rows]


@router.post("/progress/chapters/complete")
def complete_chapter(payload: ChapterCompleteRequest, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            """
            INSERT INTO completed_reading_chapters(
              user_id,track,chapter_key,chapter_title,page_number,total_chapters,route
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(user_id,track,chapter_key) DO UPDATE SET
              chapter_title=excluded.chapter_title, page_number=excluded.page_number,
              total_chapters=excluded.total_chapters, route=excluded.route
            RETURNING *
            """,
            (user["id"], payload.track, payload.chapter_key, payload.chapter_title, payload.page_number, payload.total_chapters, payload.route),
        ).fetchone()
        count = conn.execute(
            "SELECT COUNT(*)::int AS count FROM completed_reading_chapters WHERE user_id=%s AND track=%s",
            (user["id"], payload.track),
        ).fetchone()["count"]
        conn.execute(
            "INSERT INTO user_activity_log(user_id,module,activity_type,route,metadata) VALUES (%s,'reading_material','chapter_completed',%s,%s)",
            (user["id"], payload.route, Jsonb({"track": payload.track, "chapter_key": payload.chapter_key, "title": payload.chapter_title})),
        )
        conn.commit()
    return {
        "chapter": dict(row),
        "completed_items": count,
        "total_items": payload.total_chapters,
        "completion_percent": round(min(count, payload.total_chapters) / payload.total_chapters * 100, 1),
    }


@router.get("/progress/continue")
def continue_learning(user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM user_learning_states
            WHERE user_id=%s AND module<>'mock_exam' AND completion_percent<100
            ORDER BY module, state_key, last_activity_at DESC
            """,
            (user["id"],),
        ).fetchall()
    items = [dict(row) for row in rows]
    return {"items": items, "item": items[0] if items else None}


@router.get("/progress/summary")
def progress_summary(user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    with db() as conn:
        totals = conn.execute(
            """
            SELECT COUNT(*)::int attempted,
                   COUNT(*) FILTER (WHERE is_correct)::int correct,
                   COUNT(*) FILTER (WHERE NOT is_correct)::int incorrect,
                   COALESCE(SUM(time_spent_seconds),0)::int attempt_seconds
            FROM user_question_attempts WHERE user_id=%s
            """,
            (user["id"],),
        ).fetchone()
        attempts = conn.execute(
            """
            SELECT module, COALESCE(track,'all') track,
                   COUNT(*)::int attempted,
                   COUNT(DISTINCT question_id)::int unique_attempted,
                   COUNT(*) FILTER (WHERE is_correct)::int correct
            FROM user_question_attempts WHERE user_id=%s
            GROUP BY module, COALESCE(track,'all')
            """,
            (user["id"],),
        ).fetchall()
        states = conn.execute(
            "SELECT * FROM user_learning_states WHERE user_id=%s ORDER BY last_activity_at DESC",
            (user["id"],),
        ).fetchall()
        reading = conn.execute(
            """
            SELECT track, COUNT(*)::int completed, MAX(total_chapters)::int total
            FROM completed_reading_chapters WHERE user_id=%s GROUP BY track
            """,
            (user["id"],),
        ).fetchall()
        mocks = conn.execute(
            """
            SELECT track, COUNT(*)::int completed,
                   COALESCE(SUM(correct_answers),0)::int correct,
                   COALESCE(SUM(total_questions),0)::int attempted
            FROM completed_mock_exams WHERE user_id=%s GROUP BY track
            """,
            (user["id"],),
        ).fetchall()
        counts = conn.execute(
            "SELECT (SELECT COUNT(*)::int FROM saved_notes WHERE user_id=%s) notes",
            (user["id"],),
        ).fetchone()
        activity_seconds = conn.execute(
            "SELECT COALESCE(SUM(duration_seconds),0)::int total FROM user_activity_log WHERE user_id=%s",
            (user["id"],),
        ).fetchone()["total"]
        active_days = conn.execute(
            """
            SELECT DISTINCT occurred_at::date AS activity_date FROM user_activity_log WHERE user_id=%s
            UNION SELECT DISTINCT attempted_at::date AS activity_date FROM user_question_attempts WHERE user_id=%s
            ORDER BY activity_date DESC
            """,
            (user["id"], user["id"]),
        ).fetchall()

    attempt_map: dict[tuple[str, str], dict[str, Any]] = {
        (row["module"], row["track"]): dict(row) for row in attempts
    }
    modules: list[dict[str, Any]] = []
    used_attempt_keys: set[tuple[str, str]] = set()

    for row in states:
        module = row["module"]
        state_key = row["state_key"]
        data = row["state"] or {}
        if module in {"ai_chat", "notes"}:
            continue
        if module == "current_affairs":
            matching = [item for (name, _), item in attempt_map.items() if name == module]
            attempted = sum(item["attempted"] for item in matching)
            unique_attempted = sum(item["unique_attempted"] for item in matching)
            correct = sum(item["correct"] for item in matching)
            used_attempt_keys.update(key for key in attempt_map if key[0] == module)
        else:
            stats = attempt_map.get((module, state_key), {"attempted": 0, "unique_attempted": 0, "correct": 0})
            attempted = stats["attempted"]
            unique_attempted = stats["unique_attempted"]
            correct = stats["correct"]
            used_attempt_keys.add((module, state_key))
        completed_items = int(data.get("completed_items", unique_attempted) or 0)
        total_items = int(data.get("total_items", 0) or 0)
        completion = round(min(completed_items, total_items) / total_items * 100, 1) if total_items else float(row["completion_percent"] or 0)
        if attempted == 0 and completed_items == 0 and total_items == 0:
            continue
        modules.append({
            "module": module,
            "state_key": state_key,
            "title": row["title"],
            "route": row["route"],
            "attempted": attempted,
            "completed_items": completed_items,
            "total_items": total_items,
            "correct": correct,
            "incorrect": max(attempted - correct, 0),
            "accuracy": round(correct / attempted * 100, 1) if attempted else 0.0,
            "completion": completion,
        })

    state_keys = {(item["module"], item["state_key"]) for item in modules}
    for row in reading:
        key = ("reading_material", row["track"])
        metric = next((item for item in modules if (item["module"], item["state_key"]) == key), None)
        completion = round(row["completed"] / row["total"] * 100, 1) if row["total"] else 0
        if metric:
            metric.update({"completed_items": row["completed"], "total_items": row["total"], "completion": completion})
        else:
            modules.append({
                "module": "reading_material", "state_key": row["track"],
                "title": ("Citizenship" if row["track"] == "citizenship" else "Permanent Residence") + " reading",
                "route": "/reader/demo", "attempted": 0, "completed_items": row["completed"],
                "total_items": row["total"], "correct": 0, "incorrect": 0, "accuracy": 0.0, "completion": completion,
            })
        state_keys.add(key)

    for key, row in attempt_map.items():
        if key in used_attempt_keys or key in state_keys:
            continue
        modules.append({
            "module": row["module"], "state_key": row["track"], "title": None,
            "route": "/", "attempted": row["attempted"], "completed_items": row["unique_attempted"],
            "total_items": 0, "correct": row["correct"], "incorrect": row["attempted"] - row["correct"],
            "accuracy": round(row["correct"] / row["attempted"] * 100, 1) if row["attempted"] else 0.0,
            "completion": 0.0,
        })

    for row in mocks:
        if row["completed"] <= 0:
            continue
        modules.append({
            "module": "mock_exam", "state_key": row["track"],
            "title": ("Citizenship" if row["track"] == "citizenship" else "Permanent Residence") + " mock exams",
            "route": "/exam-simulator", "attempted": row["attempted"], "completed_items": row["completed"],
            "total_items": row["completed"], "correct": row["correct"],
            "incorrect": max(row["attempted"] - row["correct"], 0),
            "accuracy": round(row["correct"] / row["attempted"] * 100, 1) if row["attempted"] else 0.0,
            "completion": 100.0,
        })

    streak = 0
    expected = datetime.now(timezone.utc).date()
    days = {row["activity_date"] for row in active_days}
    if expected not in days:
        expected -= timedelta(days=1)
    while expected in days:
        streak += 1
        expected -= timedelta(days=1)

    completed_chapter_count = sum(row["completed"] for row in reading)
    measurable = [item for item in modules if item["total_items"] > 0 and item["module"] != "mock_exam"]
    total_completed = sum(min(item["completed_items"], item["total_items"]) for item in measurable)
    total_available = sum(item["total_items"] for item in measurable)
    overall = round(total_completed / total_available * 100, 1) if total_available else 0.0

    return {
        "totals": {
            "attempted": totals["attempted"],
            "correct": totals["correct"],
            "incorrect": totals["incorrect"],
            "accuracy": round(totals["correct"] / totals["attempted"] * 100, 1) if totals["attempted"] else 0.0,
            "study_streak": streak,
            "study_time_seconds": int(activity_seconds) + int(totals["attempt_seconds"]),
            "completed_chapters": completed_chapter_count,
            "overall_completion": overall,
            "notes": counts["notes"],
            "completed_mock_exams": sum(row["completed"] for row in mocks),
        },
        "modules": modules,
    }


