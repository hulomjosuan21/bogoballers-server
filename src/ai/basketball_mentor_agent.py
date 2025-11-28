import os
from typing import Optional
from sqlalchemy import select
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from src.services.ai_conversation_service import AIConversationService
from src.models.player import PlayerModel
load_dotenv()

class BasketballMentorAgent:
    def __init__(self, google_api_key: Optional[str] = None, model: Optional[str] = None):
        google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        model_name = model or os.getenv("GEMINI_MODEL")
        if not google_api_key:
            raise ValueError("Missing GOOGLE_API_KEY.")
        os.environ["GOOGLE_API_KEY"] = google_api_key

        self.convo_service = AIConversationService()

        self.chat_history = []

        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.7
        )

        self.prompt = PromptTemplate.from_template(
            """
            You are *Coach Wan*, an advanced AI basketball performance mentor.
            **You must respond entirely in Bisaya (Cebuano) language.**
            Provide concise, actionable coaching advice only.
            Avoid small talk or motivational fluff.

            Use correct basketball terminology, drills, strategies, footwork,
            shot mechanics, and decision-making corrections.
            Reference player statistics when available.

            ---
            Conversation so far:
            {chat_history}

            Player: {input}
            Coach (concise, expert Bisaya answer):
            """
        )

        self.chain = (
            {
                "input": RunnablePassthrough(),
                "chat_history": lambda _: self.chat_history
            }
            | self.prompt
            | self.llm
        )

    async def _get_player_profile(self, session, user_id: str) -> str:
        result = await session.execute(
            select(PlayerModel).filter_by(user_id=user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            return "Player not found."

        return (
            f"Player Name: {player.full_name}\n"
            f"Height: {player.height_in} in, Weight: {player.weight_kg} kg\n"
            f"Position: {', '.join(player.position)}\n"
            f"Games: {player.total_games_played}, Points: {player.total_points_scored}\n"
            f"Rebounds: {player.total_rebounds}, Assists: {player.total_assists}"
        )

    def _get_player_profile_sync(self, user_id: str) -> str:
        return "Use async _get_player_profile from endpoint context."

    async def _initialize_memory(self, session, user_id: str):
        """Load DB history into self.chat_history."""
        history = await self.convo_service.load_history(session, user_id)
        self.chat_history = history or []

    async def _run_chain_async(self, message: str) -> str:
        """Invoke the LCEL chain asynchronously."""
        response = await self.chain.ainvoke(message)
        return response.content

    async def chat(self, session, user_id: str, message: str) -> str:
        if not self.chat_history:
            await self._initialize_memory(session, user_id)

        await self.convo_service.save_message(session, user_id, "user", message)

        reply = await self._run_chain_async(message)

        await self.convo_service.save_message(session, user_id, "coach", reply)

        self.chat_history.append(
            {"type": "human", "content": message}
        )
        self.chat_history.append(
            {"type": "ai", "content": reply}
        )

        return reply
