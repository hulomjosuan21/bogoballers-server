from typing import Dict, List, Literal, Optional, Union
from dataclasses import dataclass, asdict

# -------------------------------
# 🟩 Round-Level Configs
# -------------------------------

@dataclass
class RoundRobinConfig:
    type: Literal["RoundRobin"] = "RoundRobin"
    groups: int = 1
    games_per_team: int = 1
    advances_per_group: int = 1

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class KnockoutConfig:
    type: Literal["Knockout"] = "Knockout"
    single_elim: bool = True
    seeding: Literal["random", "ranking"] = "random"
    advances: int = 1
    total_matches: Optional[int] = None

@dataclass
class BestOfConfig:
    type: Literal["BestOf"] = "BestOf"
    games: int = 3
    advances: int = 1
    total_games: Optional[int] = None

@dataclass
class DoubleEliminationConfig:
    type: Literal["DoubleElimination"] = "DoubleElimination"
    max_loss: int = 2
    brackets: Optional[List[str]] = None
    advances: int = 1
    total_matches: Optional[int] = None

    def __post_init__(self):
        if self.brackets is None:
            self.brackets = ["winners", "losers"]
@dataclass
class TwiceToBeatConfig:
    type: Literal["TwiceToBeat"] = "TwiceToBeat"
    advantaged_team: Optional[str] = None
    challenger_team: Optional[str] = None
    max_games: int = 2

    def to_dict(self) -> Dict:
        return asdict(self)

RoundConfig = Union[
    RoundRobinConfig,
    KnockoutConfig,
    BestOfConfig,
    DoubleEliminationConfig,
    TwiceToBeatConfig,
]

# -------------------------------
# 🟦 Match-Level Configs
# -------------------------------

@dataclass
class MatchBestOfConfig:
    type: Literal["BestOf"] = "BestOf"
    best_of: int = 3
    current_game: int = 1
    series_id: Optional[str] = None
    wins_required: int = 2
    home_advantage: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class MatchKnockoutConfig:
    type: Literal["Knockout"] = "Knockout"
    elimination_match: bool = True
    winner_advances_to: Optional[str] = None
    loser_eliminated: bool = True

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class MatchDoubleElimConfig:
    bracket_side: Literal["winners", "losers"]  # ← non-default, must come first
    loss_count: int = 0
    max_loss: int = 2
    series_id: Optional[str] = None
    type: Literal["DoubleElimination"] = "DoubleElimination"  # ← default, move to end

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class MatchTwiceToBeatConfig:
    type: Literal["TwiceToBeat"] = "TwiceToBeat"
    advantaged_team: Optional[str] = None
    challenger_team: Optional[str] = None
    game_number: int = 1
    series_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

MatchConfig = Union[
    MatchBestOfConfig,
    MatchKnockoutConfig,
    MatchDoubleElimConfig,
    MatchTwiceToBeatConfig,
]
