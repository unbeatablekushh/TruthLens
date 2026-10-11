from sqlalchemy.orm import Session
from app.models.auth import AuditLog
from typing import Optional
from uuid import UUID

def log_audit_event(
    db: Session,
    event_type: str,
    user_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """Log an audit event to the database without sensitive data."""
    audit_entry = AuditLog(
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry
