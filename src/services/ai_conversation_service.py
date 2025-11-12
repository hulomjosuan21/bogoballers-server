from sqlalchemy import select
from src.models.ai_conversation_model import AIConversationModel
from langchain_core.messages import HumanMessage, AIMessage

class AIConversationService:
    async def load_history(self, session, user_id: str):
        result = await session.execute(
            select(AIConversationModel)
            .filter_by(user_id=user_id)
            .order_by(AIConversationModel.convo_created_at.asc())
        )
        messages = result.scalars().all()

        return [
            HumanMessage(content=m.content)
            if m.message_role == "user"
            else AIMessage(content=m.content)
            for m in messages
        ]

    async def save_message(self, session, user_id: str, role: str, content: str):
        convo = AIConversationModel(
            user_id=user_id,
            message_role=role,
            content=content,
        )
        session.add(convo)
        await session.commit()

    async def clear_conversation(self, session, user_id: str):
        await session.execute(
            AIConversationModel.__table__.delete().where(
                AIConversationModel.user_id == user_id
            )
        )
        await session.commit()