import json
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from src.models.league_log_model import LeagueLogModel
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel
from src.models.match import LeagueMatchModel
from src.models.team import LeagueTeamModel
from src.schemas.ai_match_schemas import CommissionerDecision

class AutoMatchService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.0
        )
        self.parser = PydanticOutputParser(pydantic_object=CommissionerDecision)

    async def get_round_context(self, round_id: str):
        """
        Fetches teams, matches, and format config from DB
        and creates a clean JSON context for the AI.
        """
        # 1. Fetch Round with Format and Category Teams
        stmt = select(LeagueCategoryRoundModel).options(
            selectinload(LeagueCategoryRoundModel.format),
            selectinload(LeagueCategoryRoundModel.league_category).selectinload(LeagueCategoryModel.teams).selectinload(LeagueTeamModel.team)
        ).where(LeagueCategoryRoundModel.round_id == round_id)
        
        result = await self.session.execute(stmt)
        round_data = result.scalar_one_or_none()
        
        if not round_data:
            raise ValueError("Round not found")

        # 2. Fetch Existing Matches in this round
        matches_stmt = select(LeagueMatchModel).where(
            LeagueMatchModel.round_id == round_id
        ).order_by(LeagueMatchModel.league_match_created_at.asc())
        matches_res = await self.session.execute(matches_stmt)
        matches = matches_res.scalars().all()

        # 3. Prepare Data for AI (simplify objects to save tokens)
        teams_context = [
            {
                "id": t.league_team_id,
                "name": t.team.team_name if t.team else "Unknown Team",
                "wins": t.wins,
                "losses": t.losses,
                "rank_points": t.points,
                "status": t.status,
                "is_eliminated": t.is_eliminated
            }
            for t in round_data.league_category.teams
        ]

        matches_context = [
            {
                "id": m.league_match_id,
                "home_id": m.home_team_id,
                "away_id": m.away_team_id,
                "winner_id": m.winner_team_id,
                "status": m.status, # Completed, Unscheduled
                "label": m.display_name
            }
            for m in matches
        ]

        # Extract Format Config safely
        format_config = {}
        if round_data.format:
            format_config = round_data.format.parsed_format_obj.__dict__ if round_data.format.parsed_format_obj else {}

        return {
            "round_name": round_data.round_name,
            "current_stage": round_data.current_stage,
            "total_stages": round_data.total_stages,
            "format_config": format_config,
            "teams": teams_context,
            "match_history": matches_context
        }, round_data

    async def consult_ai(self, context_data: dict, mode: str = "progress") -> CommissionerDecision:
        """
        Sends data to Gemini and asks for the CommissionerDecision.
        mode: 'generate' (start of round) or 'progress' (during round)
        """
        
        system_prompt = """
        You are an expert Basketball League Commissioner AI for a Philippine 'Barangay' League.
        
        **CRITICAL INSTRUCTION ON LANGUAGE:**
        - The user is NOT technical. Do NOT use words like 'CRUD', 'Database', 'Boolean', 'Schema'.
        - Write the 'explanation' in simple, plain English (e.g., "Team A won Game 1, so we are scheduling Game 2").
        
        **CRITICAL INSTRUCTION ON RANKING:**
        - **ONLY** provide a `rank` if the team is being ELIMINATED (e.g. 3rd, 4th) or is the CHAMPION/RUNNER-UP.
        - **NEVER** assign a rank to a team that is 'advancing' to the next round.

        **FORMAT RULES:**
        1. **Round Robin:** All teams play every other team in their group.
        2. **Single Elimination:** If a team loses, action="eliminate". Winner advances.
        3. **Double Elimination:** - Teams start in Winners Bracket. 1st Loss -> Losers Bracket. 2nd Loss -> Eliminate.
        
        **SERIES LOGIC (Best-Of-X / Twice-to-Beat):**
        - **Best-Of-X (e.g. Best of 3):**
          1. Look at `match_history` for matches between the SAME two teams in this round.
          2. Count wins for Team A and Team B.
          3. Calculate `Wins_Needed = (Total_Games // 2) + 1`. (e.g. Best of 3 needs 2 wins).
          4. If Team A wins >= Wins_Needed -> Team A wins series.
          5. If Team B wins >= Wins_Needed -> Team B wins series.
          6. **IMPORTANT:** If neither team has reached Wins_Needed, you **MUST** generate the next game (e.g. Game 2 or Game 3).
        
        - **Twice-to-Beat:**
          1. **READ** the `format_config` to find the `advantaged_team` ID and `challenger_team` ID.
          2. **CHECK** the `match_history`.
          3. **IF** `match_history` is empty: Generate **Game 1** (Advantaged vs Challenger).
          4. **IF** Game 1 exists and is finished:
             - If **Advantaged Team** (`winner_id` == `advantaged_team`) won: They win the series. Eliminate Challenger.
             - If **Challenger Team** (`winner_id` == `challenger_team`) won: You **MUST** generate **Game 2** (Do-or-Die).
          5. **IF** Game 2 exists and is finished:
             - The winner of Game 2 wins the series. Eliminate the loser.

        **YOUR TASK:**
        Analyze the `match_history` and `teams` stats.
        - If `mode`='generate' and no matches exist: Create the initial pairings.
        - If `mode`='progress': Check completed matches.
          - **For Series:** Check if the series is tied or ongoing. If so, **create the next match immediately**.
          - If a series ends, eliminate the loser and advance the winner.
        - If a team becomes champion (last one standing), set action="champion".

        Output strictly JSON matching the provided schema.
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", """
            Context Mode: {mode}
            Current Database State: {json_data}
            
            {format_instructions}
            """)
        ])

        chain = prompt | self.llm | self.parser

        try:
            decision = await chain.ainvoke({
                "mode": mode,
                "json_data": json.dumps(context_data, default=str),
                "format_instructions": self.parser.get_format_instructions()
            })
            return decision
        except Exception as e:
            print(f"AI Processing Error: {e}")
            # Return a safe fallback or re-raise
            raise e

    async def execute_decision(self, decision: CommissionerDecision, round_obj: LeagueCategoryRoundModel, action_type: str):
        """
        Performs the actual Database Inserts/Updates based on AI plan.
        """
        
        # 1. Create New Matches
        for match_plan in decision.create_matches:
            new_match = LeagueMatchModel(
                league_id=round_obj.league_category.league_id,
                league_category_id=round_obj.league_category_id,
                round_id=round_obj.round_id,
                home_team_id=match_plan.home_team_id,
                away_team_id=match_plan.away_team_id,
                display_name=match_plan.match_label,
                is_placeholder=match_plan.is_placeholder,
                bracket_stage_label=match_plan.placeholder_label,
                depends_on_match_ids=match_plan.depends_on_match_ids,
                status="Unscheduled",
                generated_by="ai_commissioner"
            )
            self.session.add(new_match)

        for update_plan in decision.update_teams:
            stmt = select(LeagueTeamModel).where(LeagueTeamModel.league_team_id == update_plan.team_id)
            res = await self.session.execute(stmt)
            team = res.scalar_one_or_none()
            
            if team:
                if update_plan.action == "eliminate":
                    team.is_eliminated = True
                    if update_plan.rank:
                        team.final_rank = update_plan.rank
                elif update_plan.action == "champion":
                    team.is_champion = True
                    team.final_rank = 1
                elif update_plan.action == "runner_up":
                    team.final_rank = 2
                elif update_plan.action == "third_place":
                    team.final_rank = 3
                elif update_plan.action == "advance":
                    pass

        if decision.round_status_update:
            round_obj.round_status = decision.round_status_update
            
        new_log = LeagueLogModel(
            league_id=round_obj.league_category.league_id, 
            round_id=round_obj.round_id,
            action_type=action_type,
            message=decision.explanation,
            meta_data={
                "matches_created": len(decision.create_matches),
                "teams_updated": len(decision.update_teams),
                "round_status_update": decision.round_status_update
            }
        )
        self.session.add(new_log)
        await self.session.commit()