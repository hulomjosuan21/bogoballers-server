from src.models.player import PlayerModel
from src.models.league import LeagueCategoryModel
from src.utils.api_response import ApiException
from src.utils.server_utils import calculate_age

class ValidateLeaguePlayer:
    def __init__(self, league_category: LeagueCategoryModel, player: PlayerModel):
        self.league_category = league_category
        self.player = player
        self.category = league_category.category

    def validate(self):
        # 1. Ban / allowed status
        if self.player.is_ban:
            raise ApiException(f"Player {self.player.full_name} is banned from playing.")
        if not self.player.is_allowed:
            raise ApiException(f"Player {self.player.full_name} is not allowed to participate.")

        # 2. Gender check
        if self.category.player_gender != "Any" and self.player.gender != self.category.player_gender:
            raise ApiException(
                f"Player {self.player.full_name} gender '{self.player.gender}' "
                f"does not match required gender '{self.category.player_gender}'."
            )

        # 3. Age restriction
        if self.category.check_player_age and self.player.birth_date:
            age = calculate_age(self.player.birth_date)
            if self.category.player_min_age and age < self.category.player_min_age:
                raise ApiException(f"Player {self.player.full_name} is too young ({age}).")
            if self.category.player_max_age and age > self.category.player_max_age:
                raise ApiException(f"Player {self.player.full_name} is too old ({age}).")

        # 4. Address validation
        if self.category.check_address and not self.category.allow_guest_player:
            if not self.player.player_address:
                raise ApiException(f"Player {self.player.full_name} missing address.")
            if self.category.allowed_address and self.player.player_address != self.category.allowed_address:
                raise ApiException(
                    f"Player {self.player.full_name} cannot join as an outsider in category '{self.category.category_name}'."
                )

        # 5. Document requirement (basic check only)
        if self.category.requires_valid_document and not self.player.valid_documents:
            raise ApiException(f"Player {self.player.full_name} must provide valid documents.")
