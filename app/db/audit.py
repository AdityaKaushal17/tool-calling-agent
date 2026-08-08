from sqlalchemy.orm import Session

from app.db.models import AuditLog


def create_audit_entry(
    db: Session,
    *,
    task_id: str,
    user_id: int,
    action: str,
    input_json: dict,
    status: str = "started",
) -> AuditLog:
    entry = AuditLog(
        task_id=task_id,
        user_id=user_id,
        action=action,
        input_json=input_json,
        status=status,
    )
    db.add(entry)
    db.flush()
    return entry


def finalize_audit_entry(db: Session, entry: AuditLog, *, output_json: dict | None, status: str) -> AuditLog:
    entry.output_json = output_json
    entry.status = status
    db.add(entry)
    db.flush()
    return entry
