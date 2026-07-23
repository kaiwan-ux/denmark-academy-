from uuid import UUID

from fastapi import Header, HTTPException


class RequestUser:
    def __init__(self, user_id: UUID | None, role: str) -> None:
        self.user_id = user_id
        self.role = role


def current_user(
    x_user_id: str | None = Header(default=None),
    x_user_role: str = Header(default="student"),
) -> RequestUser:
    parsed_user_id = UUID(x_user_id) if x_user_id else None
    return RequestUser(user_id=parsed_user_id, role=x_user_role)


def require_admin(user: RequestUser) -> None:
    if user.role not in {"admin", "reviewer"}:
        raise HTTPException(status_code=403, detail="Admin access required")
