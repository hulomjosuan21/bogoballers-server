import random
from typing import List
from src.models.league import LeagueCategoryRoundModel
from src.models.match import LeagueMatchModel
from src.models.match_types import parse_round_config
from src.models.team import LeagueTeamModel

class MatchGenerationEngine:
    def __init__(self, league_id: str,round: LeagueCategoryRoundModel, teams: List[LeagueTeamModel]):
        self.round = round
        self.league_id = league_id
        self.teams = teams
        self.config = parse_round_config(round.format_config)

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
                        display_name=f"Group {chr(65 + group_index)}",
                    ))
        return matches

    def _generate_knockout(self) -> List[LeagueMatchModel]:
        shuffled = self._apply_seeding(self.teams, self.config.seeding)
        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=shuffled[i].league_team_id,
                away_team_id=shuffled[i + 1].league_team_id,
                status="Unscheduled",
                generated_by="system",
            )
            for i in range(0, len(shuffled) - 1, 2)
        ]

    def _generate_double_elim(self) -> List[LeagueMatchModel]:
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
                round_number=1,
                is_placeholder=False,
                depends_on_match_ids=[]
            )
            for i in range(0, len(shuffled) - 1, 2)
        ]
        
    def generate_double_elim_stage(self, stage: int) -> List[LeagueMatchModel]:
        match stage:
            case 1:
                return self._generate_winners_round_1()
            case 2:
                return self._generate_winners_semis_and_losers_round_1()
            case 3:
                return self._generate_winners_final_and_losers_round_2()
            case 4:
                return self._generate_losers_semifinal()
            case 5:
                return self._generate_losers_final()
            case 6:
                return self._generate_grand_final()
            case _:
                raise ValueError(f"Unsupported stage: {stage}")
            
    def _generate_winners_round_1(self) -> List[LeagueMatchModel]:
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
                round_number=1
            )
            for i in range(0, len(shuffled), 2)
        ]
        
    def _generate_winners_semis_and_losers_round_1(self) -> List[LeagueMatchModel]:
        previous = self._get_previous_matches("winners", 1)
        matches = []

        for i in range(0, len(previous), 2):
            matches.append(LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=None,
                away_team_id=None,
                status="Pending",
                generated_by="system",
                bracket_side="winners",
                round_number=2,
                depends_on_match_ids=[previous[i].match_id, previous[i + 1].match_id]
            ))

        for match in previous:
            matches.append(LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=None,
                away_team_id=None,
                status="Pending",
                generated_by="system",
                bracket_side="losers",
                round_number=1,
                depends_on_match_ids=[match.match_id]
            ))

        return matches

    def _generate_winners_final_and_losers_round_2(self) -> List[LeagueMatchModel]:
        winners_semis = self._get_previous_matches("winners", 2)
        losers_round_1 = self._get_previous_matches("losers", 1)

        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=None,
                away_team_id=None,
                status="Pending",
                generated_by="system",
                bracket_side="winners",
                round_number=3,
                depends_on_match_ids=[m.match_id for m in winners_semis]
            ),
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=None,
                away_team_id=None,
                status="Pending",
                generated_by="system",
                bracket_side="losers",
                round_number=2,
                depends_on_match_ids=[m.match_id for m in losers_round_1]
            )
        ]
        
    def _generate_losers_semifinal(self) -> List[LeagueMatchModel]:
        losers_round_2 = self._get_previous_matches("losers", 2)
        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=None,
                away_team_id=None,
                status="Pending",
                generated_by="system",
                bracket_side="losers",
                round_number=3,
                depends_on_match_ids=[m.match_id for m in losers_round_2]
            )
        ]
        
    def _generate_grand_final(self) -> List[LeagueMatchModel]:
        winners_final = self._get_previous_matches("winners", 3)
        losers_final = self._get_previous_matches("losers", 4)

        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=None,
                away_team_id=None,
                status="Pending",
                generated_by="system",
                bracket_side="final",
                round_number=5,
                is_final=True,
                depends_on_match_ids=[winners_final[0].match_id, losers_final[0].match_id]
            )
        ]
        
    def _generate_losers_final(self) -> List[LeagueMatchModel]:
        losers_semis = self._get_previous_matches("losers", 3)
        return [
            LeagueMatchModel(
                league_id=self.league_id,
                league_category_id=self.round.league_category_id,
                round_id=self.round.round_id,
                home_team_id=None,
                away_team_id=None,
                status="Pending",
                generated_by="system",
                bracket_side="losers",
                round_number=4,
                depends_on_match_ids=[m.match_id for m in losers_semis]
            )
        ]

    def _generate_best_of(self) -> List[LeagueMatchModel]:
        if len(self.teams) < 2: return []
        return [LeagueMatchModel(
            league_id=self.league_id,
            league_category_id=self.round.league_category_id,
            round_id=self.round.round_id,
            home_team_id=self.teams[0].league_team_id,
            away_team_id=self.teams[1].league_team_id,
            status="Unscheduled",
            generated_by="system",
            is_final=True,
        )]

    def _generate_twice_to_beat(self) -> List[LeagueMatchModel]:
        if not self.config.advantaged_team or not self.config.challenger_team:
            raise ValueError("TwiceToBeat requires both advantaged_team and challenger_team")
        return [LeagueMatchModel(
            league_id=self.league_id,
            league_category_id=self.round.league_category_id,
            round_id=self.round.round_id,
            home_team_id=self.config.advantaged_team,
            away_team_id=self.config.challenger_team,
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

    def _apply_seeding(self, teams: List[LeagueTeamModel], method: str) -> List[LeagueTeamModel]:
        if method == "ranking":
            return sorted(teams, key=lambda t: (-t.points, -t.wins, -t.draws, -t.losses))
        random.shuffle(teams)
        return teams
    
# Programmer: Josuan Leonardo Hulom
# From: Cebu Roosevelt Memorial Collegae BSIT 4B
# During: Capstone 2025