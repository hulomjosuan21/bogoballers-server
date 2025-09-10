from typing import Dict, List, Literal, Optional, Union
from dataclasses import dataclass, asdict

# note: Round-level Configs
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

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class BestOfConfig:
    type: Literal["BestOf"] = "BestOf"
    games: int = 3
    advances: int = 1

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class DoubleEliminationConfig:
    type: Literal["DoubleElimination"] = "DoubleElimination"
    max_loss: int = 2
    brackets: List[str] = None
    advances: int = 1

    def __post_init__(self):
        if self.brackets is None:
            self.brackets = ["winners", "losers"]

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class MatchDoubleElimConfig:
    bracket_side: Literal["winners", "losers"]
    type: Literal["DoubleElimination"] = "DoubleElimination"
    loss_count: int = 0
    max_loss: int = 2
    series_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

RoundConfig = Union[
    RoundRobinConfig,
    KnockoutConfig,
    BestOfConfig,
    DoubleEliminationConfig,
]

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
class TwiceToBeatConfig:
    type: Literal["TwiceToBeat"] = "TwiceToBeat"
    advantaged_team: Optional[str] = None
    challenger_team: Optional[str] = None
    max_games: int = 2

    def to_dict(self) -> Dict:
        return asdict(self)

MatchConfig = Union[
    MatchBestOfConfig,
    MatchKnockoutConfig,
    MatchDoubleElimConfig,
    TwiceToBeatConfig,
]