from datetime import datetime, timezone
from typing import Optional
import httpx
from sqlalchemy import select
from src.services.team_validators.validate_league_team_entry import get_league_category_for_validation
from src.services.team_validators.validate_team_entry import ValidateTeamEntry, get_team_for_register_validation
from src.services.paymongo_service import PaymongoClient
from src.models.team import LeagueTeamModel
from src.extensions import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.utils.api_response import ApiException

class RegisterLeagueService:
    def __init__(self):
        self.paymongo = PaymongoClient()

    async def register_team_request(
        self,
        team_id: str,
        league_id: str,
        league_category_id: str,
        amount: Optional[float],
        payment_method: str,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        try:
            async with AsyncSession() as session:
                
                team_to_reg = await get_team_for_register_validation(session, team_id)
                if not team_to_reg:
                    raise ApiException("No Team found")
                category = await get_league_category_for_validation(session, league_category_id)
                if not category:
                    raise ApiException("No Category found")
                
                validation = ValidateTeamEntry(category,team_to_reg)
                
                validation.validate()
                
                league_team = LeagueTeamModel(
                    team_id=team_id,
                    league_id=league_id,
                    league_category_id=league_category_id,
                    amount_paid=0.0,
                    payment_status="Pending",
                    payment_record={
                        "method": payment_method,
                        "amount": amount,
                        "status": "Pending",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                session.add(league_team)
                await session.commit()
                await session.refresh(league_team)

                if payment_method == "Pay on site":
                    league_team.payment_status = "Pending"
                    await session.commit()
                    return {
                        "league_team_id": league_team.league_team_id,
                        "payment_status": league_team.payment_status,
                        "message": "Team submitted. Please pay on site.",
                    }

                checkout_session = await self.paymongo.create_checkout_session(
                    amount=amount,
                    description=f"League fee for team {team_id}",
                    success_url=f"{success_url}?league_team_id={league_team.league_team_id}",
                    cancel_url=f"{cancel_url}?league_team_id={league_team.league_team_id}",
                )

                record = dict(league_team.payment_record or {})
                record["checkout_session_id"] = checkout_session["data"]["id"]
                league_team.payment_record = record
                await session.commit()

                return {
                    "message": "Checkout session created. Redirect user to PayMongo.",
                    "checkout_url": checkout_session["data"]["attributes"]["checkout_url"],
                    "session_id": checkout_session["data"]["id"],
                    "league_team_id": league_team.league_team_id,
                }
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise

    async def confirm_payment_and_register(self, league_team_id: str) -> LeagueTeamModel:
        async with AsyncSession() as session:
            league_team = await session.scalar(
                select(LeagueTeamModel).where(
                    LeagueTeamModel.league_team_id == league_team_id
                )
            )
            if not league_team:
                return None

            record = dict(league_team.payment_record or {})
            session_id = record.get("checkout_session_id")
            if not session_id:
                return None

            session_data = await self.paymongo.retrieve_checkout_session(session_id)
            attributes = session_data["data"]["attributes"]

            payments = attributes.get("payments", [])
            if not payments:
                return None

            payment_id = payments[0]["id"]
            amount = attributes["line_items"][0]["amount"] / 100

            league_team.amount_paid = amount
            league_team.payment_status = "Paid Online"
            record.update(
                {
                    "status": "Paid Online",
                    "amount": amount,
                    "payment_id": payment_id,
                    "paid_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            league_team.payment_record = record
            await session.commit()
            await session.refresh(league_team)
            return league_team

    async def cancel_payment(self, league_team_id: str):
        async with AsyncSession() as session:
            league_team = await session.scalar(
                select(LeagueTeamModel).where(
                    LeagueTeamModel.league_team_id == league_team_id
                )
            )
            if not league_team:
                return None
            league_team.payment_status = "Pending"
            record = dict(league_team.payment_record or {})
            record.update(
                {
                    "status": "Cancelled",
                    "cancelled_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            league_team.payment_record = record
            await session.commit()
            await session.refresh(league_team)
            return league_team

    async def update_league_team(self, league_team_id: str, data: dict) -> LeagueTeamModel:
        """
        Updates a league team with the provided data.
        """
        async with AsyncSession() as session:
            league_team = await session.get(LeagueTeamModel, league_team_id)
            if not league_team:
                raise ValueError("League team not found")

            # Update fields from the data dictionary
            for key, value in data.items():
                if hasattr(league_team, key):
                    setattr(league_team, key, value)
            
            # Special handling for amount paid if payment status changes
            if 'payment_status' in data and 'amount_paid' in data:
                 league_team.amount_paid = data['amount_paid']
                 record = dict(league_team.payment_record or {})
                 record.update({
                     "status": data['payment_status'],
                     "amount": data['amount_paid'],
                     "updated_by_admin_at": datetime.now(timezone.utc).isoformat()
                 })
                 league_team.payment_record = record

            await session.commit()
            await session.refresh(league_team)
            return league_team

    async def remove_league_team(self, league_team_id: str) -> bool:
     
        async with AsyncSession() as session:
            league_team = await session.get(LeagueTeamModel, league_team_id)
            if not league_team:
                raise ValueError("League team not found")
            
            await session.delete(league_team)
            await session.commit()
            return True

    async def refund_payment(
        self, league_team_id: str, amount: float, remove: bool,
        reason: str = "requested_by_customer"
    ):
        print(f"Attempting to refund: {amount}")
        async with AsyncSession() as session:
            league_team = await session.get(LeagueTeamModel, league_team_id)
            if not league_team:
                raise ValueError("League team not found")

            payment_id = (league_team.payment_record or {}).get("payment_id")
            if not payment_id:
                raise ValueError("No online payment ID found. Cannot process refund.")

            refund_details = {}

            if amount > 0:
                try:
                    refund = await self.paymongo.create_refund(payment_id, amount, reason)
                    refund_attributes = refund["data"]["attributes"]
                    
                    refund_details = {
                        "refund_id": refund["data"]["id"],
                        "amount": refund_attributes["amount"] / 100.0, # Store as float
                        "status": refund_attributes["status"],
                        "reason": refund_attributes["reason"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                except Exception as e:
                    error_str = str(e).lower()
                    if 'parameter_above_maximum' in error_str or 'greater than the remaining refundable value' in error_str:
                        raise ValueError(
                            "Refund failed: Amount may be higher than the available balance due to transaction fees or prior refunds."
                        )
                    else:
                        raise e
            
            record = dict(league_team.payment_record or {})
            record.setdefault("refunds", []).append(refund_details)
            league_team.payment_record = record

            if remove:
                await session.delete(league_team)
            else:
                total_refunded_db = sum(r.get('amount', 0) for r in record.get("refunds", []))
                if total_refunded_db >= league_team.amount_paid:
                    league_team.payment_status = "Refunded"
                else:
                    league_team.payment_status = "Partially Refunded"
            
            await session.commit()
            
            return {"message": "Action completed successfully.", "details": refund_details}