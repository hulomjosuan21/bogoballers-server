from src.models.player import PlayerTeamModel
from src.models.league import LeagueCategoryModel
from src.models.team import TeamModel
from src.utils.api_response import ApiException
from src.utils.server_utils import calculate_age

class ValidateLeagueTeamJoining:
    def __init__(self, league_category: LeagueCategoryModel, team: TeamModel):
        self.league_category = league_category
        self.team = team
        self.team = team.team
        self.category = league_category.category

    def validate(self):
        # 1. Check if league category already full
        if self.league_category.max_team and len(self.league_category.teams) >= self.league_category.max_team:
            raise ApiException(
                f"Cannot join: League category '{self.category.category_name}' already reached max teams ({self.league_category.max_team})."
            )

        # 2. Team address validation
        if self.category.check_address and not self.category.allow_guest_team:
            if not self.team.team_address:
                raise ApiException(f"Team {self.team.team_name} missing address.")
            if self.category.allowed_address and self.team.team_address != self.category.allowed_address:
                raise ApiException(
                    f"Team {self.team.team_name} cannot join as outsider/guest team in category '{self.category.category_name}'."
                )

        # 3. Team required fields
        if not self.team.team_logo_url:
            raise ApiException(f"Team {self.team.team_name} missing logo.")
        if not self.team.coach_name:
            raise ApiException(f"Team {self.team.team_name} missing coach name.")
        if not self.team.contact_number:
            raise ApiException(f"Team {self.team.team_name} missing contact number.")

        # 4. Player validations (only accepted players)
        for player_team in self.team.players:
            if player_team.is_accepted == "Accepted":
                self._validate_player(player_team.player)

    def _validate_player(self, player: PlayerTeamModel):
        # note: Gender validation
        if self.category.player_gender != "Any" and player.gender != self.category.player_gender:
            raise ApiException(
                f"Player {player.full_name} gender '{player.gender}' does not match required category gender '{self.category.player_gender}'."
            )

        # note: Address validation
        if self.category.check_address and not self.category.allow_guest_player:
            if not player.player_address:
                raise ApiException(f"Player {player.full_name} missing address.")
            if self.category.allowed_address and player.player_address != self.category.allowed_address:
               raise ApiException(f"Player {player.full_name} cannot join as an outsider or guest player in an not open league category")
           
        # note: Age validation
        if self.category.check_player_age and player.birth_date:
            age = calculate_age(player.birth_date)
            if self.category.player_min_age and age < self.category.player_min_age:
                raise ApiException(f"Player {player.full_name} is too young ({age}).")
            if self.category.player_max_age and age > self.category.player_max_age:
                raise ApiException(f"Player {player.full_name} is too old ({age}).")

