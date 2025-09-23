

import random
from typing import List
from src.engines.match_generation_engine import MatchGenerationEngine
from src.models.league import LeagueCategoryRoundModel
from src.models.match import LeagueMatchModel
from src.models.match_types import parse_round_config
from src.models.team import LeagueTeamModel

import random
from datetime import datetime, timezone
from typing import List, Optional

from src.engines.match_generation_engine import MatchGenerationEngine
from src.models.league import LeagueCategoryRoundModel
from src.models.match import LeagueMatchModel
from src.models.match_types import parse_round_config
from src.models.team import LeagueTeamModel

class LeagueProgressionEngine:
    def __init__(
        self,
        league_id: str,
        current_round: LeagueCategoryRoundModel,
        next_round: LeagueCategoryRoundModel,
        matches: List[LeagueMatchModel],
        teams: List[LeagueTeamModel]
    ):
        self.league_id = league_id
        self.current_round = current_round
        self.next_round = next_round
        self.matches = matches
        self.teams = teams
        self.current_config = parse_round_config(current_round.format_config)
        self.next_config = parse_round_config(next_round.format_config)

    def evaluate_advancing_teams(self) -> List[LeagueTeamModel]:
        match self.current_config.type:
            case "RoundRobin":
                return self._rank_round_robin()
            case "Knockout":
                return self._winners_only()
            case "DoubleElimination":
                return self._survivors()
            case "BestOf" | "TwiceToBeat":
                return self._final_winner()
            case _:
                return []

    def generate_next_matches(self) -> List[LeagueMatchModel]:
        advancing = self.evaluate_advancing_teams()
        dependency_ids = self._get_dependency_match_ids(advancing)
        generator = MatchGenerationEngine(
            self.league_id,
            self.next_round,
            advancing,
            depends_on_match_ids=dependency_ids
        )
        return generator.generate()

    def finalize_progression_state(self):
        now = datetime.now(timezone.utc)

        advancing_ids = {t.league_team_id for t in self.evaluate_advancing_teams()}
        for team in self.teams:
            if team.league_team_id not in advancing_ids and not team.is_eliminated:
                team.is_eliminated = True
                team.finalized_at = now

        final_match = next((m for m in self.matches if m.is_final and m.winner_team_id), None)
        if final_match:
            for team in self.teams:
                if team.league_team_id == final_match.winner_team_id:
                    team.is_champion = True
                    team.final_rank = 1
                    team.finalized_at = now
                elif team.league_team_id == final_match.loser_team_id:
                    team.final_rank = 2
                    team.finalized_at = now

        third_place_match = next((m for m in self.matches if m.is_third_place and m.winner_team_id), None)
        if third_place_match:
            for team in self.teams:
                if team.league_team_id == third_place_match.winner_team_id:
                    team.final_rank = 3
                    team.finalized_at = now
                elif team.league_team_id == third_place_match.loser_team_id:
                    team.final_rank = 4
                    team.finalized_at = now

    def _get_dependency_match_ids(self, advancing: List[LeagueTeamModel]) -> List[str]:
        advancing_ids = {t.league_team_id for t in advancing}
        return [
            m.league_match_id
            for m in self.matches
            if m.winner_team_id in advancing_ids
        ]

    def _rank_round_robin(self) -> List[LeagueTeamModel]:
        grouped = self._group_teams(self.teams, self.current_config.group_count)
        use_points = getattr(self.current_config, "use_point_system", False)
        advancing: List[LeagueTeamModel] = []

        for group in grouped:
            ranked = sorted(group, key=lambda t: (
                -t.points if use_points else -t.wins,
                -t.wins,
                -t.draws,
                -t.losses
            ))
            advancing.extend(ranked[:self.current_config.advances_per_group])

        return advancing

    def _winners_only(self) -> List[LeagueTeamModel]:
        winner_ids = {m.winner_team_id for m in self.matches if m.winner_team_id}
        return [t for t in self.teams if t.league_team_id in winner_ids]

    def _survivors(self) -> List[LeagueTeamModel]:
        return [t for t in self.teams if not t.is_eliminated]

    def _final_winner(self) -> List[LeagueTeamModel]:
        final_match = next((m for m in self.matches if m.is_final and m.winner_team_id), None)
        if final_match:
            return [t for t in self.teams if t.league_team_id == final_match.winner_team_id]
        return []

    def _group_teams(self, teams: List[LeagueTeamModel], groups: int) -> List[List[LeagueTeamModel]]:
        if groups <= 1 or groups >= len(teams):
            return [teams]

        shuffled = teams[:]
        random.shuffle(shuffled)

        result = [[] for _ in range(groups)]
        for i, team in enumerate(shuffled):
            result[i % groups].append(team)

        return result
