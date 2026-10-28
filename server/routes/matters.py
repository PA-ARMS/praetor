"""
Matters API - Matter-centric organization (industry standard: ABA, law firm practice management)
CRUD for matters, conflict check, time entries, and docket/calendar.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta

from server.models import get_db, Matter, TimeEntry, DocketEntry, User
from server.middleware.auth_middleware import require_auth, require_role
from server.utils.logger import setup_logger

router = APIRouter(prefix="/api/matters", tags=["matters"])
logger = setup_logger("matters")


# --- Pydantic schemas ---

class MatterCreate(BaseModel):
    matter_number: str
    display_name: str
    client_name: Optional[str] = None
    jurisdiction: Optional[str] = "Virginia"
    party_names: Optional[str] = None  # Comma-separated or JSON array string
    notes: Optional[str] = None


class MatterUpdate(BaseModel):
    display_name: Optional[str] = None
    client_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    status: Optional[str] = None  # open, closed, pending
    party_names: Optional[str] = None
    notes: Optional[str] = None


class MatterOut(BaseModel):
    id: int
    matter_number: str
    display_name: str
    client_name: Optional[str]
    jurisdiction: Optional[str]
    status: str
    party_names: Optional[str]
    notes: Optional[str]
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ConflictCheckRequest(BaseModel):
    client_name: Optional[str] = None
    party_names: Optional[str] = None  # Comma-separated


class ConflictCheckResult(BaseModel):
    has_conflict: bool
    conflicts: List[dict]  # [{ matter_number, display_name, reason }]


class TimeEntryCreate(BaseModel):
    matter_id: int
    entry_date: date
    duration_minutes: int
    activity_type: str  # research, drafting, review, hearing, conference, other
    description: Optional[str] = None
    billable: bool = True


class TimeEntryOut(BaseModel):
    id: int
    matter_id: int
    user_id: int
    entry_date: datetime
    duration_minutes: int
    activity_type: str
    description: Optional[str]
    billable: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DocketEntryCreate(BaseModel):
    matter_id: int
    deadline_type: str  # filing, hearing, statute_of_limitations, other
    due_date: datetime
    description: Optional[str] = None
    reminder_days: Optional[int] = None


class DocketEntryUpdate(BaseModel):
    completed: Optional[bool] = None
    description: Optional[str] = None


class DocketEntryOut(BaseModel):
    id: int
    matter_id: int
    deadline_type: str
    due_date: datetime
    description: Optional[str]
    reminder_days: Optional[int]
    completed: bool
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


def _normalize_parties(party_names: Optional[str]) -> List[str]:
    """Parse party names from comma-separated or JSON string into list of normalized strings."""
    if not party_names or not party_names.strip():
        return []
    s = party_names.strip()
    if s.startswith("["):
        try:
            import json
            out = json.loads(s)
            return [str(p).strip().lower() for p in out if p]
        except Exception:
            pass
    return [p.strip().lower() for p in s.split(",") if p.strip()]


def _matter_to_out(m: Matter) -> dict:
    return MatterOut(
        id=m.id,
        matter_number=m.matter_number,
        display_name=m.display_name,
        client_name=m.client_name,
        jurisdiction=m.jurisdiction,
        status=m.status,
        party_names=m.party_names,
        notes=m.notes,
        opened_at=m.opened_at,
        closed_at=m.closed_at,
        created_at=m.created_at,
    ).model_dump()


# --- Conflict check (industry standard before opening a matter) ---

@router.post("/conflict-check", response_model=ConflictCheckResult)
async def conflict_check(
    body: ConflictCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "attorney", "attorney_partner")),
):
    """
    Check for potential conflicts before opening a new matter.
    Compares client and party names against existing open matters.
    """
    conflicts = []
    client = (body.client_name or "").strip().lower()
    new_parties = _normalize_parties(body.party_names)

    matters = db.query(Matter).filter(Matter.status == "open").all()
    for m in matters:
        if client and m.client_name and m.client_name.strip().lower() == client:
            conflicts.append({
                "matter_number": m.matter_number,
                "display_name": m.display_name,
                "reason": "Same client name",
            })
            continue
        existing_parties = _normalize_parties(m.party_names)
        for np in new_parties:
            for ep in existing_parties:
                if np in ep or ep in np or np == ep:
                    conflicts.append({
                        "matter_number": m.matter_number,
                        "display_name": m.display_name,
                        "reason": f"Overlapping party: {np}",
                    })
                    break

    return ConflictCheckResult(
        has_conflict=len(conflicts) > 0,
        conflicts=conflicts,
    )


# --- Matter CRUD ---

@router.get("", response_model=List[dict])
async def list_matters(
    status: Optional[str] = Query(None, description="Filter: open, closed, pending"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """List matters with optional status filter."""
    q = db.query(Matter).order_by(Matter.created_at.desc())
    if status:
        q = q.filter(Matter.status == status)
    matters = q.all()
    return [_matter_to_out(m) for m in matters]


@router.post("", response_model=dict)
async def create_matter(
    body: MatterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "attorney", "attorney_partner")),
):
    """Create a new matter. Consider running conflict-check first."""
    if db.query(Matter).filter(Matter.matter_number == body.matter_number).first():
        raise HTTPException(status_code=400, detail="Matter number already exists")
    matter = Matter(
        matter_number=body.matter_number,
        display_name=body.display_name,
        client_name=body.client_name,
        jurisdiction=body.jurisdiction or "Virginia",
        status="open",
        party_names=body.party_names,
        notes=body.notes,
    )
    db.add(matter)
    db.commit()
    db.refresh(matter)
    return _matter_to_out(matter)


@router.get("/calendar/upcoming", response_model=List[dict])
async def upcoming_deadlines(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """List all upcoming docket deadlines across matters (next N days)."""
    now = datetime.utcnow()
    end = now + timedelta(days=days)
    entries = (
        db.query(DocketEntry, Matter)
        .join(Matter, DocketEntry.matter_id == Matter.id)
        .filter(DocketEntry.completed == False, DocketEntry.due_date >= now, DocketEntry.due_date <= end)
        .order_by(DocketEntry.due_date)
        .all()
    )
    return [
        {
            "id": e.id,
            "matter_id": e.matter_id,
            "matter_number": m.matter_number,
            "display_name": m.display_name,
            "deadline_type": e.deadline_type,
            "due_date": e.due_date.isoformat() if e.due_date else None,
            "description": e.description,
        }
        for e, m in entries
    ]


@router.get("/{matter_id}", response_model=dict)
async def get_matter(
    matter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Get a single matter by ID."""
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    return _matter_to_out(matter)


