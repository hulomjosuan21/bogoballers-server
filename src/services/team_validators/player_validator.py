from src.models.player import PlayerModel
from src.models.league import LeagueCategoryModel
from src.utils.api_response import ApiException
from src.utils.server_utils import calculate_age
from typing import Set


class ValidatePlayerEntry:
    def __init__(self, league_category: LeagueCategoryModel, player: PlayerModel):
        self.league_category = league_category
        self.player = player
        self.category = league_category.category

    def validate(self):
        self._validate_required_fields()
        self._validate_platform_status()
        self._validate_gender()
        self._validate_address()
        self._validate_age()
        self._validate_documents()

    def _validate_required_fields(self):
        if not self.player.profile_image_url:
            raise ApiException(f"Player {self.player.full_name} is missing a profile image.")
        if not self.player.jersey_name:
            raise ApiException(f"Player {self.player.full_name} is missing a jersey name.")
        if self.player.jersey_number is None: # Jersey number can be 0
            raise ApiException(f"Player {self.player.full_name} is missing a jersey number.")
        if not self.player.birth_date:
             raise ApiException(f"Player {self.player.full_name} is missing a birth date, which is required for age validation.")

    def _validate_platform_status(self):
        if self.player.is_ban:
            raise ApiException(f"Player {self.player.full_name} is banned from the platform.")
        if not self.player.is_allowed:
            raise ApiException(f"Player {self.player.full_name} is currently not allowed to participate.")

    def _validate_gender(self):
        required_gender = self.category.player_gender
        if required_gender != "Any" and self.player.gender != required_gender:
            raise ApiException(
                f"Player {self.player.full_name}'s gender ({self.player.gender}) does not match the required category gender ({required_gender})."
            )

    def _validate_address(self):
        if self.category.check_address and not self.category.allow_guest_player:
            if not self.player.player_address:
                raise ApiException(f"Player {self.player.full_name} is missing an address.")
            
            allowed_address = self.category.allowed_address
            if allowed_address and self.player.player_address != allowed_address:
                raise ApiException(
                    f"Player {self.player.full_name} cannot join as their address does not match the required location: '{allowed_address}'."
                )

    def _validate_age(self):
        if self.category.check_player_age:
            age = calculate_age(self.player.birth_date)
            
            min_age = self.category.player_min_age
            if min_age is not None and age < min_age:
                raise ApiException(f"Player {self.player.full_name} is too young ({age}). Minimum age is {min_age}.")
            
            max_age = self.category.player_max_age
            if max_age is not None and age > max_age:
                raise ApiException(f"Player {self.player.full_name} is too old ({age}). Maximum age is {max_age}.")

    def _validate_documents(self):
        if self.category.requires_valid_document:
            player_docs: Set[str] = set(self.player.valid_documents or [])
            required_docs: Set[str] = set(self.category.allowed_documents or [])

            if not required_docs:
                if not player_docs:
                     raise ApiException(f"Player {self.player.full_name} has not submitted any documents, which are required for this category.")
                return

            if not player_docs.intersection(required_docs):
                raise ApiException(
                    f"Player {self.player.full_name} does not have the required documents. Needs one of: {', '.join(required_docs)}."
                )
