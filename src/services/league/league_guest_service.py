from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from src.models.league import LeagueCategoryModel
from src.models.team import LeagueTeamModel, TeamModel
from src.services.team_validators.player_validator import ValidatePlayerEntry
from src.services.team_validators.validate_team_entry import ValidateTeamEntry, get_team_for_register_validation
from src.services.paymongo_service import PaymongoClient
from src.models.guest import GuestRegistrationRequestModel
from src.extensions import AsyncSession
from src.models.player import LeaguePlayerModel, PlayerModel, PlayerTeamModel
from src.utils.api_response import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

class LeagueGuestService:
    def __init__(self):
        self.paymongo = PaymongoClient()

    async def submit_guest_request(
        self,
        amount,
        league_category_id: str,
        payment_method: str,
        success_url: str,
        cancel_url: str,
        team_id: Optional[str] = None,
        player_id: Optional[str] = None,
    ) -> Dict:
        if not team_id and not player_id:
            raise ApiException("Either team_id or player_id must be provided.", 400)
        if team_id and player_id:
            raise ApiException("Cannot submit a request for both a team and a player simultaneously.", 400)

        async with AsyncSession() as session:
            try:
                category_result = await session.execute(
                    select(LeagueCategoryModel).options(selectinload(LeagueCategoryModel.category))
                    .where(LeagueCategoryModel.league_category_id == league_category_id)
                )
                league_category = category_result.scalar_one_or_none()
                if not league_category:
                    raise ApiException("League category not found.", 404)

                request_type = "Team" if team_id else "Player"

                if request_type == "Team":
                    if not league_category.category.allow_guest_team:
                        raise ApiException("This category does not allow guest teams.", 403)
                    team_to_validate = await get_team_for_register_validation(session, team_id)
                    if not team_to_validate:
                        raise ApiException("Team not found.", 404)
                    ValidateTeamEntry(league_category, team_to_validate).validate()
                    amount = league_category.category.guest_team_fee_amount or 0.0
                else:
                    if not league_category.category.allow_guest_player:
                        raise ApiException("This category does not allow guest players.", 403)
                    player_to_validate = await session.get(PlayerModel, player_id)
                    if not player_to_validate:
                        raise ApiException("Player not found.", 404)
                    ValidatePlayerEntry(league_category, player_to_validate).validate()
                    amount = league_category.category.guest_player_fee_amount or 0.0

                new_request = GuestRegistrationRequestModel(
                    league_id=league_category.league_id,
                    league_category_id=league_category_id,
                    team_id=team_id, player_id=player_id, request_type=request_type,
                    payment_status="Pending",
                    payment_record={"method": payment_method, "required_amount": amount, "status": "Pending", "created_at": datetime.now(timezone.utc).isoformat()}
                )
                session.add(new_request)
                await session.flush()

                if payment_method == "Pay on site":
                    new_request.payment_status = "No Charge" if amount == 0 else "Pending"
                    await session.commit()
                    return {"guest_request_id": new_request.guest_request_id, "payment_status": new_request.payment_status, "message": "Guest request submitted successfully."}

                elif payment_method == "Pay online":
                    centavos = int(max(amount, 1.0) * 100)
                    checkout_session = await self.paymongo.create_checkout_session(
                        amount=centavos,
                        description=f"Guest request for {league_category.category.category_name}",
                        success_url=f"{success_url}?guest_request_id={new_request.guest_request_id}",
                        cancel_url=f"{cancel_url}?guest_request_id={new_request.guest_request_id}",
                    )
                    
                    record = dict(new_request.payment_record or {})
                    record["checkout_session_id"] = checkout_session["data"]["id"]
                    new_request.payment_record = record
                    await session.commit()

                    return {"message": "Checkout session created.", "checkout_url": checkout_session["data"]["attributes"]["checkout_url"], "guest_request_id": new_request.guest_request_id}
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise

    async def confirm_guest_payment(self, guest_request_id: str) -> GuestRegistrationRequestModel:
        async with AsyncSession() as session:
            request = await session.get(GuestRegistrationRequestModel, guest_request_id)
            if not request: raise ApiException("Guest request not found.", 404)
            
            record = dict(request.payment_record or {})
            session_id = record.get("checkout_session_id")
            if not session_id: raise ApiException("No checkout session found.", 400)

            session_data = await self.paymongo.retrieve_checkout_session(session_id)
            attributes = session_data["data"]["attributes"]
            payments = attributes.get("payments", [])
            if not payments or payments[0]['attributes']['status'] != 'paid':
                raise ApiException("Payment not confirmed or has failed.", 402)
            
            payment = payments[0]
            amount_paid = payment["attributes"]["amount"] / 100.0

            request.amount_paid = amount_paid
            request.payment_status = "Paid Online"
            record.update({"status": "Paid Online", "amount": amount_paid, "payment_id": payment["id"], "paid_at": datetime.now(timezone.utc).isoformat()})
            request.payment_record = record
            
            return request

    async def cancel_guest_payment(self, guest_request_id: str) -> GuestRegistrationRequestModel:
        async with AsyncSession() as session:
            request = await session.get(GuestRegistrationRequestModel, guest_request_id)
            if not request: raise ApiException("Guest request not found.", 404)
            if request.payment_status == "Paid Online": return request

            record = dict(request.payment_record or {})
            record.update({"status": "Cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()})
            request.payment_record = record
            
            return request

    async def update_guest_request(self, guest_request_id: str, data: dict) -> GuestRegistrationRequestModel:
        async with AsyncSession() as session:
            request = await session.get(GuestRegistrationRequestModel, guest_request_id, options=[selectinload(GuestRegistrationRequestModel.league_category)])
            if not request: raise ApiException("Guest request not found", 404)
            if 'status' in data and data['status'] == 'Accepted':
                if request.status != 'Pending': raise ApiException(f"Request already processed.", 409)
                
                request.status = 'Accepted'
                request.request_processed_at = datetime.now(timezone.utc)
                
                if request.request_type == "Team":
                    session.add(LeagueTeamModel(team_id=request.team_id, league_id=request.league_category.league_id, league_category_id=request.league_category_id, status="Accepted", amount_paid=request.amount_paid, payment_status=request.payment_status, payment_record=request.payment_record))
                else:
                    assign_to_team_id = data.get("assign_to_team_id")
                    if assign_to_team_id:
                        session.add(PlayerTeamModel(player_id=request.player_id, team_id=assign_to_team_id, is_accepted="Guest"))
            
            if 'payment_status' in data:
                new_status = data['payment_status']
                request.payment_status = new_status
                
                if new_status.startswith("Paid"):
                    required = (request.payment_record or {}).get("required_amount", 0)
                    request.amount_paid = required
                elif new_status == "Pending":
                    request.amount_paid = 0

                record = dict(request.payment_record or {})
                record.update({
                    "status": new_status, 
                    "amount": request.amount_paid, 
                    "updated_by_admin_at": datetime.now(timezone.utc).isoformat()
                })
                request.payment_record = record

            await session.commit()
            return request

    async def remove_guest_request(self, guest_request_id: str) -> bool:
        async with AsyncSession() as session:
            request = await session.get(GuestRegistrationRequestModel, guest_request_id)
            if not request: raise ApiException("Guest request not found", 404)
            
            await session.delete(request)
            await session.commit()
            return True

    async def refund_guest_payment(self, guest_request_id: str, amount: float, remove: bool, reason: str):
        async with AsyncSession() as session:
            request = await session.get(GuestRegistrationRequestModel, guest_request_id)
            if not request: raise ApiException("Guest request not found", 404)
            
            payment_id = (request.payment_record or {}).get("payment_id")
            if not payment_id: raise ApiException("No online payment ID found. Cannot refund.", 400)

            refund_details = {}
            if amount > 0:
                refund = await self.paymongo.create_refund(payment_id, amount, reason)
                attrs = refund["data"]["attributes"]
                refund_details = {"refund_id": refund["data"]["id"], "amount": attrs["amount"] / 100.0, "status": attrs["status"], "reason": attrs["reason"], "created_at": datetime.now(timezone.utc).isoformat()}

            record = dict(request.payment_record or {})
            record.setdefault("refunds", []).append(refund_details)
            request.payment_record = record
            
            if remove:
                await session.delete(request)
            else:
                total_refunded = sum(r.get('amount', 0) for r in record.get("refunds", []))
                request.payment_status = "Refunded" if total_refunded >= request.amount_paid else "Partially Refunded"
            
            return {"message": "Refund processed.", "details": refund_details}

    async def list_requests_by_league(self, league_category_id: str) -> List[GuestRegistrationRequestModel]:
        async with AsyncSession() as session:
            result = await session.execute(
                select(GuestRegistrationRequestModel)
                .join(LeagueCategoryModel)
                .where(LeagueCategoryModel.league_category_id == league_category_id)
                .options(selectinload(GuestRegistrationRequestModel.team), selectinload(GuestRegistrationRequestModel.player), selectinload(GuestRegistrationRequestModel.league_category).selectinload(LeagueCategoryModel.category))
                .order_by(GuestRegistrationRequestModel.request_created_at.desc())
            )
            return result.scalars().all()
        
    async def get_all_team(self, league_category_id: str):
        async with AsyncSession() as session:
            stmt = (
                select(LeagueTeamModel)
                .options(
                    selectinload(
                        LeagueTeamModel.league_players.and_(
                            (LeaguePlayerModel.is_ban_in_league == False) &
                            (LeaguePlayerModel.is_allowed_in_league == True)
                        )
                    ),
                    selectinload(LeagueTeamModel.team).selectinload(TeamModel.user),
                )
            )
            
            stmt = stmt.where(
                LeagueTeamModel.status == "Accepted",
                LeagueTeamModel.league_category_id == league_category_id
            )

            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_guest_players_as_serialized(
        self,
        league_id: str
    ) -> List[Dict[str, Any]]:
        async with AsyncSession() as session:
            stmt = (
                select(PlayerModel)
                .join(
                    GuestRegistrationRequestModel, 
                    GuestRegistrationRequestModel.player_id == PlayerModel.player_id
                )
                .where(
                    GuestRegistrationRequestModel.league_id == league_id,
                    GuestRegistrationRequestModel.request_type == "Player"
                )
                .order_by(desc(GuestRegistrationRequestModel.request_created_at))
            )
            
            result = await session.execute(stmt)
            player_models = result.scalars().all()
            return [player.to_json() for player in player_models]

    async def get_guest_teams_as_serialized(
        self,
        league_id: str
    ) -> List[Dict[str, Any]]:
        async with AsyncSession() as session:
            stmt = (
                select(TeamModel)
                .join(
                    GuestRegistrationRequestModel, 
                    GuestRegistrationRequestModel.team_id == TeamModel.team_id
                )
                .where(
                    GuestRegistrationRequestModel.league_id == league_id,
                    GuestRegistrationRequestModel.request_type == "Team"
                )
                .order_by(desc(GuestRegistrationRequestModel.request_created_at))
            )
            
            result = await session.execute(stmt)
            team_models = result.scalars().all()
            return [team.to_json() for team in team_models]