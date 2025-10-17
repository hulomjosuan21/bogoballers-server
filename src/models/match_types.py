import json
from typing import Dict, List, Literal, Optional, Union
from dataclasses import dataclass, asdict, field

@dataclass
class TwiceToBeatConfig:
    type: Literal["TwiceToBeat"] = "TwiceToBeat"
    advantaged_team: Optional[str] = None
    challenger_team: Optional[str] = None
    max_games: int = 2
    
@dataclass
class RoundRobinConfig:
    type: Literal["RoundRobin"] = "RoundRobin"
    group_count: int = 1
    advances_per_group: int = 1
    use_point_system: bool = False


@dataclass
class KnockoutConfig:
    type: Literal["Knockout"] = "Knockout"
    group_count: int = 1
    seeding: Literal["random", "ranking"] = "random"
    series_config: Optional[TwiceToBeatConfig] = None


@dataclass
class BestOfConfig:
    type: Literal["BestOf"] = "BestOf"
    group_count: int = 1
    games: int = 3
    advances_per_group: int = 1
    series_config: Optional[TwiceToBeatConfig] = None

@dataclass
class DoubleEliminationConfig:
    type: Literal["DoubleElimination"] = "DoubleElimination"
    group_count: int = 1
    max_loss: int = 2
    progress_group: int = 1
    max_progress_group: int = 6
    brackets: List[str] = field(default_factory=lambda: ["winners", "losers"])
    advances_per_group: int = 1
    
RoundConfig = Union[
    RoundRobinConfig,
    KnockoutConfig,
    DoubleEliminationConfig,
    BestOfConfig,
]

def infer_format_type(config: dict) -> str:
    if "max_loss" in config:
        return "DoubleElimination"
    if "games" in config:
        return "BestOf"
    if "seeding" in config:
        return "Knockout"
    return "RoundRobin"

def sanitize_config(config) -> dict:
    allowed_keys = {
        "type", "group_count", "advances_per_group",
        "use_point_system", "seeding", "max_loss", "brackets", "games",
        "advantaged_team", "challenger_team", "max_games", "progress_group", "max_progress_group"
    }
    return {k: v for k, v in config.items() if k in allowed_keys}

def parse_round_config(config: dict) -> RoundConfig:
    config = sanitize_config(config)
    format_type = config.get("type") or infer_format_type(config)

    series_config_raw = config.pop("series_config", None)
    series_config = None
    if isinstance(series_config_raw, dict):
        match series_config_raw.get("type"):
            case "TwiceToBeat":
                series_config = TwiceToBeatConfig(**series_config_raw)

    match format_type:
        case "RoundRobin":
            return RoundRobinConfig(**config)
        case "Knockout":
            return KnockoutConfig(**config, series_config=series_config)
        case "DoubleElimination":
            return DoubleEliminationConfig(**config)
        case "BestOf":
            return BestOfConfig(**config, series_config=series_config)
        case _:
            raise ValueError(f"Unknown format type: {format_type}")


