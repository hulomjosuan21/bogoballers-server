from sqlalchemy import select
from src.services.league.league_player_service import LeaguePlayerService
from src.models.player import LeaguePlayerModel, PlayerModel, PlayerTeamModel
from src.models.team import LeagueTeamModel, TeamModel
from src.extensions import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.utils.api_response import ApiException
from sqlalchemy.orm import selectinload
from src.services.team_validators.validate_league_team_entry import get_league_team_for_validation, LeagueTeamEntryApproval, get_league_category_for_validation
from src.services.team_validators.validate_team_entry import get_team_for_register_validation, ValidateTeamEntry

league_player_service = LeaguePlayerService()

class LeagueTeamService:
    async def validate_team_entry(self, league_id: str, league_team_id: str, league_category_id: str):
        async with AsyncSession() as session:
            league_team = await get_league_team_for_validation(session=session,league_team_id=league_team_id)
            
            if not league_team:
                raise ApiException("No team found.")
            
            league_category = await get_league_category_for_validation(session=session, league_category_id=league_category_id)
            
            if not league_category:
                raise ApiException("No category found.")
            
            validate_team_entry = LeagueTeamEntryApproval(league_category=league_category,league_team=league_team)
            
            player_team_ids = validate_team_entry.validate()
            players_count = await league_player_service.create_many(league_id=league_id,
                                                                    league_team_id=league_team.league_team_id, 
                                                                    league_category_id=league_category.league_category_id,
                                                                    player_team_ids=player_team_ids)
            
            league_team.status = "Accepted"
            await session.commit()
            
        return f"Team {league_team.team.team_name} validate successfully total players {players_count}"
    
    async def get_all_loaded(self):
        return (
            select(LeagueTeamModel)
            .options(
                # Team + its user
                selectinload(LeagueTeamModel.team).selectinload(TeamModel.user),

                # Team → PlayerTeam → Player → User
                selectinload(LeagueTeamModel.team)
                    .selectinload(TeamModel.players)
                    .selectinload(PlayerTeamModel.player)
                    .selectinload(PlayerModel.user),

                # Category + League
                selectinload(LeagueTeamModel.category),
                selectinload(LeagueTeamModel.league),

                # LeaguePlayers → Player + User
                selectinload(LeagueTeamModel.league_players)
                    .selectinload(LeaguePlayerModel.player)
                    .selectinload(PlayerModel.user),

                # LeaguePlayers → PlayerTeam → Player + User
                selectinload(LeagueTeamModel.league_players)
                    .selectinload(LeaguePlayerModel.player_team)
                    .selectinload(PlayerTeamModel.player)
                    .selectinload(PlayerModel.user),

                # LeaguePlayers → Category + League + LeagueTeam
                selectinload(LeagueTeamModel.league_players).selectinload(LeaguePlayerModel.league_category),
                selectinload(LeagueTeamModel.league_players).selectinload(LeaguePlayerModel.league),
                selectinload(LeagueTeamModel.league_players).selectinload(LeaguePlayerModel.league_team),
            )
        )
            
    
    async def get_all(self, status: str | None, league_id: str, league_category_id: str):
        async with AsyncSession() as session:
            stmt = await self.get_all_loaded()
            
            conditions = [
                LeagueTeamModel.league_id == league_id,
                LeagueTeamModel.league_category_id == league_category_id,
            ]

            if status:
                conditions.append(LeagueTeamModel.status == status)

            stmt = stmt.where(*conditions)

            result = await session.execute(stmt)
            return result.scalars().all()
        
    async def get_all_submission(self, league_id: str, league_category_id: str):
        async with AsyncSession() as session:
            stmt = await self.get_all_loaded()
            
            stmt = stmt.where(
                LeagueTeamModel.status != "Accepted",
                LeagueTeamModel.league_id == league_id,
                LeagueTeamModel.league_category_id == league_category_id
            )

            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def update_one(self, league_team_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                league_team = await session.get(LeagueTeamModel, league_team_id)
                
                if not league_team:
                    raise ApiException("League team not found")
                
                league_team.copy_with(raise_on_same=True, **data)
                await session.commit()
                
            return "League team update success"
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise
        
    async def delete_one(self, league_team_id: str):
        try:
            async with AsyncSession() as session:
                league_team = await session.get(LeagueTeamModel, league_team_id)
                
                if not league_team:
                    raise ApiException("League team not found")
                
                await session.delete(league_team)
                await session.commit()
                
            return "League team delete success"
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise
        
    async def check_entry_one(self, data: dict):
        async with AsyncSession() as session:
            team_id = data.get("team_id")
            league_category_id = data.get("league_category_id")
            team = await get_team_for_register_validation(session=session,team_id=team_id)
            
            if not team:
                raise ApiException("No team found.")

            league_category = await get_league_category_for_validation(session=session, league_category_id=league_category_id)
            
            if not league_category:
                raise ApiException("No category found.")

            ValidateTeamEntry(league_category=league_category,team=team).validate()
            
        return True
            
    async def add_one(self, data: dict):
        try:
            payment_method = data.get("payment_method")
            async with AsyncSession() as session:
                team_id = data.get("team_id")
                league_category_id = data.get("league_category_id")

                if payment_method == "online":
                    return await self.initiate_payment_registration(session=session,data=data)
                amount_paid = float(data.get("amount_paid", 0.0))
                league_team = LeagueTeamModel(
                    team_id=team_id,
                    league_id=data.get("league_id"),
                    league_category_id=league_category_id,
                    status=data.get("status", "Pending"),
                    payment_status=data.get("payment_status", "Pending"),
                    amount_paid=amount_paid
                )
                session.add(league_team)
                await session.commit()
                await session.refresh(league_team)
                return {
                    "success": True,
                    "message": "Registration submitted successfully.",
                    "league_team_id": league_team.league_team_id,
                    "amount_paid": amount_paid
                }
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise ApiException("Your team is already registered for this league", 409)
            
    async def add_one_no_payment(self,data: dict):
        try:
            async with AsyncSession() as session:
                league_team = LeagueTeamModel(
                    team_id=data.get("team_id"),
                    league_id=data.get("league_id"),
                    league_category_id=data.get("league_category_id"),
                    status="Accepted",
                    payment_status="Waived",
                    amount_paid=0
                )
                session.add(league_team)
                await session.commit()
                await session.refresh(league_team)
            return "Registration submitted successfully."
        
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise ApiException("Your team is already registered for this league", 409)