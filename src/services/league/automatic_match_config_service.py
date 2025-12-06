

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import uuid
from sqlalchemy import delete, select, update, or_, case
from src.schemas.format_schemas import RoundConfig
from src.models.team import LeagueTeamModel, TeamModel
from src.services.league.league_category_service import LeagueCategoryService
from src.models.match import LeagueMatchModel
from src.extensions import AsyncSession
from src.models.edge import LeagueFlowEdgeModel
from src.models.format import LeagueRoundFormatModel
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel
from sqlalchemy.orm import joinedload, selectinload, noload, aliased

ALLOWED_CONNECTIONS = {
    ("leagueCategory", "leagueCategoryRound"): ("category-out", "round-in"),
    ("leagueCategoryRound", "leagueCategoryRound"): ("round-out", "round-in"),
    ("roundFormat", "leagueCategoryRound"): ("format-out", "round-format-in"),
}

def _is_permanent_round_id(round_id: str) -> bool:
    return round_id.startswith("lround-")

def _is_permanent_format_id(format_id: str) -> bool:
    return format_id.startswith("lformat-")

ROUND_NAME_TO_ORDER = {
    "Elimination": 0,
    "Quarterfinal": 1,
    "Semifinal": 2,
    "Final": 3,
}

class AutomaticMatchConfigService:
    async def get_flow_state(self, league_id: str) -> dict:
        async with AsyncSession() as session:

            stmt_cats = (
                select(LeagueCategoryModel)
                .options(
                    noload(LeagueCategoryModel.teams),
                    noload(LeagueCategoryModel.rounds),
                    joinedload(LeagueCategoryModel.category)
                )
                .where(
                    LeagueCategoryModel.league_id == league_id,
                    LeagueCategoryModel.manage_automatic.is_(True),
                )
            )
            categories = (await session.execute(stmt_cats)).scalars().all()
            
            if not categories:
                return {"nodes": [], "edges": []}

            category_ids = [c.league_category_id for c in categories]

            stmt_rounds = (
                select(LeagueCategoryRoundModel)
                .where(LeagueCategoryRoundModel.league_category_id.in_(category_ids))
                .options(
                    noload(LeagueCategoryRoundModel.league_category),
                    noload(LeagueCategoryRoundModel.format)
                )
            )
            rounds = (await session.execute(stmt_rounds)).scalars().all()
            round_ids = [r.round_id for r in rounds]
            stmt_formats = (
                select(LeagueRoundFormatModel)
                .where(LeagueRoundFormatModel.round_id.in_(round_ids))
                .options(
                    noload(LeagueRoundFormatModel.round)
                )
            )
            formats = (await session.execute(stmt_formats)).scalars().all()

            stmt_edges = (
                select(LeagueFlowEdgeModel)
                .where(LeagueFlowEdgeModel.league_category_id.in_(category_ids))
            )
            edges = (await session.execute(stmt_edges)).scalars().all()

            nodes = []
            y_offset = 50
            Y_SPACING = 120

            for c in categories:
                position = c.position or {"x": 50, "y": y_offset}
                if not c.position:
                    y_offset += Y_SPACING
                    
                nodes.append({
                    "id": c.league_category_id,
                    "type": "leagueCategory",
                    "position": position,
                    "data": {
                        "type": "league_category",
                        "league_category": c.to_json(),
                    },
                })

            for r in rounds:
                nodes.append({
                    "id": r.round_id,
                    "type": "leagueCategoryRound",
                    "position": r.position or {"x": 300, "y": 50},
                    "data": {
                        "type": "league_category_round",
                        "league_category_round": r.round_name,
                        "round": r.to_json(),
                    },
                })

            for f in formats:
                nodes.append({
                    "id": f.format_id,
                    "type": "roundFormat",
                    "position": f.position or {"x": 200, "y": 300},
                    "data": {
                        "type": "league_category_round_format",
                        "format_name": f.format_name,
                        "format_type": f.format_name,
                        "league_category_id": f.league_category_id,
                        "format_obj": f.to_dict(),
                    },
                })

            edge_list = [
                {
                    "id": e.edge_id,
                    "source": e.source_node_id,
                    "target": e.target_node_id,
                    "sourceHandle": e.source_handle,
                    "targetHandle": e.target_handle,
                }
                for e in edges
            ]

            return {"nodes": nodes, "edges": edge_list}
        
    async def _resolve_league_category_id_from_node(
        self, session, node_id: str, node_type: str
    ) -> Optional[str]:
        if node_type == "leagueCategory":
            lc = await session.get(LeagueCategoryModel, node_id)
            return lc.league_category_id if lc else None

        if node_type == "leagueCategoryRound":
            r = await session.get(LeagueCategoryRoundModel, node_id)
            return r.league_category_id if r else None

        if node_type == "roundFormat":
            fmt = await session.get(LeagueRoundFormatModel, node_id)
            if not fmt or not fmt.round_id:
                return None
            r = await session.get(LeagueCategoryRoundModel, fmt.round_id)
            return r.league_category_id if r else None

        return None

    async def _validate_handles(self, src_type: str, dst_type: str, sh: Optional[str], th: Optional[str]) -> bool:
        allowed = ALLOWED_CONNECTIONS.get((src_type, dst_type))
        if not allowed:
            return False
        return allowed == (sh, th)


    async def create_round(
        self,
        league_category_id: str,
        round_name: str,
        round_order: int,
        position: Optional[dict],
    ) -> dict:
        async with AsyncSession() as session:
            lc = await session.get(LeagueCategoryModel, league_category_id)
            if not lc:
                raise ValueError("League Category not found.")
            if not lc.manage_automatic:
                raise ValueError("Category is not configured for automatic management.")

            new_round = LeagueCategoryRoundModel(
                round_id=f"lround-{uuid.uuid4()}",
                league_category_id=league_category_id,
                round_name=round_name,
                round_order=round_order,
                position=position,
            )
            session.add(new_round)
            await session.commit()
            await session.refresh(new_round)
            return new_round.to_json()
        
    def get_default_config(self, format_type: str) -> dict:
        match format_type:
            case "RoundRobin":
                return {
                    "group_count": 1,
                    "advances_per_group": 1,
                    "use_point_system": False,
                }
            case "Knockout":
                return {
                    "group_count": 1,
                    "seeding": "random",
                    "series_config": None,
                }
            case "DoubleElimination":
                return {
                    "group_count": 1,
                    "max_loss": 2,
                    "progress_group": 1,
                    "max_progress_group": 6,
                    "advances_per_group": 1,
                }
            case "BestOf":
                return {
                    "group_count": 1,
                    "games": 3,
                    "advances_per_group": 1,
                    "series_config": None,
                }
            case _:
                raise ValueError(f"Invalid format_type: {format_type}")

    async def create_or_attach_format(
        self,
        format_name: str,
        round_id: str,
        format_type: str,
        position: Optional[dict],
    ) -> dict:
        async with AsyncSession() as session:
            r = await session.get(LeagueCategoryRoundModel, round_id)
            if not r:
                raise ValueError("Round not found.")

            existing = (
                await session.execute(
                    select(LeagueRoundFormatModel).where(LeagueRoundFormatModel.round_id == round_id)
                )
            ).scalar_one_or_none()

            if existing:
                existing.format_name = format_name
                if position is not None:
                    existing.position = position
                await session.commit()
                await session.refresh(existing)
                return existing.to_dict()
            
            if not format_type:
                raise ValueError("format_type is required when creating a new format.")

            default_config = self.get_default_config(format_type)

            new_format = LeagueRoundFormatModel(
                round_id=round_id,
                format_name=format_name,
                format_type=format_type,
                league_category_id=r.league_category_id,
                format_obj=default_config,
                position=position,
            )
            session.add(new_format)
            await session.commit()
            await session.refresh(new_format)
            return new_format.to_dict()

    async def attach_format_to_round(self, format_id: str, round_id: str) -> dict:
        async with AsyncSession() as session:
            r = await session.get(LeagueCategoryRoundModel, round_id)
            if not r:
                raise ValueError("Round not found.")

            occupied = (
                await session.execute(
                    select(LeagueRoundFormatModel).where(LeagueRoundFormatModel.round_id == round_id)
                )
            ).scalar_one_or_none()
            if occupied:
                raise ValueError("Target round already has a format.")

            fmt = await session.get(LeagueRoundFormatModel, format_id)
            if not fmt:
                raise ValueError("Format not found.")

            if fmt.round_id and fmt.round_id != round_id:
                raise ValueError("This format is already attached to another round.")

            fmt.round_id = round_id
            await session.commit()
            await session.refresh(fmt)
            return fmt.to_dict()

    async def update_node_position(self, node_id: str, node_type: str, position: dict) -> bool:
        async with AsyncSession() as session:
            model_map = {
                "leagueCategory": LeagueCategoryModel,
                "leagueCategoryRound": LeagueCategoryRoundModel,
                "roundFormat": LeagueRoundFormatModel,
            }
            model = model_map.get(node_type)
            if not model:
                raise ValueError(f"Unknown node type: {node_type}")

            pk = getattr(model, list(model.__table__.primary_key.columns)[0].name)
            obj = (
                await session.execute(select(model).where(pk == node_id))
            ).scalar_one_or_none()
            if not obj:
                return False
            obj.position = position
            await session.commit()
            return True

    async def _infer_types_from_ids(
        self, session, source_id: str, target_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
       
        def _type_from_id(id_: str) -> Optional[str]:
            if id_.startswith("lround-"):
                return "leagueCategoryRound"
            if id_.startswith("lformat-"):
                return "roundFormat"
            if id_.startswith("league-category-"):
                return "leagueCategory"
            return None

        src_type = _type_from_id(source_id)
        dst_type = _type_from_id(target_id)

        if not src_type:
            if await session.get(LeagueCategoryRoundModel, source_id):
                src_type = "leagueCategoryRound"
            elif await session.get(LeagueRoundFormatModel, source_id):
                src_type = "roundFormat"
            elif await session.get(LeagueCategoryModel, source_id):
                src_type = "leagueCategory"

        if not dst_type:
            if await session.get(LeagueCategoryRoundModel, target_id):
                dst_type = "leagueCategoryRound"
            elif await session.get(LeagueRoundFormatModel, target_id):
                dst_type = "roundFormat"
            elif await session.get(LeagueCategoryModel, target_id):
                dst_type = "leagueCategory"

        return src_type, dst_type
      
    async def create_edge(self, league_id: str, league_category_id: str,
                          source_id: str, target_id: str,
                          source_handle: Optional[str], target_handle: Optional[str]) -> dict:
        async with AsyncSession() as session:
            if not league_category_id:
                round = await session.get(LeagueCategoryRoundModel, target_id)
                if round:
                    league_category_id = round.league_category_id
                else:
                    raise ValueError("Could not determine node types for edge endpoints.")

            new_edge = LeagueFlowEdgeModel(
                league_id=league_id,
                league_category_id=league_category_id,
                source_node_id=source_id,
                target_node_id=target_id,
                source_handle=source_handle,
                target_handle=target_handle
            )
            session.add(new_edge)
            await session.commit()
            await session.refresh(new_edge)
            return new_edge.to_dict()

    async def delete_edge(self, edge_id: str) -> bool:
        async with AsyncSession() as session:
            stmt = delete(LeagueFlowEdgeModel).where(LeagueFlowEdgeModel.edge_id == edge_id)
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def delete_node(self, node_id: str, node_type: str) -> bool:
        async with AsyncSession() as session:
            model_map = {
                "leagueCategory": LeagueCategoryModel,
                "leagueCategoryRound": LeagueCategoryRoundModel,
                "roundFormat": LeagueRoundFormatModel,
            }
            model = model_map.get(node_type)
            if not model:
                raise ValueError(f"Invalid node type for deletion: {node_type}")

            pk_column = getattr(model, list(model.__table__.primary_key.columns)[0].name)

            stmt = delete(model).where(pk_column == node_id)
            result = await session.execute(stmt)

            edge_stmt = delete(LeagueFlowEdgeModel).where(
                (LeagueFlowEdgeModel.source_node_id == node_id) |
                (LeagueFlowEdgeModel.target_node_id == node_id)
            )
            await session.execute(edge_stmt)

            await session.commit()
            return result.rowcount > 0
        
    async def update_format(self, format_id: str, format_name: str, format_obj: dict, is_configured: bool):
        async with AsyncSession() as session:
            stmt = (
                update(LeagueRoundFormatModel)
                .where(LeagueRoundFormatModel.format_id == format_id)
                .values(
                    format_name=format_name,
                    format_obj=format_obj,
                    is_configured=is_configured
                )
                .execution_options(synchronize_session="fetch")
            )

            result = await session.execute(stmt)
            if result.rowcount == 0:
                raise ValueError("Format not found")

            await session.commit()
            
            return "Success"
        
    def _collect_winners_losers(
        self, matches: List[LeagueMatchModel]
    ) -> Tuple[List[str], List[str]]:
        winners: List[str] = []
        losers: List[str] = []
        for m in matches:
            if m.winner_team_id:
                winners.append(m.winner_team_id)
            if m.loser_team_id:
                losers.append(m.loser_team_id)
        return winners, losers

    async def _apply_elimination_and_ranking(
        self,
        session,
        round_obj: LeagueCategoryRoundModel,
        cfg: RoundConfig,
        all_teams: List[LeagueTeamModel],
        winners: List[str],
        losers: List[str],
    ) -> Tuple[List[str], List[str]]:
        eliminated_ids: List[str] = []
        advanced_ids: List[str] = []
        team_by_id: Dict[str, LeagueTeamModel] = {t.league_team_id: t for t in all_teams}
        total = len(all_teams)

        next_bottom_rank = total

        async def eliminate(team_id: str):
            nonlocal next_bottom_rank
            t = team_by_id.get(team_id)
            if not t or t.is_eliminated:
                return
            t.is_eliminated = True
            t.eliminated_in_round_id = round_obj.round_id
            t.final_rank = next_bottom_rank
            next_bottom_rank -= 1
            session.add(t)
            eliminated_ids.append(team_id)

        def advance(team_id: str):
            if team_id in team_by_id and not team_by_id[team_id].is_eliminated:
                advanced_ids.append(team_id)

        fmt_type = round_obj.format.format_type.lower()

        if fmt_type == "knockout":
            for loser_id in losers:
                await eliminate(loser_id)
            for winner_id in winners:
                advance(winner_id)


        elif fmt_type == "bestof":
            group_map: Dict[str, List[LeagueTeamModel]] = {}
            for t in all_teams:
                g = t.group_label or "A"
                group_map.setdefault(g, []).append(t)

            advances = max(1, int(cfg.advances_per_group or 1))

            for _, team_list in group_map.items():
                sorted_group = sorted(
                    team_list,
                    key=lambda t: (
                        -t.points,
                        -t.wins,
                        t.losses,
                        t.team.team_name.lower() if t.team and t.team.team_name else ""
                    )
                )
                advanced = sorted_group[:advances]
                eliminated = sorted_group[advances:]

                for t in advanced:
                    advance(t.league_team_id)
                for t in eliminated:
                    await eliminate(t.league_team_id)

        elif fmt_type == "roundrobin":
            group_map: Dict[str, List[LeagueTeamModel]] = {}
            for t in all_teams:
                g = t.group_label or "A"
                group_map.setdefault(g, []).append(t)

            advances = max(1, int(cfg.advances_per_group or 1))
            for _, team_list in group_map.items():
                sorted_group = sorted(
                    team_list,
                    key=lambda t: (-t.points, -t.wins, -t.draws, t.losses)
                )
                advanced = sorted_group[:advances]
                eliminated = sorted_group[advances:]
                for t in advanced:
                    advance(t.league_team_id)
                for t in eliminated:
                    await eliminate(t.league_team_id)

        elif fmt_type == "doubleelimination":
            max_loss = max(1, int(getattr(cfg, "max_loss", 2) or 2))
            for team in all_teams:
                if team.losses >= max_loss and not team.is_eliminated:
                    await eliminate(team.league_team_id)
                else:
                    if not team.is_eliminated:
                        advance(team.league_team_id)

        await session.flush()
        return eliminated_ids, advanced_ids

    async def _finalize_championship(
        self,
        session,
        round_obj: LeagueCategoryRoundModel,
        matches: List[LeagueMatchModel],
    ) -> None:
        final_like = [m for m in matches if m.is_final] or matches
        final_match = max(final_like, key=lambda m: (m.stage_number or 0, m.league_match_created_at))

        if not final_match.winner_team_id or not final_match.loser_team_id:
            return

        winner: LeagueTeamModel = await session.get(LeagueTeamModel, final_match.winner_team_id)
        if winner:
            winner.is_champion = True
            winner.final_rank = 1
            winner.finalized_at = datetime.now(timezone.utc)
            session.add(winner)

        runner: LeagueTeamModel = await session.get(LeagueTeamModel, final_match.loser_team_id)
        if runner:
            runner.final_rank = 2
            runner.finalized_at = datetime.now(timezone.utc)
            session.add(runner)

        third_matches = [m for m in matches if getattr(m, "is_third_place", False)]
        if third_matches:
            tp = max(third_matches, key=lambda m: (m.stage_number or 0, m.league_match_created_at))
            if tp.winner_team_id:
                third = await session.get(LeagueTeamModel, tp.winner_team_id)
                if third and (third.final_rank is None or third.final_rank > 3):
                    third.final_rank = 3
                    third.finalized_at = datetime.now(timezone.utc)
                    session.add(third)
        else:
            semi_losers = [m.loser_team_id for m in matches if m.round_number == (final_match.round_number or 1) - 1]
            for loser_id in semi_losers:
                if loser_id:
                    loser_team = await session.get(LeagueTeamModel, loser_id)
                    if loser_team and (loser_team.final_rank is None or loser_team.final_rank > 3):
                        loser_team.final_rank = 3
                        loser_team.finalized_at = datetime.now(timezone.utc)
                        session.add(loser_team)


    async def get_round_matches(self, round_id: str) -> List[dict]:
        async with AsyncSession() as session:
            HomeLeagueTeam = aliased(LeagueTeamModel)
            AwayLeagueTeam = aliased(LeagueTeamModel)
            HomeTeam = aliased(TeamModel)
            AwayTeam = aliased(TeamModel)
            stmt = (
                select(
                    LeagueMatchModel.league_match_id,
                    LeagueMatchModel.display_name,
                    LeagueMatchModel.home_team_score,
                    LeagueMatchModel.away_team_score,
                    LeagueMatchModel.winner_team_id,
                    LeagueMatchModel.loser_team_id,
                    HomeTeam.team_name.label("home_team_name"),
                    AwayTeam.team_name.label("away_team_name"),
                    case(
                        (
                            or_(
                                LeagueMatchModel.scheduled_date.is_not(None),
                                LeagueMatchModel.status != "Unscheduled"
                            ),
                            True
                        ),
                        else_=False
                    ).label("is_scheduled")
                )
                .select_from(LeagueMatchModel)
                .outerjoin(HomeLeagueTeam, LeagueMatchModel.home_team_id == HomeLeagueTeam.league_team_id)
                .outerjoin(HomeTeam, HomeLeagueTeam.team_id == HomeTeam.team_id)
                .outerjoin(AwayLeagueTeam, LeagueMatchModel.away_team_id == AwayLeagueTeam.league_team_id)
                .outerjoin(AwayTeam, AwayLeagueTeam.team_id == AwayTeam.team_id)
                
                .where(LeagueMatchModel.round_id == round_id)
            )
            result = await session.execute(stmt)
            return [dict(row) for row in result.mappings()]