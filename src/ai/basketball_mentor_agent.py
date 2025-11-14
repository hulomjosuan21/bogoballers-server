import asyncio
import os
from typing import Optional
from sqlalchemy import select
from langchain_core.prompts import PromptTemplate
from langchain_classic.memory import ConversationBufferMemory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.chains import LLMChain

from src.models.player import PlayerModel
from src.services.ai_conversation_service import AIConversationService


class BasketballMentorAgent:
    def __init__(self, google_api_key: Optional[str] = None):
        google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("Missing GOOGLE_API_KEY.")
        os.environ["GOOGLE_API_KEY"] = google_api_key

        self.convo_service = AIConversationService()
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)

        self.prompt = PromptTemplate.from_template(
            """
            You are *Coach Wan*, an advanced AI basketball performance mentor.
            **You must respond entirely in Bisaya (Cebuano) language.**
            You must respond with clear, concise, and actionable coaching advice only.
            Avoid small talk, greetings, or motivational fluff.

            Use real basketball terminology and focus on specific improvements,
            statistics, drills, techniques, or strategy adjustments.

            If player data is available, reference it directly.
            
            ---
            Conversation so far:
            {chat_history}

            Player: {input}
            Coach (concise, expert answer in Bisaya):
            """
        )

        self.chain = LLMChain(llm=self.llm, prompt=self.prompt, memory=self.memory)


    async def _get_player_profile(self, session, user_id: str) -> str:
        result = await session.execute(select(PlayerModel).filter_by(user_id=user_id))
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
        self.memory.clear()
        history = await self.convo_service.load_history(session, user_id)
        for msg in history:
            self.memory.chat_memory.add_message(msg)

    async def _run_chain_async(self, message: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.chain.run, {"input": message})


    async def chat(self, session, user_id: str, message: str) -> str:
        if not self.memory.buffer:
            await self._initialize_memory(session, user_id)

        await self.convo_service.save_message(session, user_id, "user", message)

        reply = await self._run_chain_async(message)

        await self.convo_service.save_message(session, user_id, "coach", reply)

        return reply
