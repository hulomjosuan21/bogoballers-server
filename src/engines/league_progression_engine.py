import random
from typing import List
from src.engines.match_generation_engine import MatchGenerationEngine
from src.models.league import LeagueCategoryRoundModel
from src.models.match import LeagueMatchModel
from src.models.match_types import TwiceToBeatConfig, parse_round_config
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
        teams: List[LeagueTeamModel],
        auto_proceed: bool
    ):
        self.league_id = league_id
        self.current_round = current_round
        self.next_round = next_round
        self.matches = matches
        self.teams = teams
        self.current_config = parse_round_config(current_round.format_config)
        self.next_config = parse_round_config(next_round.format_config)
        self.auto_proceed = auto_proceed

    def evaluate_advancing_teams(self) -> List[LeagueTeamModel]:
        match self.current_config.type:
            case "RoundRobin":
                return self._rank_round_robin()
            case "Knockout" | "BestOf":
                if isinstance(self.current_config.series_config, TwiceToBeatConfig):
                    return self._twice_to_beat_winner(self.current_config.series_config)
                return self._final_winner()
            case "TwiceToBeat":
                return self._twice_to_beat_winner(self.current_config)
            case "DoubleElimination":
                return self._survivors()
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
                team.eliminated_in_round_id = self.current_round.round_id

        final_match = next((m for m in self.matches if m.is_final and m.winner_team_id), None)
        if final_match:
            for team in self.teams:
                if team.league_team_id == final_match.winner_team_id:
                    team.is_champion = True
                    team.final_rank = 1
                    team.finalized_at = now
                    team.eliminated_in_round_id = self.current_round.round_id
                elif team.league_team_id == final_match.loser_team_id:
                    team.final_rank = 2
                    team.finalized_at = now
                    team.eliminated_in_round_id = self.current_round.round_id

        third_place_match = next((m for m in self.matches if m.is_third_place and m.winner_team_id), None)
        if third_place_match:
            for team in self.teams:
                if team.league_team_id == third_place_match.winner_team_id:
                    team.final_rank = 3
                    team.finalized_at = now
                    team.eliminated_in_round_id = self.current_round.round_id
                elif team.league_team_id == third_place_match.loser_team_id:
                    team.final_rank = 4
                    team.finalized_at = now
                    team.eliminated_in_round_id = self.current_round.round_id
                    
        self.current_round.round_status = "Finished"
        if self.auto_proceed:
            self.next_round.round_status = "Ongoing"

    def _twice_to_beat_winner(self, config: TwiceToBeatConfig) -> List[LeagueTeamModel]:
        finals = [m for m in self.matches if m.is_final and m.winner_team_id]
        challenger_wins = sum(1 for m in finals if m.winner_team_id == config.challenger_team)

        if challenger_wins >= 2:
            return [t for t in self.teams if t.league_team_id == config.challenger_team]
        return [t for t in self.teams if t.league_team_id == config.advantaged_team]

    def _get_dependency_match_ids(self, advancing: List[LeagueTeamModel]) -> List[str]:
        advancing_ids = {t.league_team_id for t in advancing}
        return [
            m.league_match_id
            for m in self.matches
            if m.winner_team_id in advancing_ids
        ]

    def compute_goal_stats(self, team_id: str, matches: List[LeagueMatchModel]) -> tuple[int, int, int]:
        scored = 0
        conceded = 0
        for m in matches:
            if m.home_team_id == team_id:
                scored += m.home_team_score
                conceded += m.away_team_score
            elif m.away_team_id == team_id:
                scored += m.away_team_score
                conceded += m.home_team_score
        return scored, conceded, scored - conceded

    def _rank_round_robin(self) -> List[LeagueTeamModel]:
        grouped = self._group_teams(self.teams, self.current_config.group_count)
        use_points = getattr(self.current_config, "use_point_system", False)
        advancing: List[LeagueTeamModel] = []

        for group in grouped:
            def tiebreak_sort(team: LeagueTeamModel):
                if use_points:
                    scored, conceded, goal_diff = self.compute_goal_stats(team.league_team_id, self.matches)
                    return (
                        -team.points,
                        -goal_diff,
                        -scored
                    )
                else:
                    return (
                        -team.wins,
                        -team.draws,
                        -team.losses
                    )

            ranked = sorted(group, key=tiebreak_sort)

            top_n = ranked[:self.current_config.advances_per_group]
            if use_points and self._has_tie(top_n, use_points):
                top_n = self._resolve_head_to_head(top_n)

            advancing.extend(top_n)

        return advancing
    
    def _resolve_head_to_head(self, tied_teams: List[LeagueTeamModel]) -> List[LeagueTeamModel]:
        head_to_head_scores = {t.league_team_id: 0 for t in tied_teams}
        tied_ids = set(head_to_head_scores.keys())

        for match in self.matches:
            if match.home_team_id in tied_ids and match.away_team_id in tied_ids:
                if match.winner_team_id in tied_ids:
                    head_to_head_scores[match.winner_team_id] += 1

        return sorted(
            tied_teams,
            key=lambda t: (-head_to_head_scores[t.league_team_id])
        )
        
    def _has_tie(self, teams: List[LeagueTeamModel], use_points: bool) -> bool:
        key = lambda t: t.points if use_points else t.wins
        return len(set(key(t) for t in teams)) < len(teams)

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

    def _group_teams(self, teams: List[LeagueTeamModel], group_count: int) -> List[List[LeagueTeamModel]]:
        if group_count <= 1 or group_count >= len(teams):
            for team in teams:
                team.group_label = "A"
            return [teams]

        shuffled = teams[:]
        random.shuffle(shuffled)

        labels = [chr(65 + i) for i in range(group_count)]
        result = [[] for _ in range(group_count)]

        for i, team in enumerate(shuffled):
            group_index = i % group_count
            team.group_label = labels[group_index]
            result[group_index].append(team)

        return result
