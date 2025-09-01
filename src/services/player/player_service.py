from datetime import datetime
import json
from typing import List, Optional
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import String, case, cast, func, or_, select, asc, desc
from sqlalchemy.orm import joinedload, selectinload
from src.services.cloudinary_service import CloudinaryService
from src.models.player import PlayerModel
from src.models.user import UserModel
from src.extensions import AsyncSession, settings
from src.utils.api_response import ApiException
from src.utils.server_utils import validate_required_fields
import traceback

class PlayerService:
    async def search_players(self, session, search: str, limit: int = 10) -> List[PlayerModel]:
        query = select(PlayerModel).options(selectinload(PlayerModel.user))

        search_term = f"%{search}%"
        query = query.where(
            or_(
                func.lower(PlayerModel.full_name).like(func.lower(search_term)),
                func.lower(PlayerModel.jersey_name).like(func.lower(search_term)),
                cast(PlayerModel.jersey_number, String).like(search_term),
                func.lower(cast(PlayerModel.position, String)).like(func.lower(search_term))
            )
        )

        query = query.order_by(
            case(
                (func.lower(PlayerModel.full_name) == func.lower(search), 1),
                (cast(PlayerModel.jersey_number, String) == search, 2),
                else_=3
            ),
            PlayerModel.full_name
        ).limit(limit)
            
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_players(
        self,
        filters: Optional[dict] = None,
        search: Optional[str] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        limit: Optional[int] = None
    ) -> List[PlayerModel]:
        async with AsyncSession() as session:
            query = select(PlayerModel).options(
                selectinload(PlayerModel.user)
            )

            if filters:
                for field, value in filters.items():
                    if hasattr(PlayerModel, field):
                        query = query.where(getattr(PlayerModel, field) == value)

            if search:
                search_term = f"%{search}%"
                query = query.where(
                    or_(
                        func.lower(PlayerModel.full_name).like(func.lower(search_term)),
                        func.lower(PlayerModel.jersey_name).like(func.lower(search_term)),
                        cast(PlayerModel.jersey_number, String).like(search_term)
                    )
                )

            if search and not order_by:
                query = query.order_by(
                    case(
                        (func.lower(PlayerModel.full_name) == func.lower(search), 1),
                        (PlayerModel.jersey_number == search, 2),
                        else_=3
                    ),
                    PlayerModel.full_name
                )
            elif order_by and hasattr(PlayerModel, order_by):
                column = getattr(PlayerModel, order_by)
                query = query.order_by(desc(column) if descending else asc(column))

            if limit is not None:
                query = query.limit(limit)
                
            result = await session.execute(query)
            players = result.scalars().all()
            return players
    
    async def create_many(self, players):
        try:
            async with AsyncSession() as session:
                new_players = []

                for player in players:
                    user = UserModel(
                        email=player.get("email"),
                        contact_number=player.get("contact_number"),
                        account_type="Player",
                        is_verified=True
                    )
                    user.set_password(player.get('password_str'))
                    session.add(user)
                    await session.flush()

                    birth_date = datetime.fromisoformat(player.get("birth_date")).date()
                    position = player.get("position")

                    new_player = PlayerModel(
                        user_id=user.user_id,
                        full_name=player.get("full_name"),
                        gender=player.get("gender"),
                        birth_date=birth_date,
                        player_address=player.get("player_address"),
                        height_in=player.get("height_in"),
                        weight_kg=player.get("weight_kg"),
                        jersey_name=player.get("jersey_name"),
                        jersey_number=player.get("jersey_number"),
                        position=position,
                        profile_image_url=player.get("profile_image_url"),
                        total_games_played=player.get('total_games_played', 0),
                        total_points_scored=player.get('total_points_scored', 0),
                        total_assists=player.get('total_assists', 0),
                        total_rebounds=player.get('total_rebounds', 0),
                        total_join_league=player.get('total_join_league', 0)
                    )

                    new_players.append(new_player)

                session.add_all(new_players)
                await session.commit()

                return f"{len(new_players)} players successfully created"

        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise
        
    async def create_one(self, form_data: dict, file):
        required_fields = [
            "email", "contact_number", "password_str",
            "full_name", "gender", "birth_date",
            "player_address", "jersey_name", "jersey_number",
            "position"
        ]

        validate_required_fields(form_data,required_fields)
        if not file:
            raise ApiException("Missing profile image", 400)
        email = form_data.get("email")
        contact_number = form_data.get("contact_number")
        password = form_data.get("password_str")
        account_type = "Player"
        fcm_token = form_data.get("fcm_token", None)

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
            raise ApiException(f": {str(e)}", 400)

        try:
            async with AsyncSession() as session:
                user = UserModel(
                    email=email,
                    contact_number=contact_number,
                    account_type=account_type,
                    is_verified=True,
                    fcm_token=fcm_token
                )
                user.set_password(password)
                session.add(user)
                await session.commit()
                await session.refresh(user)

                profile_image_url = await CloudinaryService.upload_file(file, folder=settings["player_profiles_folder"])

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

        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise

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
        
    async def get_player_leaderboard(self, order_by: Optional[str] = None, limit: int = 100):
        async with AsyncSession() as session:
            query = select(PlayerModel).options(selectinload(PlayerModel.user))

            if order_by:
                if order_by not in {
                    "total_points_scored",
                    "total_assists",
                    "total_rebounds",
                    "total_games_played",
                    "total_join_league"
                }:
                    raise ValueError(f"Invalid order by: {order_by}")

                column = getattr(PlayerModel, order_by)

                query = query.where(column > 0).order_by(desc(column))

            else:
                total_score = (
                    PlayerModel.total_points_scored +
                    PlayerModel.total_assists +
                    PlayerModel.total_rebounds +
                    PlayerModel.total_games_played +
                    PlayerModel.total_join_league
                )

                query = query.where(total_score > 0).order_by(desc(total_score))

            query = query.limit(limit)

            result = await session.execute(query)
            players = result.scalars().all()
            return players