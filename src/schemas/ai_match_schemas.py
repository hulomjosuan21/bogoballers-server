from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class MatchGenerationAction(BaseModel):
    home_team_id: Optional[str] = Field(None, description="ID of the home team. Null if bracket placeholder.")
    away_team_id: Optional[str] = Field(None, description="ID of the away team. Null if bracket placeholder.")
    match_label: str = Field(..., description="Label for the match (e.g., 'Game 1', 'Upper Bracket Round 1')")
    is_placeholder: bool = Field(False, description="True if specific teams aren't known yet (e.g. 'Winner of A vs B')")
    placeholder_label: Optional[str] = Field(None, description="Description of the slot (e.g., 'Winner of Match 1')")
    depends_on_match_ids: List[str] = Field(default=[], description="List of previous match IDs this match depends on.")

class TeamUpdateAction(BaseModel):
    team_id: str
    action: Literal["eliminate", "advance", "champion", "runner_up", "third_place"]
    rank: Optional[int] = None
    reason: Optional[str] = Field(None, description="Why this action was taken (e.g., 'Lost twice in double elim')")

class CommissionerDecision(BaseModel):
    explanation: str = Field(..., description="Reasoning based on format rules (Round Robin/Double Elim/Twice-to-Beat).")
    create_matches: List[MatchGenerationAction] = Field(default=[])
    update_teams: List[TeamUpdateAction] = Field(default=[])
    round_status_update: Optional[Literal["Ongoing", "Finished"]] = None
    next_round_ready: bool = Field(default=False, description="If True, the system should prepare the next round.")