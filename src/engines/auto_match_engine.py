import random
from typing import List, Optional

from src.models.match import LeagueMatchModel
from src.models.league import LeagueCategoryRoundModel
from src.models.team import LeagueTeamModel

class AutoMatchEngine:
    def __init__(self, league_id: str, round: "LeagueCategoryRoundModel", teams: List["LeagueTeamModel"]):
        self.league_id = league_id
        self.round = round
        self.teams = teams
        self.config = round.format.parsed_format_obj if round.format else None
        if not self.config:
            raise ValueError("Round format missing or not configured.")

    # -------------------- HELPERS --------------------
    def _group_teams(self, teams: List["LeagueTeamModel"], group_count: int) -> List[List["LeagueTeamModel"]]:
        """Divide teams into N groups and assign group_label."""
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

    def _apply_seeding(self, teams: List["LeagueTeamModel"], method: str) -> List["LeagueTeamModel"]:
        if method == "ranking":
            return sorted(teams, key=lambda t: (-t.points, -t.wins, -t.draws, -t.losses))
        shuffled = teams[:]
        random.shuffle(shuffled)
        return shuffled

    def _make_match(self, home: "LeagueTeamModel", away: "LeagueTeamModel", label: str,
                    stage_number: int = 1, is_final: bool = False, depends_on: Optional[list] = None) -> "LeagueMatchModel":
        return LeagueMatchModel(
            league_id=self.league_id,
            league_category_id=self.round.league_category_id,
            round_id=self.round.round_id,
            home_team_id=home.league_team_id,
            away_team_id=away.league_team_id,
            status="Unscheduled",
            generated_by="system",
            stage_number=stage_number,
            display_name=label,
            is_final=is_final,
            depends_on_match_ids=depends_on or []
        )

    def _make_series(self, home: "LeagueTeamModel", away: "LeagueTeamModel",
                     series_config: Optional[dict] = None, games: int = 1,
                     label: str = "", stage_number: int = 1) -> List["LeagueMatchModel"]:
        matches = []

        if series_config and series_config.get("type") == "TwiceToBeat":
            m1 = self._make_match(home, away, f"{label} - Twice-to-Beat Game 1",
                                  stage_number=stage_number, is_final=True)
            m2 = self._make_match(home, away, f"{label} - Twice-to-Beat Game 2",
                                  stage_number=stage_number, is_final=True,
                                  depends_on=[m1.league_match_id])
            matches.extend([m1, m2])

        # Best-of-N series
        elif games > 1:
            for g in range(1, games + 1):
                matches.append(
                    self._make_match(home, away, f"{label} - Game {g}",
                                     stage_number=stage_number, is_final=(g == games))
                )
        else:
            matches.append(self._make_match(home, away, label, stage_number=stage_number))

        return matches

    def generate(self) -> List["LeagueMatchModel"]:
        """Generate matches in memory depending on format type."""
        match self.config.type:
            case "RoundRobin":
                return self._generate_round_robin()
            case "Knockout":
                return self._generate_knockout()
            case "BestOf":
                return self._generate_best_of()
            case "DoubleElimination":
                return self._generate_double_elim_stage()
            case _:
                raise ValueError(f"Unsupported format type: {self.config.type}")

    # -------------------- ROUND ROBIN --------------------
    def _generate_round_robin(self) -> List["LeagueMatchModel"]:
        matches = []
        groups = self._group_teams(self.teams, getattr(self.config, "group_count", 1))
        for group_index, group in enumerate(groups):
            label = f"Group {chr(65+group_index)}"
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    matches.append(self._make_match(group[i], group[j], label))
        return matches

    # -------------------- KNOCKOUT --------------------
    def _generate_knockout(self) -> List["LeagueMatchModel"]:
        matches = []
        grouped = self._group_teams(self.teams, getattr(self.config, "group_count", 1))
        seeded: List["LeagueTeamModel"] = []
        for group in grouped:
            seeded.extend(self._apply_seeding(group, getattr(self.config, "seeding", "random")))

        for i in range(0, len(seeded) - 1, 2):
            matches.extend(
                self._make_series(seeded[i], seeded[i + 1],
                                  series_config=getattr(self.config, "series_config", None),
                                  games=1, label="Knockout")
            )
        return matches

    # -------------------- BEST OF --------------------
    def _generate_best_of(self) -> List["LeagueMatchModel"]:
        matches = []
        grouped = self._group_teams(self.teams, getattr(self.config, "group_count", 1))
        games = getattr(self.config, "games", 3)

        for group_index, group in enumerate(grouped):
            for i in range(0, len(group) - 1, 2):
                matches.extend(
                    self._make_series(group[i], group[i + 1],
                                      series_config=getattr(self.config, "series_config", None),
                                      games=games,
                                      label=f"Group {chr(65+group_index)}")
                )
        return matches

    # -------------------- DOUBLE ELIMINATION --------------------
    def _generate_double_elim_stage(self) -> List["LeagueMatchModel"]:
        stage = getattr(self.round, "stage_number", 1) or 1
        shuffled = self.teams[:]
        random.shuffle(shuffled)

        matches = []
        for i in range(0, len(shuffled) - 1, 2):
            matches.append(
                self._make_match(shuffled[i], shuffled[i + 1],
                                 label=f"Winners Stage {stage}",
                                 stage_number=stage)
            )
        return matches
