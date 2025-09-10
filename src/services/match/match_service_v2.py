import random
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from src.models.match import MatchModel
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryRoundModel
from src.models.team import LeagueTeamModel, TeamModel
from src.models.match_types import BestOfConfig, DoubleEliminationConfig, KnockoutConfig, RoundConfig, RoundRobinConfig, TwiceToBeatConfig

class MatchGenerationEngine:
    def __init__(self, round: LeagueCategoryRoundModel, teams: List[LeagueTeamModel]):
        self.round = round
        self.teams = teams
        self.config = round.format_config or {}
        self.format_type = round.format_type
        self.options = round.format_options or {}

    def generate_matches(self) -> List[MatchModel]:
        match self.format_type:
            case "RoundRobin":
                return self._generate_round_robin()
            case "Knockout":
                return self._generate_knockout()
            case "DoubleElimination":
                return self._generate_double_elim()
            case "BestOf":
                return self._generate_best_of()
            case "TwiceToBeat":
                return self._generate_twice_to_beat()
            case _:
                raise ValueError(f"Unsupported format_type: {self.format_type}")

    def _generate_round_robin(self) -> List[MatchModel]:
        matches = []
        grouped = self._group_teams(self.teams, self.config.get("group_count", 1))
        for group_index, group in enumerate(grouped):
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    matches.append(MatchModel(
                        league_id=self.round.category.league_id,
                        league_category_id=self.round.league_category_id,
                        round_id=self.round.round_id,
                        home_team_id=group[i].league_team_id,
                        home_team_type="league",
                        away_team_id=group[j].league_team_id,
                        away_team_type="league",
                        status="Unscheduled",
                        generated_by="system",
                        display_name=f"Group {chr(65 + group_index)}",
                    ))
        return matches

    def _generate_knockout(self) -> List[MatchModel]:
        matches = []
        shuffled = self.teams[:]
        random.shuffle(shuffled)
        for i in range(0, len(shuffled), 2):
            if i + 1 >= len(shuffled): continue
            matches.append(MatchModel(
                league_id=self.round.category.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=shuffled[i].league_team_id,
                home_team_type="league",
                away_team_id=shuffled[i + 1].league_team_id,
                away_team_type="league",
                status="Unscheduled",
                generated_by="system",
            ))
        return matches

    def _generate_double_elim(self) -> List[MatchModel]:
        matches = []
        shuffled = self.teams[:]
        random.shuffle(shuffled)
        for i in range(0, len(shuffled), 2):
            if i + 1 >= len(shuffled): continue
            matches.append(MatchModel(
                league_id=self.round.category.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=shuffled[i].league_team_id,
                home_team_type="league",
                away_team_id=shuffled[i + 1].league_team_id,
                away_team_type="league",
                status="Unscheduled",
                generated_by="system",
                bracket_side="winners",
            ))
        return matches

    def _generate_best_of(self) -> List[MatchModel]:
        if len(self.teams) < 2: return []
        home = self.teams[0]
        away = self.teams[1]
        return [MatchModel(
            league_id=self.round.category.league_id,
            league_category_id=self.round.league_category_id,
            round_id=self.round.round_id,
            home_team_id=home.league_team_id,
            home_team_type="league",
            away_team_id=away.league_team_id,
            away_team_type="league",
            status="Unscheduled",
            generated_by="system",
            is_final=True,
        )]

    def _generate_twice_to_beat(self) -> List[MatchModel]:
        adv = self.config.get("advantaged_team")
        chal = self.config.get("challenger_team")
        if not adv or not chal:
            raise ValueError("TwiceToBeatConfig requires both advantaged_team and challenger_team")
        return [MatchModel(
            league_id=self.round.category.league_id,
            league_category_id=self.round.league_category_id,
            round_id=self.round.round_id,
            home_team_id=adv,
            home_team_type="league",
            away_team_id=chal,
            away_team_type="league",
            status="Unscheduled",
            generated_by="system",
            is_final=True,
            display_name="Twice-to-Beat Finals"
        )]

    def _group_teams(self, teams: List[LeagueTeamModel], groups: int) -> List[List[LeagueTeamModel]]:
        if groups <= 1 or groups >= len(teams):
            return [teams]
        shuffled = teams[:]
        random.shuffle(shuffled)
        group_size = len(teams) // groups
        return [shuffled[i * group_size:(i + 1) * group_size] for i in range(groups)]

class MatchProgressionEngine:
    def __init__(self, matches: List[MatchModel], config: dict, teams: List[LeagueTeamModel]):
        self.matches = matches
        self.config = config
        self.teams = teams
        self.advancing_teams: List[LeagueTeamModel] = []

    def evaluate_advancement(self) -> List[LeagueTeamModel]:
        format_type = self.config.get("format_type")

        match format_type:
            case "RoundRobin":
                self._evaluate_round_robin()
            case "Knockout":
                self._evaluate_knockout()
            case "DoubleElimination":
                self._evaluate_double_elim()
            case "BestOf":
                self._evaluate_best_of()
            case "TwiceToBeat":
                self._evaluate_twice_to_beat()

        return self.advancing_teams

    def _evaluate_round_robin(self):
        grouped = self._group_teams(self.teams, self.config.get("group_count", 1))
        for group in grouped:
            ranked = sorted(group, key=lambda t: (
                -t.points,
                -t.wins,
                -t.draws,
                -t.losses
            ))
            self.advancing_teams.extend(ranked[:self.config.get("advances_per_group", 1)])

    def _evaluate_knockout(self):
        winners = [m.winner_team_id for m in self.matches if m.winner_team_id]
        self.advancing_teams = [t for t in self.teams if t.league_team_id in winners]

    def _evaluate_double_elim(self):
        survivors = [t for t in self.teams if getattr(t, "loss_count", 0) < self.config.get("max_loss", 2)]
        self.advancing_teams = survivors

    def _evaluate_best_of(self):
        winners = [m.winner_team_id for m in self.matches if m.is_final and m.winner_team_id]
        self.advancing_teams = [t for t in self.teams if t.league_team_id in winners]

    def _evaluate_twice_to_beat(self):
        final_match = next((m for m in self.matches if m.is_final), None)
        if final_match and final_match.winner_team_id:
            self.advancing_teams = [t for t in self.teams if t.league_team_id == final_match.winner_team_id]

    def _group_teams(self, teams: List[LeagueTeamModel], groups: int) -> List[List[LeagueTeamModel]]:
        if groups <= 1 or groups >= len(teams):
            return [teams]
        shuffled = teams[:]
        random.shuffle(shuffled)
        group_size = len(teams) // groups
        return [shuffled[i * group_size:(i + 1) * group_size] for i in range(groups)]
