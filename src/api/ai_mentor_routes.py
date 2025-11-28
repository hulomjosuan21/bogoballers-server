from quart import Blueprint, request, jsonify
from src.extensions import AsyncSession
from src.ai.basketball_mentor_agent import BasketballMentorAgent
from langchain_core.messages import HumanMessage, AIMessage

ai_mentor_bp = Blueprint("ai", __name__, url_prefix="/ai")
mentor_agent = BasketballMentorAgent()


@ai_mentor_bp.post("/chat")
async def chat_with_ai():
    data = await request.get_json()
    user_id = data.get("user_id")
    message = data.get("message")

    if not user_id or not message:
        return jsonify({"error": "user_id and message are required"}), 400

    async with AsyncSession() as session:
        reply = await mentor_agent.chat(session, user_id, message)

        return jsonify({
            "user": {"role": "user", "content": message},
            "coach": {"role": "coach", "content": reply}
        })


@ai_mentor_bp.get("/history/<user_id>")
async def get_history(user_id: str):
    async with AsyncSession() as session:
        history = await mentor_agent.convo_service.load_history(session, user_id)

        formatted = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                formatted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted.append({"role": "coach", "content": msg.content})
            else:
                formatted.append({"role": "unknown", "content": str(msg)})

        return jsonify(formatted)

@ai_mentor_bp.delete("/history/<user_id>")
async def clear_history(user_id: str):
    async with AsyncSession() as session:
        await mentor_agent.convo_service.clear_conversation(session, user_id)
        return jsonify({"message": "Conversation cleared."})
