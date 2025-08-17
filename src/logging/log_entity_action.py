from functools import wraps
from typing import Callable, Type
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.future import select
from src.extensions import AsyncSession
from src.models import EntityLogModel
from src.utils.log_message_builder import build_log_message

def log_action(
    *,
    model_class: Type,
    match_column: InstrumentedAttribute,
    action_message: str,
):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            response = await func(*args, **kwargs)

            try:
                from quart_auth import current_user
                user = current_user.user

                async with AsyncSession() as session:
                    result = await session.execute(
                        select(model_class).where(match_column == user.user_id)
                    )
                    entity = result.scalar_one_or_none()
                    if not entity:
                        return response

                    primary_key_name = model_class.__mapper__.primary_key[0].name
                    entity_id = getattr(entity, primary_key_name)

                    log_message = await build_log_message(action_message)

                    session.add(EntityLogModel(
                        entity_id=entity_id,
                        message=log_message
                    ))
                    await session.commit()

            except Exception as log_error:
                print(f"[LOGGING ERROR]: {log_error}")

            return response

        return wrapper
    return decorator
