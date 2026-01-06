"""Forecast workflow session management.

Manages the state of a multi-step fuel forecast workflow, tracking:
- Current step and step statuses
- Pending (uncommitted) driver changes
- Base scenario for roll-forward
- Forecast period configuration
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from enum import Enum


class StepStatus(Enum):
    """Status of a workflow step."""
    PENDING = "pending"      # Not started
    ACTIVE = "active"        # Currently viewing
    DONE = "done"            # Completed
    CHANGED = "changed"      # Has changes to review


# Step configuration - 8 steps for the fuel forecast workflow
STEP_CONFIG = {
    1: {"label": "Start Point", "short": "START"},
    2: {"label": "Coal Position", "short": "INVENTORY"},
    3: {"label": "Coal Contracts", "short": "CONTRACTS"},  # NEW - contract pricing
    4: {"label": "Use Factors", "short": "USE"},
    5: {"label": "Heat Rates", "short": "HEAT"},
    6: {"label": "Generation", "short": "GEN"},
    7: {"label": "Other Costs", "short": "OTHER"},
    8: {"label": "Review & Save", "short": "REVIEW"},
}

TOTAL_STEPS = 8


@dataclass
class StepInfo:
    """Information about a single workflow step."""
    number: int
    label: str
    short_label: str
    status: StepStatus
    is_current: bool = False
    is_clickable: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "number": self.number,
            "label": self.label,
            "short_label": self.short_label,
            "status": self.status.value,
            "is_current": self.is_current,
            "is_clickable": self.is_clickable,
        }


@dataclass
class ForecastSession:
    """State for a fuel forecast workflow session.
    
    Tracks the user's progress through the 5-step workflow,
    including any uncommitted changes to driver values.
    """
    
    session_id: str
    created_at: datetime
    
    # Workflow configuration
    start_mode: str = "roll_forward"  # roll_forward, copy, fresh
    base_scenario_id: Optional[int] = None
    base_scenario_name: Optional[str] = None
    
    # Forecast period
    as_of_date: Optional[date] = None
    forecast_through: Optional[date] = None
    
    # Step tracking
    current_step: int = 1
    step_status: Dict[int, str] = field(default_factory=lambda: {
        1: StepStatus.PENDING.value,
        2: StepStatus.PENDING.value,
        3: StepStatus.PENDING.value,
        4: StepStatus.PENDING.value,
        5: StepStatus.PENDING.value,
        6: StepStatus.PENDING.value,
        7: StepStatus.PENDING.value,
        8: StepStatus.PENDING.value,
    })
    
    # Pending changes (uncommitted driver values)
    pending_changes: Dict[str, Any] = field(default_factory=dict)
    
    # Tracking what sections user chose to keep vs update
    keep_prior: Dict[str, bool] = field(default_factory=dict)
    
    # Notes accumulated through workflow
    change_notes: List[str] = field(default_factory=list)
    
    def get_steps(self) -> List[StepInfo]:
        """Get step information for navigation rendering."""
        steps = []
        for i in range(1, TOTAL_STEPS + 1):
            config = STEP_CONFIG[i]
            status_str = self.step_status.get(i, StepStatus.PENDING.value)
            status = StepStatus(status_str)
            
            # Override status if this is the current step
            is_current = (i == self.current_step)
            if is_current:
                status = StepStatus.ACTIVE
            
            # Determine if step is clickable
            # Can click if: already done, or is the next available step
            is_clickable = (
                status in (StepStatus.DONE, StepStatus.CHANGED) or
                i <= self.current_step
            )
            
            steps.append(StepInfo(
                number=i,
                label=config["label"],
                short_label=config["short"],
                status=status,
                is_current=is_current,
                is_clickable=is_clickable,
            ))
        
        return steps
    
    def mark_step_done(self, step: int) -> None:
        """Mark a step as completed."""
        if 1 <= step <= TOTAL_STEPS:
            self.step_status[step] = StepStatus.DONE.value
    
    def mark_step_changed(self, step: int) -> None:
        """Mark a step as having changes to review."""
        if 1 <= step <= TOTAL_STEPS:
            self.step_status[step] = StepStatus.CHANGED.value
    
    def advance_to_step(self, step: int) -> None:
        """Move to a specific step."""
        if 1 <= step <= TOTAL_STEPS:
            self.current_step = step
    
    def can_proceed_to_step(self, step: int) -> bool:
        """Check if user can navigate to a step."""
        if step == 1:
            return True
        # Can only go to step N if all previous steps are done
        for i in range(1, step):
            if self.step_status.get(i) == StepStatus.PENDING.value:
                return False
        return True
    
    def set_pending_change(self, driver_name: str, value: Any) -> None:
        """Store a pending driver value change."""
        self.pending_changes[driver_name] = value
    
    def get_pending_change(self, driver_name: str, default: Any = None) -> Any:
        """Get a pending driver value."""
        return self.pending_changes.get(driver_name, default)
    
    def set_keep_prior(self, section: str, keep: bool) -> None:
        """Record whether user chose to keep prior values for a section."""
        self.keep_prior[section] = keep
    
    def add_change_note(self, note: str) -> None:
        """Add a note about a change made."""
        self.change_notes.append(note)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "start_mode": self.start_mode,
            "base_scenario_id": self.base_scenario_id,
            "base_scenario_name": self.base_scenario_name,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            "forecast_through": self.forecast_through.isoformat() if self.forecast_through else None,
            "current_step": self.current_step,
            "step_status": self.step_status,
            "pending_changes": self.pending_changes,
            "keep_prior": self.keep_prior,
            "change_notes": self.change_notes,
        }


# =============================================================================
# Session Storage (In-Memory for MVP)
# =============================================================================

_sessions: Dict[str, ForecastSession] = {}


def create_session(
    start_mode: str = "roll_forward",
    base_scenario_id: Optional[int] = None,
    base_scenario_name: Optional[str] = None,
    as_of_date: Optional[date] = None,
    forecast_through: Optional[date] = None,
) -> ForecastSession:
    """Create a new forecast workflow session.
    
    Args:
        start_mode: How to initialize - roll_forward, copy, or fresh
        base_scenario_id: Source scenario for roll_forward or copy
        base_scenario_name: Name of source scenario
        as_of_date: As-of date for the forecast
        forecast_through: End date for forecast period
        
    Returns:
        New ForecastSession
    """
    session_id = str(uuid.uuid4())[:8]
    
    session = ForecastSession(
        session_id=session_id,
        created_at=datetime.utcnow(),
        start_mode=start_mode,
        base_scenario_id=base_scenario_id,
        base_scenario_name=base_scenario_name,
        as_of_date=as_of_date,
        forecast_through=forecast_through,
    )
    
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> Optional[ForecastSession]:
    """Retrieve a session by ID.
    
    Args:
        session_id: The session identifier
        
    Returns:
        ForecastSession if found, None otherwise
    """
    return _sessions.get(session_id)


def update_session(session: ForecastSession) -> None:
    """Update a session in storage.
    
    Args:
        session: The session to update
    """
    _sessions[session.session_id] = session


def delete_session(session_id: str) -> bool:
    """Delete a session.
    
    Args:
        session_id: The session to delete
        
    Returns:
        True if deleted, False if not found
    """
    if session_id in _sessions:
        del _sessions[session_id]
        return True
    return False


def list_sessions() -> List[ForecastSession]:
    """List all active sessions.
    
    Returns:
        List of all sessions
    """
    return list(_sessions.values())


def cleanup_old_sessions(max_age_hours: int = 24) -> int:
    """Remove sessions older than max_age_hours.
    
    Args:
        max_age_hours: Maximum session age in hours
        
    Returns:
        Number of sessions removed
    """
    now = datetime.utcnow()
    to_remove = []
    
    for session_id, session in _sessions.items():
        age = now - session.created_at
        if age.total_seconds() > max_age_hours * 3600:
            to_remove.append(session_id)
    
    for session_id in to_remove:
        del _sessions[session_id]
    
    return len(to_remove)

