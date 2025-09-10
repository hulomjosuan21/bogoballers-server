from typing import Dict

from src.models.match_types import MatchConfig, MatchBestOfConfig, MatchKnockoutConfig, TwiceToBeatConfig, MatchDoubleElimConfig

def parse_match_config(data: Dict) -> MatchConfig:
    match_type = data.get("type")
    if match_type == "BestOf":
        return MatchBestOfConfig(**data)
    elif match_type == "Knockout":
        return MatchKnockoutConfig(**data)
    elif match_type == "DoubleElimination":
        return MatchDoubleElimConfig(**data)
    elif match_type == "TwiceToBeat":
        return TwiceToBeatConfig(**data)
    raise ValueError(f"Unknown match config type: {match_type}")

class MatchGenerationEngine:
    ...