from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from src.services.paymongo_service import PaymongoClient
from src.models.team import LeagueTeamModel
from src.extensions import AsyncSession
from quart_auth import current_user

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
        async with AsyncSession() as session:
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
                league_team.payment_status = "Paid On Site"
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

    async def refund_payment(
        self, league_team_id: str, amount: float, payment_status, remove: bool,
        reason: str = "requested_by_customer"
    ):
        async with AsyncSession() as session:
            league_team = await session.scalar(
                select(LeagueTeamModel).where(
                    LeagueTeamModel.league_team_id == league_team_id
                )
            )
            if not league_team:
                return None

            payment_id = (league_team.payment_record or {}).get("payment_id")
            if not payment_id:
                return None

            refund = await self.paymongo.create_refund(payment_id, amount, reason)

            record = dict(league_team.payment_record or {})
            record.setdefault("refunds", []).append(
                {
                    "refund_id": refund["data"]["id"],
                    "amount": amount,
                    "status": refund["data"]["attributes"]["status"],
                    "reason": refund["data"]["attributes"]["reason"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            league_team.payment_record = record

            if remove:
                await session.delete(league_team)
            else:
                league_team.payment_status = payment_status

            await session.commit()

            if not remove:
                await session.refresh(league_team)

            return refund