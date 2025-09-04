from sqlalchemy import select
from src.models.player import PlayerModel, PlayerTeamModel
from src.services.paymongo_service import PayMongoService
from src.models.team import LeagueTeamModel, TeamModel
from src.extensions import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.utils.api_response import ApiException
from sqlalchemy.orm import selectinload
from src.services.team_entry_service import get_league_team_for_validation, ValidateTeamEntry, get_league_category_for_validation
from quart import request

paymongo_service = PayMongoService()

class LeagueTeamService:
    async def validate_team_entry(self, league_team_id: str, league_category_id: str):
        async with AsyncSession() as session:
            league_team = await get_league_team_for_validation(session=session,league_team_id=league_team_id)
            
            if not league_team:
                raise ApiException("No team found.")
            
            league_category = await get_league_category_for_validation(session=session, league_category_id=league_category_id)
            
            if not league_category:
                raise ApiException("No category found.")
            
            validate_team = ValidateTeamEntry(league_category=league_category,league_team=league_team)
            
            player_team_ids = validate_team.validate()
            print(f"Player ids: ${player_team_ids}")
            
        return "Validate success"
                
    
    async def get_all(self, status: str, league_id: str, league_category_id: str):
        async with AsyncSession() as session:
            stmt = (
                select(LeagueTeamModel)
                .options(
                    selectinload(LeagueTeamModel.team).selectinload(TeamModel.user),
                    selectinload(LeagueTeamModel.team)
                        .selectinload(TeamModel.players)
                        .selectinload(PlayerTeamModel.player)
                        .selectinload(PlayerModel.user),
                    selectinload(LeagueTeamModel.category),
                    selectinload(LeagueTeamModel.league),
                )
                .where(
                    LeagueTeamModel.status == status,
                    LeagueTeamModel.league_id == league_id,
                    LeagueTeamModel.league_category_id == league_category_id
                )
            )

            result = await session.execute(stmt)
            return result.scalars().all()
        
    async def get_all_submission(self, league_id: str, league_category_id: str):
        async with AsyncSession() as session:
            stmt = (
                select(LeagueTeamModel)
                .options(
                    selectinload(LeagueTeamModel.team).selectinload(TeamModel.user),
                    selectinload(LeagueTeamModel.team)
                        .selectinload(TeamModel.players)
                        .selectinload(PlayerTeamModel.player)
                        .selectinload(PlayerModel.user),
                    selectinload(LeagueTeamModel.category),
                    selectinload(LeagueTeamModel.league),
                )
                .where(
                    LeagueTeamModel.status != "Accepted",
                    LeagueTeamModel.league_id == league_id,
                    LeagueTeamModel.league_category_id == league_category_id
                )
            )

            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def initiate_payment_registration(self, session ,data: dict):
        try:
            existing_team = await session.execute(
                select(LeagueTeamModel).where(
                    LeagueTeamModel.team_id == data.get("team_id"),
                )
            )
            if existing_team.scalar_one_or_none():
                raise ApiException("Your team is already registered for this league", 409)

            amount_in_pesos = float(data.get("amount_paid", 500))
            if amount_in_pesos < 0:
                raise ApiException("Amount cannot be negative", 400)
            if amount_in_pesos < 20.00:
                raise ApiException(
                    f"Online payment requires minimum ₱20.00. Your amount (₱{amount_in_pesos:.2f}) "
                    "can only be processed as on-site payment.",
                    400
                )

            league_team = LeagueTeamModel(
                team_id=data.get("team_id"),
                league_id=data.get("league_id"),
                league_category_id=data.get("league_category_id"),
                status="Pending",
                payment_status="Pending",
                amount_paid=amount_in_pesos
            )
            session.add(league_team)
            await session.commit()
            await session.refresh(league_team)

            metadata = {
                "team_id": str(data.get("team_id")),
                "league_id": str(data.get("league_id")),
                "league_category_id": str(data.get("league_category_id")),
                "league_team_id": str(league_team.league_team_id),
                "registration_type": "team_league_registration"
            }

            requestbackend_base_url = str(request.host_url).rstrip("/")
            success_url = f"{requestbackend_base_url}/league-team/payment-success?league_team_id={league_team.league_team_id}&payment_intent_id="
            cancel_url = f"{requestbackend_base_url}/league-team/payment-cancel?league_team_id={league_team.league_team_id}"
            error_url = f"{requestbackend_base_url}/league-team/payment-error?league_team_id={league_team.league_team_id}"

            payment_intent = await paymongo_service.create_payment_intent(
                amount_in_pesos=amount_in_pesos,
                description=f"Team Registration Fee - ₱{amount_in_pesos:.2f}",
                success_url=success_url,
                cancel_url=cancel_url,
                error_url=error_url,
                metadata=metadata
            )

            success_url = f"{success_url}{payment_intent['data']['id']}"
            
            checkout_session = await paymongo_service.create_checkout_session(
                payment_intent_id=payment_intent["data"]["id"],
                success_url=success_url,
                cancel_url=cancel_url,
                error_url=error_url,
                amount_in_pesos=amount_in_pesos
            )

            return {
                "success": True,
                "message": "Registration created! Complete payment to activate.",
                "checkout_url": checkout_session["data"]["attributes"]["checkout_url"],
                "payment_intent_id": payment_intent["data"]["id"],
                "league_team_id": league_team.league_team_id,
                "amount": amount_in_pesos
            }
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise ApiException("Your team is already registered for this league", 409)
        
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
        
    async def add_one(self, data: dict):
        try:
            payment_method = data.get("payment_method")
            async with AsyncSession() as session:
                if payment_method == "online":
                    return await self.initiate_payment_registration(session=session,data=data)
                amount_paid = float(data.get("amount_paid", 0.0))
                league_team = LeagueTeamModel(
                    team_id=data.get("team_id"),
                    league_id=data.get("league_id"),
                    league_category_id=data.get("league_category_id"),
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