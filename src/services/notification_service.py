from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from src.extensions import AsyncSession
from src.models.notification import NotificationModel
from src.extensions import settings
from src.utils.api_response import ApiException

class NotificationService:
    async def get_notifications(self, user_id: str):
        async with AsyncSession() as session:
            try:
                result = await session.execute(
                    select(NotificationModel)
                    .where(NotificationModel.to_id == user_id)
                    .order_by(NotificationModel.created_at.desc())
                )
                return result.scalars().all()
            except SQLAlchemyError as e:
                return []

    async def create_notification(self, data: dict):
        async with AsyncSession() as session:
            try:
                notif = NotificationModel(
                    action_type=data.get("action_type", "message_only"),
                    action_payload=data.get("action_payload"),
                    title=data.get("title"),
                    message=data["message"],
                    to_id=data["to_id"],
                    status=data.get("status", "unread"),
                )
                session.add(notif)
                await session.commit()
                await session.refresh(
                    notif,
                    attribute_names=["to_user"]
                )
                
                await notif.send_notification(settings.get("enable_notification", False))
                return notif
            except SQLAlchemyError as e:
                await session.rollback()
                return None
            
    async def delete_one(self, notification_id: str):
        async with AsyncSession() as session:
            try:
                category = await session.get(NotificationModel, notification_id)
                if not category:
                    raise ApiException("Notification not found")
                await session.delete(category)
                await session.commit()
                return "Notification deleted successfully."
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e