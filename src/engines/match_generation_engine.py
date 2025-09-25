import math
import random
from typing import List, Optional
from src.models.league import LeagueCategoryRoundModel
from src.models.match import LeagueMatchModel
from src.models.match_types import TwiceToBeatConfig, parse_round_config
from src.models.team import LeagueTeamModel

class MatchGenerationEngine:
    def __init__(self, league_id: str, round: LeagueCategoryRoundModel, teams: List[LeagueTeamModel], depends_on_match_ids: Optional[List[str]] = None):
        self.round = round
        self.league_id = league_id
        self.teams = teams
        self.config = parse_round_config(round.format_config)
        self.depends_on_match_ids = depends_on_match_ids or []
        
        if hasattr(self.config, "group_count"):
            if self.config.group_count < 1:
                raise ValueError("Invalid configuration: group_count must be at least 1")

            if self.config.group_count > len(teams):
                raise ValueError(
                    f"Invalid configuration: group_count ({self.config.group_count}) exceeds number of teams ({len(teams)})"
                )

            grouped = self._group_teams(self.teams, self.config.group_count)
            for i, group in enumerate(grouped):
                if hasattr(self.config, "advances_per_group"):
                    if self.config.advances_per_group > len(group):
                        raise ValueError(
                            f"Invalid configuration: advances_per_group ({self.config.advances_per_group}) exceeds team count in group {chr(65 + i)} ({len(group)})"
                        )
                        
    def _group_teams(self, teams: List[LeagueTeamModel], group_count: int) -> List[List[LeagueTeamModel]]:
        if group_count <= 1 or group_count >= len(teams):
            for team in teams:
                team.group_label = "A"
            return [teams]

        shuffled = teams[:]
        random.shuffle(shuffled)

        labels = [chr(65 + i) for i in range(group_count)]  # "A", "B", "C", ...
        result = [[] for _ in range(group_count)]

        for i, team in enumerate(shuffled):
            group_index = i % group_count
            team.group_label = labels[group_index]  # ✅ assign label to team
            result[group_index].append(team)

        return result
                        
    def generate(self) -> List[LeagueMatchModel]:
        match self.config.type:
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
                raise ValueError(f"Unsupported format type: {self.config.type}")

    def _generate_round_robin(self) -> List[LeagueMatchModel]:
        matches = []
        grouped = self._group_teams(self.teams, self.config.group_count)
        for group_index, group in enumerate(grouped):
            label = group[0].group_label if group else chr(65 + group_index)
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    matches.append(LeagueMatchModel(
                        league_id=self.league_id,
                        league_category_id=self.round.league_category_id,
                        round_id=self.round.round_id,
                        home_team_id=group[i].league_team_id,
                        away_team_id=group[j].league_team_id,
                        status="Unscheduled",
                        generated_by="system",
                        display_name=f"Group {label}",
                        depends_on_match_ids=self.depends_on_match_ids
                    ))
        return matches

    def _generate_knockout(self) -> List[LeagueMatchModel]:
        matches = []
        grouped = self._group_teams(self.teams, self.config.group_count)

        seeded: List[LeagueTeamModel] = []
        for group in grouped:
            seeded.extend(self._apply_seeding(group, self.config.seeding))

        for i in range(0, len(seeded) - 1, 2):
            home = seeded[i]
            away = seeded[i + 1]

            if (
                isinstance(self.config.series_config, TwiceToBeatConfig) and
                self.config.series_config.advantaged_team == home.league_team_id and
                self.config.series_config.challenger_team == away.league_team_id
            ):
                match1 = LeagueMatchModel(
                    league_id=self.league_id,
                    league_category_id=self.round.league_category_id,
                    round_id=self.round.round_id,
                    home_team_id=home.league_team_id,
                    away_team_id=away.league_team_id,
                    status="Unscheduled",
                    generated_by="system",
                    is_final=True,
                    display_name="Knockout - Twice-to-Beat Game 1",
                    depends_on_match_ids=self.depends_on_match_ids
                )
                match2 = LeagueMatchModel(
                    league_id=self.league_id,
                    league_category_id=self.round.league_category_id,
                    round_id=self.round.round_id,
                    home_team_id=home.league_team_id,
                    away_team_id=away.league_team_id,
                    status="Unscheduled",
                    generated_by="system",
                    is_final=True,
                    display_name="Knockout - Twice-to-Beat Game 2",
                    depends_on_match_ids=[match1.league_match_id]
                )
                matches.extend([match1, match2])
            else:
                matches.append(LeagueMatchModel(
                    league_id=self.league_id,
                    league_category_id=self.round.league_category_id,
                    round_id=self.round.round_id,
                    home_team_id=home.league_team_id,
                    away_team_id=away.league_team_id,
                    status="Unscheduled",
                    generated_by="system",
                    depends_on_match_ids=self.depends_on_match_ids
                ))

        return matches
    
    def _generate_best_of(self) -> List[LeagueMatchModel]:
        if len(self.teams) < 2:
            raise ValueError("Match generation requires at least 2 teams.")

        matches: List[LeagueMatchModel] = []
        games = self.config.games
        grouped = self._group_teams(self.teams, self.config.group_count)

        for group_index, group in enumerate(grouped):
            label = group[0].group_label if group else chr(65 + group_index)

            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    home = group[i]
                    away = group[j]

                    if (
                        isinstance(self.config.series_config, TwiceToBeatConfig) and
                        self.config.series_config.advantaged_team == home.league_team_id and
                        self.config.series_config.challenger_team == away.league_team_id
                    ):
                        match1 = LeagueMatchModel(
                            league_id=self.league_id,
                            league_category_id=self.round.league_category_id,
                            round_id=self.round.round_id,
                            home_team_id=home.league_team_id,
                            away_team_id=away.league_team_id,
                            status="Unscheduled",
                            generated_by="system",
                            is_final=True,
                            display_name=f"Best-of - Twice-to-Beat Game 1",
                            depends_on_match_ids=self.depends_on_match_ids
                        )
                        match2 = LeagueMatchModel(
                            league_id=self.league_id,
                            league_category_id=self.round.league_category_id,
                            round_id=self.round.round_id,
                            home_team_id=home.league_team_id,
                            away_team_id=away.league_team_id,
                            status="Unscheduled",
                            generated_by="system",
                            is_final=True,
                            display_name=f"Best-of - Twice-to-Beat Game 2",
                            depends_on_match_ids=[match1.league_match_id]
                        )
                        matches.extend([match1, match2])
                    else:
                        for game_number in range(1, games + 1):
                            matches.append(LeagueMatchModel(
                                league_id=self.league_id,
                                league_category_id=self.round.league_category_id,
                                round_id=self.round.round_id,
                                home_team_id=home.league_team_id,
                                away_team_id=away.league_team_id,
                                status="Unscheduled",
                                generated_by="system",
                                display_name=f"Group {label} - Game {game_number}",
                                depends_on_match_ids=self.depends_on_match_ids
                            ))

        return matches

    def _generate_twice_to_beat(self) -> List[LeagueMatchModel]:
        if not self.config.advantaged_team or not self.config.challenger_team:
            raise ValueError("TwiceToBeat requires both advantaged_team and challenger_team")

        match1 = LeagueMatchModel(
            league_id=self.league_id,
            league_category_id=self.round.league_category_id,
            round_id=self.round.round_id,
            home_team_id=self.config.advantaged_team,
            away_team_id=self.config.challenger_team,
            status="Unscheduled",
            generated_by="system",
            is_final=True,
            display_name="Twice-to-Beat Finals - Game 1",
            depends_on_match_ids=self.depends_on_match_ids
        )

        match2 = LeagueMatchModel(
            league_id=self.league_id,
            league_category_id=self.round.league_category_id,
            round_id=self.round.round_id,
            home_team_id=self.config.advantaged_team,
            away_team_id=self.config.challenger_team,
            status="Unscheduled",
            generated_by="system",
            is_final=True,
            display_name="Twice-to-Beat Finals - Game 2",
            depends_on_match_ids=[match1.league_match_id]
        )

        return [match1, match2]

    def _apply_seeding(self, teams: List[LeagueTeamModel], method: str) -> List[LeagueTeamModel]:
        if method == "ranking":
            return sorted(teams, key=lambda t: (-t.points, -t.wins, -t.draws, -t.losses))
        random.shuffle(teams)
        return teams

    def _generate_double_elim(self) -> List[LeagueMatchModel]:
        shuffled = self.teams[:]
        random.shuffle(shuffled)
        stage_number = self.config.progress_group
        
        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=shuffled[i].league_team_id,
                away_team_id=shuffled[i + 1].league_team_id,
                status="Unscheduled",
                generated_by="system",
                bracket_side="winners",
                round_number=1,
                stage_number=stage_number,
                is_placeholder=False,
                depends_on_match_ids=[]
            )
            for i in range(0, len(shuffled) - 1, 2)
        ]
        
    async def resolve_winner_team_id(self, session, match_id: str) -> Optional[str]:
        from src.services.match.match_service import LeagueMatchService
        match = await LeagueMatchService.get_match_by_id(session, match_id)
        return match.winner_team_id if match and match.winner_team_id else None

        
    async def generate_double_elim_stage(self, session, stage: int) -> List[LeagueMatchModel]:
        match stage:
            case 1:
                return self._generate_winners_round_1(stage)
            case 2:
                return await self._generate_winners_semis_and_losers_round_1(session, stage)
            case 3:
                return await self._generate_winners_final_and_losers_round_2(session, stage)
            case 4:
                return await self._generate_losers_semifinal(session, stage)
            case 5:
                return await self._generate_losers_final(session, stage)
            case 6:
                return await self._generate_grand_final(session, stage)
            case _:
                raise ValueError(f"Unsupported stage: {stage}")
            
            
    def _generate_winners_round_1(self, stage) -> List[LeagueMatchModel]:
        shuffled = self.teams[:]
        random.shuffle(shuffled)
        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=shuffled[i].league_team_id,
                away_team_id=shuffled[i + 1].league_team_id,
                status="Unscheduled",
                generated_by="system",
                bracket_side="winners",
                stage_number=stage,
                round_number=1
            )
            for i in range(0, len(shuffled), 2)
        ]
        
    async def _generate_winners_semis_and_losers_round_1(self, session, stage) -> List[LeagueMatchModel]:
        from src.services.match.match_service import LeagueMatchService
        previous = await LeagueMatchService.get_previous_matches(session, "winners", 1, self.round.league_category_id)
        matches = []

        for i in range(0, len(previous), 2):
            winner_a = await self.resolve_winner_team_id(session, previous[i].league_match_id)
            winner_b = await self.resolve_winner_team_id(session, previous[i + 1].league_match_id)
            if not winner_a or not winner_b:
                continue

            matches.append(LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=winner_a,
                away_team_id=winner_b,
                status="Unscheduled",
                generated_by="system",
                bracket_side="winners",
                stage_number=stage,
                round_number=2,
                depends_on_match_ids=[previous[i].league_match_id, previous[i + 1].league_match_id]
            ))

        for match in previous:
            loser = match.loser_team_id
            if not loser:
                continue

            matches.append(LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=loser,
                away_team_id=None,
                status="Unscheduled",
                generated_by="system",
                bracket_side="losers",
                stage_number=stage,
                round_number=1,
                depends_on_match_ids=[match.league_match_id]
            ))

        return matches

    async def _generate_winners_final_and_losers_round_2(self, session, stage) -> List[LeagueMatchModel]:
        from src.services.match.match_service import LeagueMatchService
        winners_semis = await LeagueMatchService.get_previous_matches(session, "winners", 2, self.round.league_category_id)
        losers_round_1 = await LeagueMatchService.get_previous_matches(session, "losers", 1, self.round.league_category_id)

        winner_a = await self.resolve_winner_team_id(session, winners_semis[0].league_match_id)
        winner_b = await self.resolve_winner_team_id(session, winners_semis[1].league_match_id)
        loser_a = await self.resolve_winner_team_id(session, losers_round_1[0].league_match_id)
        loser_b = await self.resolve_winner_team_id(session, losers_round_1[1].league_match_id)

        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=winner_a,
                away_team_id=winner_b,
                status="Unscheduled",
                generated_by="system",
                bracket_side="winners",
                stage_number=stage,
                round_number=3,
                depends_on_match_ids=[winners_semis[0].league_match_id, winners_semis[1].league_match_id]
            ),
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=loser_a,
                away_team_id=loser_b,
                status="Unscheduled",
                generated_by="system",
                bracket_side="losers",
                stage_number=stage,
                round_number=2,
                depends_on_match_ids=[losers_round_1[0].league_match_id, losers_round_1[1].league_match_id]
            )
        ]
        
    async def _generate_losers_semifinal(self, session, stage) -> List[LeagueMatchModel]:
        from src.services.match.match_service import LeagueMatchService
        losers_round_2 = await LeagueMatchService.get_previous_matches(session, "losers", 2, self.round.league_category_id)

        winner_a = await self.resolve_winner_team_id(session, losers_round_2[0].league_match_id)
        winner_b = await self.resolve_winner_team_id(session, losers_round_2[1].league_match_id)

        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=winner_a,
                away_team_id=winner_b,
                status="Unscheduled",
                generated_by="system",
                bracket_side="losers",
                stage_number=stage,
                round_number=3,
                depends_on_match_ids=[losers_round_2[0].league_match_id, losers_round_2[1].league_match_id]
            )
        ]
        
    async def _generate_grand_final(self, session, stage) -> List[LeagueMatchModel]:
        from src.services.match.match_service import LeagueMatchService
        winners_final = await LeagueMatchService.get_previous_matches(session, "winners", 3, self.round.league_category_id)
        losers_final = await LeagueMatchService.get_previous_matches(session, "losers", 4, self.round.league_category_id)

        winner_a = await self.resolve_winner_team_id(session, winners_final[0].league_match_id)
        winner_b = await self.resolve_winner_team_id(session, losers_final[0].league_match_id)

        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=winner_a,
                away_team_id=winner_b,
                status="Unscheduled",
                generated_by="system",
                bracket_side="final",
                round_number=5,
                stage_number=stage,
                depends_on_match_ids=[winners_final[0].league_match_id, losers_final[0].league_match_id]
            )
        ]

        
    async def _generate_losers_final(self, session, stage) -> List[LeagueMatchModel]:
        from src.services.match.match_service import LeagueMatchService
        losers_semis = await LeagueMatchService.get_previous_matches(session, "losers", 3, self.round.league_category_id)

        winner_a = await self.resolve_winner_team_id(session, losers_semis[0].league_match_id)

        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=winner_a,
                away_team_id=None,
                status="Unscheduled",
                generated_by="system",
                bracket_side="losers",
                stage_number=stage,
                round_number=4,
                depends_on_match_ids=[losers_semis[0].league_match_id]
            )
        ]
    
# Programmer: Josuan Leonardo Hulom
# From: Cebu Roosevelt Memorial Collegae BSIT 4B
# During: Capstone 2025