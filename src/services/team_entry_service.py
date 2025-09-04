from typing import List

from sqlalchemy import select
from src.models.league_admin import CategoryModel
from src.models.player import PlayerModel, PlayerTeamModel
from src.models.team import LeagueTeamModel, TeamModel
from src.models.league import LeagueCategoryModel
from sqlalchemy.orm import selectinload
from src.utils.api_response import ApiException

from datetime import date
from typing import List

async def get_league_team_for_validation(session, league_team_id: str):
    result = await session.execute(
        select(LeagueTeamModel)
        .options(
            # note: LeagueTeam → Team
            selectinload(LeagueTeamModel.team)
            .options(
                selectinload(TeamModel.players)  # note: Team → PlayerTeam list
                .options(
                    selectinload(PlayerTeamModel.player)  # note: PlayerTeam → Player
                )
            ),

            # note: LeagueTeam → LeagueCategory → Category
            selectinload(LeagueTeamModel.category)
            .options(
                selectinload(LeagueCategoryModel.category)  # note: Category linked to league category
            ),

            # note: LeagueTeam → League
            selectinload(LeagueTeamModel.league)
        )
        .where(LeagueTeamModel.league_team_id == league_team_id)
    )

    league_team: LeagueTeamModel | None = result.scalar_one_or_none()
    return league_team

async def get_league_category_for_validation(session, league_category_id: str):
    result = await session.execute(
        select(LeagueCategoryModel)
        .options(
            selectinload(LeagueCategoryModel.category)
        )
        .where(LeagueCategoryModel.league_category_id == league_category_id)
    )

    league_category: LeagueCategoryModel | None = result.scalar_one_or_none()
    return league_category

class ValidateTeamEntry:
    def __init__(self, league_category: LeagueCategoryModel, league_team: LeagueTeamModel):
        self.league_category = league_category
        self.category: CategoryModel = league_category.category
        self.league_team = league_team
        self.team: TeamModel = league_team.team
        
        self.players: List[PlayerTeamModel] = [
            pt for pt in league_team.team.players if pt.is_accepted == "Accepted"
        ]

    def validate(self):
        # note: validate team-level requirements
        ValidateTeam(self.category, self.team).validate()

        # note: validate players
        ValidateTeamPlayers(self.category, self.players).validate()
        
        # note: return all accepted players player_team_id after validation
        return [pt.player_team_id for pt in self.players]

class ValidateTeam:
    def __init__(self, category: CategoryModel, team: TeamModel):
        self.category = category
        self.team = team

    def validate(self):
        # note: address validation
        if self.category.check_address and not self.category.allow_guest_team:
            if not self.team.team_address:
                raise ApiException("Team address is required but missing.")
            if self.category.allowed_address and self.team.team_address != self.category.allowed_address:
                raise ApiException(f"Team {self.team.team_name} cannot join as an outsider or guest team in an not open league category.")

        # note: logo required
        if not self.team.team_logo_url:
            raise ApiException("Team logo is required but missing.")

        # note: coach required
        if not self.team.coach_name:
            raise ApiException("Coach name is required but missing.")

        # note: contact required
        if not self.team.contact_number:
            raise ApiException("Contact number is required but missing.")

class ValidateTeamPlayers:
    def __init__(self, category: CategoryModel, players: List[PlayerTeamModel]):
        self.category = category
        self.players = players

    def validate(self):
        # note: Enforce 12–15 players
        if len(self.players) < 12:
            raise ApiException(f"Minimum 12 players required, got {len(self.players)}.")
        if len(self.players) > 15:
            raise ApiException(f"Maximum 15 players allowed, got {len(self.players)}.")

        # note: loops players
        for player_team in self.players:
            ValidatePlayer(self.category, player_team.player).validate()

        # note: Jersey numbers must be unique
        jersey_numbers = [int(p.player.jersey_number) for p in self.players if p.player.jersey_number]
        if len(jersey_numbers) != len(set(jersey_numbers)):
            raise ApiException("Duplicate jersey numbers found in team.")

class ValidatePlayer:
    def __init__(self, category: CategoryModel, player: PlayerModel):
        self.category = category
        self.player = player

    def validate(self):
        # note: banned / not allowed
        if self.player.is_ban:
            raise ApiException(f"Player {self.player.full_name} is banned.")
        if not self.player.is_allowed:
            raise ApiException(f"Player {self.player.full_name} is not allowed.")

        # note: age check
        if self.category.check_player_age:
            if not self.player.birth_date:
                raise ApiException(f"Player {self.player.full_name} missing birthdate.")
            age = self._calculate_age(self.player.birth_date)
            if self.category.player_min_age and age < self.category.player_min_age:
                raise ApiException(f"Player {self.player.full_name} is too young ({age}).")
            if self.category.player_max_age and age > self.category.player_max_age:
                raise ApiException(f"Player {self.player.full_name} is too old ({age}).")

        # note: gender check
        if self.category.player_gender != "Any":
            if self.player.gender != self.category.player_gender:
                raise ApiException(f"Player {self.player.full_name} gender {self.player.gender} not allowed.")

        # note: jersey number required
        if not self.player.jersey_number:
            raise ApiException(f"Player {self.player.full_name} missing jersey number.")

        # note: address validation
        if self.category.check_address and not self.category.allow_guest_player:
            if not self.player.player_address:
                raise ApiException(f"Player {self.player.full_name} missing address.")
            if self.category.allowed_address and self.player.player_address != self.category.allowed_address:
               raise ApiException(f"Player {self.player.full_name} cannot join as an outsider or guest player in an not open league category")
                    
        # note: document validation
        if self.category.requires_valid_document:
            if not self.player.valid_documents or len(self.player.valid_documents) == 0:
                raise ApiException(f"Player {self.player.full_name} missing required documents.")

            # if self.category.document_valid_until and date.today() > self.category.document_valid_until:
            #     raise ApiException(f"Documents for {self.player.full_name} are expired.")

    def _calculate_age(self, birthdate: date) -> int:
        today = date.today()
        return today.year - birthdate.year - (
            (today.month, today.day) < (birthdate.month, birthdate.day)
        )