@router.patch("/{matter_id}", response_model=dict)
async def update_matter(
    matter_id: int,
    body: MatterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "attorney", "attorney_partner")),
):
    """Update matter. If status set to closed, closed_at is set."""
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    if body.display_name is not None:
        matter.display_name = body.display_name
    if body.client_name is not None:
        matter.client_name = body.client_name
    if body.jurisdiction is not None:
        matter.jurisdiction = body.jurisdiction
    if body.status is not None:
        matter.status = body.status
        if body.status == "closed" and not matter.closed_at:
            matter.closed_at = datetime.utcnow()
        elif body.status != "closed":
            matter.closed_at = None
    if body.party_names is not None:
        matter.party_names = body.party_names
    if body.notes is not None:
        matter.notes = body.notes
    db.commit()
    db.refresh(matter)
    return _matter_to_out(matter)


# --- Time entries ---

@router.get("/{matter_id}/time-entries", response_model=List[dict])
async def list_time_entries(
    matter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """List time entries for a matter."""
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    entries = db.query(TimeEntry).filter(TimeEntry.matter_id == matter_id).order_by(TimeEntry.entry_date.desc()).all()
    return [
        {
            "id": e.id,
            "matter_id": e.matter_id,
            "user_id": e.user_id,
            "entry_date": e.entry_date.isoformat() if e.entry_date else None,
            "duration_minutes": e.duration_minutes,
            "activity_type": e.activity_type,
            "description": e.description,
            "billable": e.billable,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


@router.post("/{matter_id}/time-entries", response_model=dict)
async def create_time_entry(
    matter_id: int,
    body: TimeEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Add a time entry to a matter."""
    if body.matter_id != matter_id:
        raise HTTPException(status_code=400, detail="matter_id mismatch")
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    entry = TimeEntry(
        matter_id=matter_id,
        user_id=current_user.id,
        entry_date=datetime.combine(body.entry_date, datetime.min.time()),
        duration_minutes=body.duration_minutes,
        activity_type=body.activity_type,
        description=body.description,
        billable=body.billable,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "matter_id": entry.matter_id,
        "user_id": entry.user_id,
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
        "duration_minutes": entry.duration_minutes,
        "activity_type": entry.activity_type,
        "description": entry.description,
        "billable": entry.billable,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


# --- Docket / calendar ---

@router.get("/{matter_id}/docket", response_model=List[dict])
async def list_docket(
    matter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """List docket entries (deadlines) for a matter."""
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    entries = db.query(DocketEntry).filter(DocketEntry.matter_id == matter_id).order_by(DocketEntry.due_date).all()
    return [
        {
            "id": e.id,
            "matter_id": e.matter_id,
            "deadline_type": e.deadline_type,
            "due_date": e.due_date.isoformat() if e.due_date else None,
            "description": e.description,
            "reminder_days": e.reminder_days,
            "completed": e.completed,
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


@router.post("/{matter_id}/docket", response_model=dict)
async def create_docket_entry(
    matter_id: int,
    body: DocketEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "attorney", "attorney_partner", "paralegal")),
):
    """Add a docket deadline to a matter."""
    if body.matter_id != matter_id:
        raise HTTPException(status_code=400, detail="matter_id mismatch")
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    entry = DocketEntry(
        matter_id=matter_id,
        deadline_type=body.deadline_type,
        due_date=body.due_date,
        description=body.description,
        reminder_days=body.reminder_days,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "matter_id": entry.matter_id,
        "deadline_type": entry.deadline_type,
        "due_date": entry.due_date.isoformat() if entry.due_date else None,
        "description": entry.description,
        "reminder_days": entry.reminder_days,
        "completed": entry.completed,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@router.patch("/docket/{docket_id}", response_model=dict)
async def update_docket_entry(
    docket_id: int,
    body: DocketEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Mark docket entry completed or update description."""
    entry = db.query(DocketEntry).filter(DocketEntry.id == docket_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Docket entry not found")
    if body.completed is not None:
        entry.completed = body.completed
        entry.completed_at = datetime.utcnow() if body.completed else None
    if body.description is not None:
        entry.description = body.description
    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "matter_id": entry.matter_id,
        "deadline_type": entry.deadline_type,
        "due_date": entry.due_date.isoformat() if entry.due_date else None,
        "description": entry.description,
        "completed": entry.completed,
        "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
    }
