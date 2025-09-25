from typing import List, Optional
from src.models.match_types import TwiceToBeatConfig, parse_round_config
from src.models.league import LeagueCategoryRoundModel
from src.models.match import LeagueMatchModel


class LeagueFinalizationEngine:
    def __init__(self, final_round: LeagueCategoryRoundModel, matches: List[LeagueMatchModel]):
        self.final_round = final_round
        self.matches = matches
        self.config = parse_round_config(final_round.format_config)

    def get_final_standings(self) -> dict:
        standings = {}

        if isinstance(self.config, TwiceToBeatConfig):
            finals = [m for m in self.matches if m.is_final and m.winner_team_id]
            challenger_wins = sum(1 for m in finals if m.winner_team_id == self.config.challenger_team)

            if challenger_wins >= 2:
                standings["champion"] = self.config.challenger_team
                standings["runner_up"] = self.config.advantaged_team
            else:
                standings["champion"] = self.config.advantaged_team
                standings["runner_up"] = self.config.challenger_team

        else:
            final_match = next((m for m in self.matches if m.is_final), None)
            if final_match and final_match.home_team_id and final_match.away_team_id:
                winner, loser = self._evaluate_match(final_match)
                if winner and loser:
                    standings["champion"] = winner
                    standings["runner_up"] = loser

        # ✅ Third place match
        third_match = next((m for m in self.matches if getattr(m, "is_third_place", False)), None)
        if third_match:
            third_winner, _ = self._evaluate_match(third_match)
            if third_winner:
                standings["third_place"] = third_winner

        return standings

    def _evaluate_match(self, match: LeagueMatchModel) -> tuple[Optional[str], Optional[str]]:
        if match.home_team_score is not None and match.away_team_score is not None:
            if match.home_team_score > match.away_team_score:
                return match.home_team_id, match.away_team_id
            elif match.away_team_score > match.home_team_score:
                return match.away_team_id, match.home_team_id
            else:
                return None, None
        elif match.winner_team_id and match.loser_team_id:
            return match.winner_team_id, match.loser_team_id
        return None, None