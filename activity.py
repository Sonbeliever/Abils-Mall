from extensions import db
from models import ActivityLog


def log_activity(actor_id, action, detail="", company_id=None):
    log = ActivityLog(
        actor_id=actor_id,
        company_id=company_id,
        action=action,
        detail=detail
    )
    db.session.add(log)
    db.session.commit()
    return log
