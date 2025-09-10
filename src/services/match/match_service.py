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
from src.utils.api_response import ApiException

class MatchGenerationEngine:
    def __init__(self, round: LeagueCategoryRoundModel, teams: List[LeagueTeamModel]):
        self.round = round
        self.teams = teams
        self.config = self._parse_config(round.format_type, round.format_config)
        self.options = round.format_options or {}

    def _parse_config(self, format_type: Optional[str], config_dict: dict) -> RoundConfig:
        def filter_fields(cls, raw: dict) -> dict:
            allowed = set(cls.__annotations__.keys())
            return {k: v for k, v in raw.items() if k in allowed}

        match format_type:
            case "RoundRobin":
                return RoundRobinConfig(**filter_fields(RoundRobinConfig, config_dict))
            case "Knockout":
                return KnockoutConfig(**filter_fields(KnockoutConfig, config_dict))
            case "BestOf":
                return BestOfConfig(**filter_fields(BestOfConfig, config_dict))
            case "DoubleElimination":
                return DoubleEliminationConfig(**filter_fields(DoubleEliminationConfig, config_dict))
            case "TwiceToBeat":
                return TwiceToBeatConfig(**filter_fields(TwiceToBeatConfig, config_dict))
            case _:
                raise ValueError(f"Unknown format_type: {format_type}")

    def generate_matches(self) -> List[MatchModel]:
        match self.config:
            case RoundRobinConfig():
                return self._generate_round_robin()
            case KnockoutConfig():
                return self._generate_knockout()
            case BestOfConfig():
                return self._generate_best_of()
            case DoubleEliminationConfig():
                return self._generate_double_elim()
            case TwiceToBeatConfig():
                return self._generate_twice_to_beat()
            case _:
                raise ValueError("Unsupported config")

    def _generate_round_robin(self) -> List[MatchModel]:
        matches = []
        grouped = self._group_teams(self.teams, self.config.groups)
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

    def _generate_twice_to_beat(self) -> List[MatchModel]:
        adv = self.config.advantaged_team
        chal = self.config.challenger_team
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

class MatchRoundProgressionEngine:
    def __init__(self, matches: List[MatchModel], config: RoundConfig, teams: List[LeagueTeamModel], options: dict):
        self.matches = matches
        self.config = config
        self.teams = teams
        self.options = options
        self.advancing_teams: List[LeagueTeamModel] = []

    def apply_progression(self):
        if isinstance(self.config, KnockoutConfig):
            self._apply_knockout_progression()
        elif isinstance(self.config, DoubleEliminationConfig):
            self._apply_double_elim_progression()
        elif isinstance(self.config, RoundRobinConfig):
            self._apply_round_robin_progression()
        elif isinstance(self.config, TwiceToBeatConfig):
            pass

    def _apply_knockout_progression(self):
        for i in range(len(self.matches) - 1):
            self.matches[i].next_match_id = self.matches[i + 1].match_id
            self.matches[i].next_match_slot = "home"

    def _apply_double_elim_progression(self):
        for i in range(len(self.matches) - 1):
            self.matches[i].next_match_id = self.matches[i + 1].match_id
            self.matches[i].next_match_slot = "home"
            self.matches[i].loser_next_match_id = self.matches[i + 1].match_id
            self.matches[i].loser_next_match_slot = "away"

    def _apply_round_robin_progression(self):
        grouped = self._group_teams(self.teams, self.config.groups)
        for group in grouped:
            ranked = sorted(group, key=lambda t: (
                -t.points,
                -t.wins,
                -t.draws,
                -t.losses
            ))
            self.advancing_teams.extend(ranked[:self.config.advances_per_group])

    def _group_teams(self, teams: List[LeagueTeamModel], groups: int) -> List[List[LeagueTeamModel]]:
        if groups <= 1 or groups >= len(teams):
            return [teams]
        shuffled = teams[:]
        random.shuffle(shuffled)
        group_size = len(teams) // groups
        return [shuffled[i * group_size:(i + 1) * group_size] for i in range(groups)]
    
class MatchService:
    async def generate_and_save_matches(self, round_id: str) -> str:
        try:
            async with AsyncSession() as session:
                result = await session.execute(
                    select(LeagueCategoryRoundModel)
                    .options(selectinload(LeagueCategoryRoundModel.category))
                    .where(LeagueCategoryRoundModel.round_id == round_id)
                )
                round_obj = result.scalar_one_or_none()
                if not round_obj:
                    raise ApiException("No round found.")

                result = await session.execute(
                    select(LeagueTeamModel)
                    .options(
                        selectinload(LeagueTeamModel.team)
                            .selectinload(TeamModel.user),
                        selectinload(LeagueTeamModel.team)
                            .selectinload(TeamModel.players),
                        selectinload(LeagueTeamModel.league_players),
                    )
                    .where(
                        LeagueTeamModel.league_category_id == round_obj.league_category_id,
                        LeagueTeamModel.status == "Accepted",
                        LeagueTeamModel.is_eliminated == False
                    )
                )
                teams = result.scalars().all()

                if not teams or len(teams) < 3:
                    raise ApiException("No eligible teams found.")

                generator = MatchGenerationEngine(round_obj, teams)
                matches = generator.generate_matches()
                
                progression = MatchRoundProgressionEngine(matches, generator.config, teams, generator.options)
                progression.apply_progression()

                session.add_all(matches)
                round_obj.matches_generated = True

                await session.commit()
                return f"{len(matches)} match(es) generated successfully."
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e