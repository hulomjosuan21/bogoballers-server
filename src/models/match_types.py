from typing import Dict, List, Literal, Optional, Union
from dataclasses import dataclass, asdict

@dataclass
class RoundRobinConfig:
    type: Literal["RoundRobin"] = "RoundRobin"
    group_count: int = 1
    team_count: int = 0
    advances_per_group: int = 1
    regeneration_count: int = 0
    use_point_system: bool = False

@dataclass
class KnockoutConfig:
    type: Literal["Knockout"] = "Knockout"
    group_count: int = 1
    team_count: int = 0
    seeding: Literal["random", "ranking"] = "random"
    regeneration_count: int = 0

@dataclass
class DoubleEliminationConfig:
    type: Literal["DoubleElimination"] = "DoubleElimination"
    group_count: int = 1
    team_count: int = 0
    max_loss: int = 2
    brackets: List[str] = None
    regeneration_count: int = 0

    def __post_init__(self):
        if self.brackets is None:
            self.brackets = ["winners", "losers"]

@dataclass
class BestOfConfig:
    type: Literal["BestOf"] = "BestOf"
    group_count: int = 1
    team_count: int = 0
    games: int = 3
    regeneration_count: int = 0

@dataclass
class TwiceToBeatConfig:
    type: Literal["TwiceToBeat"] = "TwiceToBeat"
    team_count: int = 2
    advantaged_team: Optional[str] = None
    challenger_team: Optional[str] = None
    max_games: int = 2

RoundConfig = Union[
    RoundRobinConfig,
    KnockoutConfig,
    DoubleEliminationConfig,
    BestOfConfig,
    TwiceToBeatConfig,
]

def infer_format_type(config: dict) -> str:
    if "advantaged_team" in config and "challenger_team" in config:
        return "TwiceToBeat"
    if "max_loss" in config:
        return "DoubleElimination"
    if "games" in config:
        return "BestOf"
    if "seeding" in config:
        return "Knockout"
    return "RoundRobin"

def sanitize_config(config: dict) -> dict:
    allowed_keys = {
        "type", "group_count", "team_count", "advances_per_group", "regeneration_count",
        "use_point_system", "seeding", "max_loss", "brackets", "games",
        "advantaged_team", "challenger_team", "max_games"
    }
    return {k: v for k, v in config.items() if k in allowed_keys}

def parse_round_config(config: dict) -> RoundConfig:
    config = sanitize_config(config)
    format_type = config.get("type") or infer_format_type(config)

    match format_type:
        case "RoundRobin":
            return RoundRobinConfig(**config)
        case "Knockout":
            return KnockoutConfig(**config)
        case "DoubleElimination":
            return DoubleEliminationConfig(**config)
        case "BestOf":
            return BestOfConfig(**config)
        case "TwiceToBeat":
            return TwiceToBeatConfig(**config)
        case _:
            raise ValueError(f"Unknown format type: {format_type}")
