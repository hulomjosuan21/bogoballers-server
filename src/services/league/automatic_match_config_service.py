

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import uuid
from sqlalchemy import and_, delete, select, update
from src.models.match_types import BestOfConfig, DoubleEliminationConfig, KnockoutConfig, RoundConfig, RoundRobinConfig
from src.models.team import LeagueTeamModel
from src.services.league.league_category_service import LeagueCategoryService
from src.engines.auto_match_engine import AutoMatchEngine
from src.models.match import LeagueMatchModel
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
    async def generate_matches(self, round_id: str) -> list[dict]:
        async with AsyncSession() as session:
            round_obj = await session.get(LeagueCategoryRoundModel, round_id)
            if not round_obj:
                raise ValueError("Round not found")

            if round_obj.matches_generated:
                raise ValueError("Matches already generated for this round")

            category = await session.get(LeagueCategoryModel, round_obj.league_category_id)
            teams = await LeagueCategoryService.get_eligible_teams(session, category.league_category_id)

            engine = AutoMatchEngine(
                league_id=category.league_id,
                round=round_obj,
                teams=teams,
            )

            matches = engine.generate()

            for m in matches:
                session.add(m)
            round_obj.matches_generated = True
            round_obj.round_status = "Ongoing"

            await session.commit()
            return f"{len(matches)} match generated"

    async def reset_round(self, round_id: str) -> dict:
        async with AsyncSession() as session:
            round_obj = await session.get(LeagueCategoryRoundModel, round_id)
            if not round_obj:
                raise ValueError("Round not found")

            # Delete matches
            await session.execute(
                delete(LeagueMatchModel).where(LeagueMatchModel.round_id == round_id)
            )

            round_obj.matches_generated = False
            round_obj.round_status = "Upcoming"
            await session.commit()
            return {"message": f"Matches for round {round_id} have been reset"}
    
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

            category_ids = [c.league_category_id for c in categories]
            
            rounds = (
                await session.execute(
                    select(LeagueCategoryRoundModel).where(
                        LeagueCategoryRoundModel.league_category_id.in_(category_ids)
                    )
                )
            ).scalars().all()

            formats = (
                await session.execute(
                    select(LeagueRoundFormatModel).where(
                        LeagueRoundFormatModel.round_id.in_([r.round_id for r in rounds])
                    )
                )
            ).scalars().all()

            edges = (
                await session.execute(
                    select(LeagueFlowEdgeModel).where(
                        LeagueFlowEdgeModel.league_category_id.in_(category_ids)
                    )
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
        
        # process round
        
    async def auto_process_round(self, round_id: str) -> str:
        """
        One button to do everything:
        - If first time (no matches_generated): generate matches for this round.
        - Else if all matches finished:
            - If DoubleElimination and more stages remain -> bump stage and generate next stage matches.
            - Else finish this round:
                - eliminate teams (mark eliminated, rank them)
                - if next_round_id exists, auto-generate matches for the next round
                - if Final, crown champion / runner-up / 3rd place
        - If there are unfinished matches, stop.
        Returns: str message summary
        """
        async with AsyncSession() as session:
            # --- Load round + category + format ---
            r: LeagueCategoryRoundModel = await session.get(LeagueCategoryRoundModel, round_id)
            if not r:
                raise ValueError("Round not found.")

            cat: LeagueCategoryModel = await session.get(LeagueCategoryModel, r.league_category_id)
            if not cat:
                raise ValueError("League category not found.")

            if not r.format or not r.format.parsed_format_obj:
                raise ValueError("Round format missing or not configured.")

            cfg: RoundConfig = r.format.parsed_format_obj

            # Eligible teams are those not eliminated
            teams: List[LeagueTeamModel] = await LeagueCategoryService.get_eligible_teams(
                session, cat.league_category_id
            )

            # --- First time: generate matches for this round ---
            if not r.matches_generated:
                engine = AutoMatchEngine(league_id=cat.league_id, round=r, teams=teams)
                matches = engine.generate()
                for m in matches:
                    session.add(m)

                r.matches_generated = True
                r.round_status = "Ongoing"
                await session.commit()
                return f"Generated {len(matches)} matches for round {r.round_name}."

            # --- Load matches for this round ---
            round_matches: List[LeagueMatchModel] = (
                await session.execute(
                    select(LeagueMatchModel).where(LeagueMatchModel.round_id == r.round_id)
                )
            ).scalars().all()

            if not round_matches:
                # Defensive re-generate
                engine = AutoMatchEngine(league_id=cat.league_id, round=r, teams=teams)
                matches = engine.generate()
                for m in matches:
                    session.add(m)
                r.matches_generated = True
                r.round_status = "Ongoing"
                await session.commit()
                return f"Generated {len(matches)} matches for round {r.round_name}."

            # --- Ensure all matches are finished AND have results ---
            unfinished = [
                m for m in round_matches
                if m.status != "Completed" or not m.winner_team_id or not m.loser_team_id
            ]
            if unfinished:
                raise ValueError(
                    f"Cannot process round {r.round_name}. "
                    f"{len(unfinished)} matches are still unfinished or missing results."
                )

            # --- Everything finished, collect results ---
            winners, losers = self._collect_winners_losers(round_matches)
            eliminated_ids, advanced_ids = await self._apply_elimination_and_ranking(
                session, r, cfg, teams, winners, losers
            )

            # --- Double Elimination staged ---
            if r.format.format_type == 'DoubleElimination':
                if r.current_stage < r.total_stages:
                    r.current_stage += 1
                    teams = await LeagueCategoryService.get_eligible_teams(session, cat.league_category_id)
                    engine = AutoMatchEngine(league_id=cat.league_id, round=r, teams=teams)
                    next_stage_matches = engine.generate()
                    for m in next_stage_matches:
                        session.add(m)
                    r.round_status = "Ongoing"
                    await session.commit()
                    return (
                        f"Advanced to stage {r.current_stage} of Double Elimination. "
                        f"Generated {len(next_stage_matches)} matches. "
                        f"Eliminated {len(eliminated_ids)} teams."
                    )

                # last stage finished => fall through to close the round

            # --- Close this round ---
            r.round_status = "Finished"

            # --- Final round crown ---
            if (r.round_name or "").lower() == "final":
                await self._finalize_championship(session, r, round_matches)
                await session.commit()
                return f"Final round completed. Champion and runner-up assigned."

            # --- Advance to next round ---
            if r.next_round_id:
                next_r: LeagueCategoryRoundModel = await session.get(LeagueCategoryRoundModel, r.next_round_id)
                if not next_r:
                    await session.commit()
                    return f"Round {r.round_name} finished. No valid next round found."

                next_eligible = await LeagueCategoryService.get_eligible_teams(session, cat.league_category_id)
                if not next_r.format or not next_r.format.parsed_format_obj:
                    await session.commit()
                    return f"Round {r.round_name} finished. Next round exists but missing format."

                if not next_r.matches_generated:
                    next_engine = AutoMatchEngine(league_id=cat.league_id, round=next_r, teams=next_eligible)
                    next_matches = next_engine.generate()
                    for m in next_matches:
                        session.add(m)
                    next_r.matches_generated = True
                    next_r.round_status = "Ongoing"

                await session.commit()
                return f"Round {r.round_name} finished. Advanced to round {next_r.round_name}."

            # --- No next round ---
            await session.commit()
            return f"Round {r.round_name} finished. No further rounds."

    # ------------------ Helpers ------------------

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
