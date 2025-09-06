from sqlalchemy import select
from extensions import AsyncSession
from src.models.message import MessageModel
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

async def send_message_notification(sender_id: str, receiver_id: str, title: str, content: str):
    try:
        async with AsyncSession() as session:
            msg = MessageModel(
                sender_id=sender_id,
                receiver_id=receiver_id,
                title=title,
                content=content
            )
            session.add(msg)
            await session.commit()

            result = await session.execute(
                select(MessageModel)
                .where(MessageModel.message_id == msg.message_id)
                .options(
                    selectinload(MessageModel.sender),
                    selectinload(MessageModel.receiver)
                )
            )
            loaded_msg = result.scalars().first()

            result = await loaded_msg.send_notification(enable=True)
            return f"Message {result.title} sent successfully."
    except (IntegrityError, SQLAlchemyError):
        await session.rollback()
        raise