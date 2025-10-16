

from typing import Optional, Tuple
import uuid
from sqlalchemy import and_, delete, select, update
from src.extensions import AsyncSession
from src.models.edge import LeagueFlowEdgeModel
from src.models.format import LeagueRoundFormatModel
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel

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
    # You can tune these based on RoundTypeEnum
    "Elimination": 0,
    "Quarterfinal": 1,
    "Semifinal": 2,
    "Final": 3,
}

class AutomaticMatchConfigService:
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

    async def get_flow_state(self, league_id: str) -> dict:
        async with AsyncSession() as session:
            categories = (
                await session.execute(
                    select(LeagueCategoryModel).where(
                        and_(
                            LeagueCategoryModel.league_id == league_id,
                            LeagueCategoryModel.manage_automatic.is_(True),
                        )
                    )
                )
            ).scalars().all()

            rounds = (
                await session.execute(
                    select(LeagueCategoryRoundModel)
                    .join(LeagueCategoryModel)
                    .where(
                        and_(
                            LeagueCategoryModel.league_id == league_id,
                            LeagueCategoryModel.manage_automatic.is_(True),
                        )
                    )
                )
            ).scalars().all()

            formats = (
                await session.execute(
                    select(LeagueRoundFormatModel)
                    .join(
                        LeagueCategoryRoundModel,
                        LeagueRoundFormatModel.round_id == LeagueCategoryRoundModel.round_id,
                        isouter=True,
                    )
                    .join(
                        LeagueCategoryModel,
                        LeagueCategoryRoundModel.league_category_id == LeagueCategoryModel.league_category_id,
                        isouter=True,
                    )
                    .where(LeagueCategoryModel.league_id == league_id)
                )
            ).scalars().all()

            edges = (
                await session.execute(
                    select(LeagueFlowEdgeModel).where(LeagueFlowEdgeModel.league_id == league_id)
                )
            ).scalars().all()

            nodes = []
            y_offset = 50
            Y_SPACING = 120

            for c in categories:
                nodes.append(
                    {
                        "id": c.league_category_id,
                        "type": "leagueCategory",
                        "position": c.position or {"x": 50, "y": y_offset},
                        "data": {
                            "type": "league_category",
                            "league_category": c.to_json(),
                        },
                    }
                )
                y_offset += Y_SPACING

            for r in rounds:
                nodes.append(
                    {
                        "id": r.round_id,
                        "type": "leagueCategoryRound",
                        "position": r.position or {"x": 300, "y": 50},
                        "data": {
                            "type": "league_category_round",
                            "league_category_round": r.round_name,
                            "round": r.to_json(),
                        },
                    }
                )

            for f in formats:
                nodes.append(
                    {
                        "id": f.format_id,
                        "type": "roundFormat",
                        "position": f.position or {"x": 200, "y": 300},
                        "data": {
                            "type": "league_category_round_format",
                            "format_name": f.format_name,
                            "format_type": f.format_name,
                            "format_obj": f.to_dict(),
                        },
                    }
                )

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

            new_format = LeagueRoundFormatModel(
                round_id=round_id,
                format_name=format_name,
                format_type=format_type,
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
        
    async def update_format(self, format_id: str, format_name: str, format_obj: dict):
        async with AsyncSession() as session:
            stmt = (
                update(LeagueRoundFormatModel)
                .where(LeagueRoundFormatModel.format_id == format_id)
                .values(
                    format_name=format_name,
                    format_obj=format_obj
                )
                .execution_options(synchronize_session="fetch")
            )

            result = await session.execute(stmt)
            if result.rowcount == 0:
                raise ValueError("Format not found")

            await session.commit()
            
            return "Success"