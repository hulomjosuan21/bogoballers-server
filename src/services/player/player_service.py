from datetime import datetime
import json
from sqlite3 import IntegrityError
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import joinedload, selectinload
from src.services.cloudinary_service import CloudinaryService
from src.models.player import PlayerModel
from src.models.user import UserModel
from src.extensions import AsyncSession
from src.utils.api_response import ApiException
import traceback

class PlayerService:
    async def create(self, form_data: dict, file):
        required_fields = [
            "email", "contact_number", "password_str",
            "full_name", "gender", "birth_date",
            "player_address", "jersey_name", "jersey_number",
            "position"
        ]

        missing_fields = [f for f in required_fields if not form_data.get(f)]
        if missing_fields:
            raise ApiException(f"Missing required fields: {', '.join(missing_fields)}", 400)

        if not file:
            raise ApiException("Missing profile image", 400)

        email = form_data.get("email")
        contact_number = form_data.get("contact_number")
        password = form_data.get("password_str")
        account_type = "Player"

        full_name = form_data.get("full_name")
        gender = form_data.get("gender")
        birth_date = datetime.fromisoformat(form_data["birth_date"]).date()
        player_address = form_data.get("player_address")
        jersey_name = form_data.get("jersey_name")
        jersey_number = float(form_data["jersey_number"])
        
        try:
            position = json.loads(form_data.get("position"))
            if not isinstance(position, list):
                raise ValueError("Position must be a list")
        except (json.JSONDecodeError, ValueError) as e:
            raise ApiException(f"Invalid position data: {str(e)}", 400)

        try:
            async with AsyncSession() as session:
                user = UserModel(
                    email=email,
                    contact_number=contact_number,
                    account_type=account_type,
                    is_verified=True
                )
                user.set_password(password)
                session.add(user)
                await session.commit()
                await session.refresh(user)

                profile_image_url = await CloudinaryService.upload_file(file, folder="players/profiles")

                player = PlayerModel(
                    user_id=user.user_id,
                    full_name=full_name,
                    gender=gender,
                    birth_date=birth_date,
                    player_address=player_address,
                    jersey_name=jersey_name,
                    jersey_number=jersey_number,
                    position=position,
                    profile_image_url=profile_image_url,
                )
                session.add(player)
                await session.commit()

                return 'Register successfully'

        except IntegrityError:
            traceback.print_exc()
            await session.rollback()
            raise ApiException('Email or player already exists', 400)
        except Exception as e:
            traceback.print_exc()
            await session.rollback()
            raise ApiException(str(e), 500)

    async def get_authenticated_player(self, user_id: str = None, current_user_id: str = None):
        async with AsyncSession() as session:
            if user_id:
                result = await session.execute(
                    select(PlayerModel)
                    .options(joinedload(PlayerModel.user))
                    .where(PlayerModel.user_id == user_id)
                )
                player = result.scalars().first()
            else:
                result = await session.execute(
                    select(PlayerModel)
                    .options(joinedload(PlayerModel.user))
                    .where(PlayerModel.user_id == current_user_id)
                )
                player = result.scalars().first()

            if not player:
                raise ApiException("Player not found")

            return player.to_json()

    async def get_many(self, search: str = None):
        try:
            async with AsyncSession() as session:
                query = select(PlayerModel).options(selectinload(PlayerModel.user))

                if search:
                    search_term = f"%{search}%"
                    query = query.where(
                        or_(
                            PlayerModel.full_name.ilike(search_term),
                            PlayerModel.jersey_name.ilike(search_term),
                            cast(PlayerModel.jersey_number, String).ilike(search_term)
                        )
                    )

                result = await session.execute(query)
                players = result.scalars().all()
                players_data = [p.to_json() for p in players]

                return players_data

        except Exception as e:
            return []