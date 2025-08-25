from datetime import datetime
import json
from sqlite3 import IntegrityError
from quart import Blueprint, request
from sqlalchemy import String, cast, or_, select
from src.services.cloudinary_service import CloudinaryService
from src.models.player import PlayerModel
from src.models.user import UserModel
from src.extensions import AsyncSession
from src.utils.api_response import ApiResponse,ApiException
import traceback
from quart_auth import current_user, login_required
from sqlalchemy.orm import joinedload, selectinload
player_bp = Blueprint('player',__name__,url_prefix='/player')

class PlayerHandler:
    @staticmethod
    @player_bp.post('/create')
    async def create_player():
        form = await request.form
        file = (await request.files).get("profile_image")

        required_fields = [
            "email", "contact_number", "password_str",
            "full_name", "gender", "birth_date",
            "player_address", "jersey_name", "jersey_number",
            "position"
        ]

        missing_fields = [f for f in required_fields if not form.get(f)]
        if missing_fields:
            return await ApiResponse.error(
                f"Missing required fields: {', '.join(missing_fields)}",
                status_code=400
            )

        if not file:
            return await ApiResponse.error("Missing profile image", status_code=400)

        email = form.get("email")
        contact_number = form.get("contact_number")
        password = form.get("password_str")
        account_type = "Player"

        full_name = form.get("full_name")
        gender = form.get("gender")
        birth_date = datetime.fromisoformat(form["birth_date"]).date()
        player_address = form.get("player_address")
        jersey_name = form.get("jersey_name")
        jersey_number = float(form["jersey_number"])
        try:
            position = json.loads(form.get("position"))
            if not isinstance(position, list):
                raise ValueError("Position must be a list")
        except (json.JSONDecodeError, ValueError) as e:
            return await ApiResponse.error(f"Invalid position data: {str(e)}", status_code=400)

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

                return await ApiResponse.success(
                    message='Register successfully',
                )

        except IntegrityError:
            traceback.print_exc()
            await session.rollback()
            return await ApiResponse.error('Email or player already exists', status_code=400)
        except Exception as e:
            traceback.print_exc()
            await session.rollback()
            return await ApiResponse.error(str(e), status_code=500)
        
    @staticmethod
    @login_required
    @player_bp.get('/auth')
    async def get_player():
        try:
            user_id = request.args.get("user_id")

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
                        .where(PlayerModel.user_id == current_user.auth_id)
                    )
                    player = result.scalars().first()

                if not player:
                    raise ApiException("Player not found")

                return await ApiResponse.payload(player.to_json())

        except Exception as e:
            return await ApiResponse.error(e)
        
    @staticmethod
    @player_bp.get('/all')
    async def get_players():
        try:
            search = request.args.get("search", None)

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

                return await ApiResponse.payload(payload=players_data)

        except Exception as e:
            print(f"Error in get_players: {e}")
            return await ApiResponse.payload(payload=[])