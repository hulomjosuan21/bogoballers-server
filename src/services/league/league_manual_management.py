import uuid
from sqlalchemy import select, delete, func
from src.models.team import LeagueTeamModel
from src.models.edge import LeagueFlowEdgeModel
from src.models.group import LeagueGroupModel
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel
from src.models.match import LeagueMatchModel
from src.extensions import AsyncSession
from sqlalchemy.exc import IntegrityError

class ManualLeagueManagementService:
    async def get_flow_state(self, league_id: str) -> dict:
        async with AsyncSession() as session:
            categories_result = await session.execute(
                select(LeagueCategoryModel).where(
                    LeagueCategoryModel.league_id == league_id, 
                    LeagueCategoryModel.manage_automatic.is_(False)
                )
            )
            categories = categories_result.scalars().all()
            category_ids = [c.league_category_id for c in categories]

            rounds_result = await session.execute(
                select(LeagueCategoryRoundModel)
                .where(LeagueCategoryRoundModel.league_category_id.in_(category_ids))
            )
            rounds = rounds_result.scalars().all()

            groups_result = await session.execute(
                select(LeagueGroupModel)
                .join(LeagueCategoryRoundModel, LeagueGroupModel.round_id == LeagueCategoryRoundModel.round_id)
                .where(LeagueCategoryRoundModel.league_category_id.in_(category_ids))
            )
            groups = groups_result.scalars().all()

            matches_result = await session.execute(
                select(LeagueMatchModel)
                .where(LeagueMatchModel.league_category_id.in_(category_ids))
            )
            matches = matches_result.scalars().all()

            edges_result = await session.execute(
                select(LeagueFlowEdgeModel)
                .where(LeagueFlowEdgeModel.league_category_id.in_(category_ids))
            )
            flow_edges = edges_result.scalars().all()

            nodes = []
            
            y_offset_category = 50
            Y_SPACING = 120
            
            for category in categories:
                position = category.position
                if not position:
                    position = {"x": 50, "y": y_offset_category}
                    y_offset_category += Y_SPACING
                
                nodes.append({
                    "id": category.league_category_id,
                    "type": "leagueCategory",
                    "position": position,
                    "data": { "type": "league_category", "league_category": category.to_json() }
                })

            for r in rounds:
                nodes.append({
                    "id": r.round_id,
                    "type": "leagueCategoryRound",
                    "position": r.position or {"x": 300, "y": 50},
                    "data": { "type": "league_category_round", "league_category_round": r.round_name, "round": r.to_json() }
                })
            
            for group in groups:
                nodes.append({
                    "id": group.group_id,
                    "type": "group",
                    "position": group.position or {"x": 550, "y": 50},
                    "data": { "type": "group", "group": group.to_dict() }
                })

            for match in matches:
                nodes.append({
                    "id": match.league_match_id,
                    "type": "leagueMatch",
                    "position": match.position or {"x": 800, "y": 50},
                    "data": { "type": "league_match", "league_match": match.to_json() }
                })
            
            edges = []
            for edge in flow_edges:
                edges.append({
                    "id": edge.edge_id,
                    "source": edge.source_node_id,
                    "target": edge.target_node_id,
                    "sourceHandle": edge.source_handle,
                    "targetHandle": edge.target_handle
                })
                
            
            final_response = {"nodes": nodes, "edges": edges}
            return final_response
        
    async def count_matches_in_round(self, round_id: str, group_id: str | None = None) -> int:
        async with AsyncSession() as session:
            stmt = select(func.count()).select_from(LeagueMatchModel).where(
                LeagueMatchModel.round_id == round_id
            )

            if group_id:
                stmt = stmt.where(LeagueMatchModel.group_id == group_id)

            result = await session.execute(stmt)
            return result.scalar_one()
    

    async def create_new_round(self, league_category_id: str, round_name: str, round_order: int, position: dict) -> dict:
        async with AsyncSession() as session:
            new_round = LeagueCategoryRoundModel(
                round_id=f"lround-{uuid.uuid4()}",
                league_category_id=league_category_id,
                round_name=round_name,
                round_order=round_order,
                position=position
            )
            session.add(new_round)
            await session.commit()
            await session.refresh(new_round)
            return new_round.to_json()

    async def create_empty_match(
        self, 
        league_id: str, 
        league_category_id: str, 
        round_id: str, 
        display_name: str, 
        position: dict,
        is_final: bool,
        group_id: str | None,
        is_runner_up: bool,
        is_elimination: bool,
        is_third_place: bool
    ) -> dict:
        async with AsyncSession() as session:
            new_match = LeagueMatchModel(
                league_id=league_id,
                league_category_id=league_category_id,
                round_id=round_id,
                display_name=display_name,
                position=position,
                group_id=group_id,
                is_final=is_final,
                is_runner_up=is_runner_up,
                is_elimination=is_elimination,
                is_third_place=is_third_place,
                pairing_method="manual",
            )
            session.add(new_match)
            await session.commit()
            await session.refresh(new_match)
            return new_match.to_json()

    async def create_group(self, league_category_id, round_id: str, round_name: str, display_name: str, position: dict) -> dict:
        async with AsyncSession() as session:
            new_group = LeagueGroupModel(
                league_category_id=league_category_id,
                round_id=round_id,
                round_name=round_name,
                display_name=display_name,
                position=position
            )
            session.add(new_group)
            await session.commit()
            await session.refresh(new_group)
            return new_group.to_dict()

    async def update_group(self, group_id: str, data: dict) -> dict:
        async with AsyncSession() as session:
            group = await session.get(LeagueGroupModel, group_id)
            if not group:
                raise ValueError(f"Group with ID {group_id} not found.")
            
            for key, value in data.items():
                if hasattr(group, key):
                    setattr(group, key, value)
            
            await session.commit()
            await session.refresh(group)
            return group.to_dict()

    async def create_edge(self, league_category_id: str, league_id: str, source_id: str, target_id: str, source_handle: str, target_handle: str) -> dict:
        async with AsyncSession() as session:
            new_edge = LeagueFlowEdgeModel(
                league_category_id=league_category_id,
                league_id=league_id,
                source_node_id=source_id,
                target_node_id=target_id,
                source_handle=source_handle,
                target_handle=target_handle
            )
            session.add(new_edge)
            await session.commit()
            await session.refresh(new_edge)
            return new_edge.to_dict()

    async def assign_team_to_match(self, match_id: str, team_id: str, slot: str) -> dict:
        async with AsyncSession() as session:
            try:
                match = await session.get(LeagueMatchModel, match_id)
                if not match:
                    raise ValueError(f"Match with ID {match_id} not found.")

                if match.home_team_id == team_id or match.away_team_id == team_id:
                    raise ValueError("This team is already assigned to this match.")

                if slot == 'home':
                    match.home_team_id = team_id
                elif slot == 'away':
                    match.away_team_id = team_id
                else:
                    raise ValueError("Invalid slot specified. Must be 'home' or 'away'.")

                await session.commit()
                await session.refresh(match)
                return match.to_json()

            except IntegrityError as e:
                await session.rollback()
                if "check_home_and_away_not_same" in str(e.orig):
                    raise ValueError("A team cannot be both home and away in the same match.")
                raise
            except Exception:
                await session.rollback()
                raise
            
    async def update_match_connections(self, match_id: str, data: dict) -> dict:
        async with AsyncSession() as session:
            match = await session.get(LeagueMatchModel, match_id)
            if not match:
                raise ValueError(f"Match with ID {match_id} not found.")
            
            for key, value in data.items():
                if hasattr(match, key):
                    setattr(match, key, value)
            
            await session.commit()
            await session.refresh(match)
            return match.to_json()

    async def update_node_position(self, node_id: str, node_type: str, position: dict) -> bool:
        async with AsyncSession() as session:
            model_map = {
                "leagueCategory": LeagueCategoryModel,
                "leagueCategoryRound": LeagueCategoryRoundModel,
                "group": LeagueGroupModel,
                "leagueMatch": LeagueMatchModel
            }
            model = model_map.get(node_type)

            if not model:
                raise ValueError(f"Unknown node type: {node_type}")

            pk_column_name = list(model.__table__.primary_key.columns)[0].name
            
            stmt = select(model).where(getattr(model, pk_column_name) == node_id)
            
            result = await session.execute(stmt)
            node_to_update = result.scalar_one_or_none()

            if node_to_update:
                node_to_update.position = position
                await session.commit()
                return True
                
            return False

    async def delete_category_with_cascade(self, category_id: str) -> bool:
        async with AsyncSession() as session:
            category_to_delete = await session.get(LeagueCategoryModel, category_id)
            if not category_to_delete:
                return False
            
            await session.delete(category_to_delete)
            await session.commit()
            return True

    async def delete_edge(self, edge_id: str) -> bool:
        async with AsyncSession() as session:
            stmt = delete(LeagueFlowEdgeModel).where(LeagueFlowEdgeModel.edge_id == edge_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def delete_single_node(self, node_id: str, node_type: str) -> bool:
        async with AsyncSession() as session:
            model_map = {
                "leagueCategoryRound": LeagueCategoryRoundModel,
                "group": LeagueGroupModel,
                "leagueMatch": LeagueMatchModel
            }
            model = model_map.get(node_type)
            if not model:
                raise ValueError(f"Invalid node type for single deletion: {node_type}")
            
            pk_column = getattr(model, list(model.__table__.primary_key.columns)[0].name)
            stmt = delete(model).where(pk_column == node_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def synchronize_bracket(self, league_category_id: str) -> dict:
        async with AsyncSession() as session, session.begin():
            
            total_teams_stmt = select(func.count(LeagueTeamModel.league_team_id)).where(
                LeagueTeamModel.league_category_id == league_category_id
            )
            total_teams_count = (await session.execute(total_teams_stmt)).scalar_one() or 0

            resolved_matches_stmt = select(LeagueMatchModel).where(
                LeagueMatchModel.league_category_id == league_category_id,
                LeagueMatchModel.winner_team_id.isnot(None)
            )
            edges_stmt = select(LeagueFlowEdgeModel).where(LeagueFlowEdgeModel.league_category_id == league_category_id)
            resolved_matches = (await session.execute(resolved_matches_stmt)).scalars().all()
            edges = (await session.execute(edges_stmt)).scalars().all()

            edge_map = {}
            for edge in edges:
                if edge.source_node_id not in edge_map:
                    edge_map[edge.source_node_id] = []
                edge_map[edge.source_node_id].append(edge)

            progressed_teams_count = 0
            eliminated_teams_count = 0
            ranked_teams_count = 0
            
            for match in resolved_matches:
                outgoing_edges = edge_map.get(match.league_match_id, [])
                for edge in outgoing_edges:
                    team_to_progress = None
                    if 'winner' in edge.source_handle and match.winner_team_id:
                        team_to_progress = match.winner_team_id
                    elif 'loser' in edge.source_handle and match.loser_team_id:
                        team_to_progress = match.loser_team_id

                    if team_to_progress:
                        next_match = await session.get(LeagueMatchModel, edge.target_node_id)
                        if next_match and team_to_progress not in [next_match.home_team_id, next_match.away_team_id]:
                            if next_match.home_team_id is None:
                                next_match.home_team_id = team_to_progress
                                progressed_teams_count += 1
                            elif next_match.away_team_id is None:
                                next_match.away_team_id = team_to_progress
                                progressed_teams_count += 1
                
                winner_id = match.winner_team_id
                loser_id = match.loser_team_id

                if match.is_elimination and loser_id:
                    loser_team = await session.get(LeagueTeamModel, loser_id)
                    
                    if loser_team and not loser_team.is_eliminated and loser_team.final_rank is None:
                        loser_team.is_eliminated = True
                        loser_team.eliminated_in_round_id = match.round_id
                        
                        already_ranked_stmt = select(func.count(LeagueTeamModel.league_team_id)).where(
                            LeagueTeamModel.league_category_id == league_category_id,
                            LeagueTeamModel.is_eliminated == True,
                            LeagueTeamModel.final_rank.isnot(None)
                        )
                        already_ranked_count = (await session.execute(already_ranked_stmt)).scalar_one() or 0
                        
                        loser_team.final_rank = total_teams_count - already_ranked_count
                        
                        eliminated_teams_count += 1
                        ranked_teams_count += 1 

                if match.is_final and winner_id and loser_id:
                    champion_team = await session.get(LeagueTeamModel, winner_id)
                    if champion_team:
                        champion_team.is_champion = True
                        champion_team.final_rank = 1
                        ranked_teams_count += 1
                    
                    runner_up_team = await session.get(LeagueTeamModel, loser_id)
                    if runner_up_team:
                        runner_up_team.final_rank = 2
                        ranked_teams_count += 1

                elif match.is_third_place and winner_id and loser_id:
                    third_place_team = await session.get(LeagueTeamModel, winner_id)
                    if third_place_team:
                        third_place_team.final_rank = 3
                        ranked_teams_count += 1
                    
                    fourth_place_team = await session.get(LeagueTeamModel, loser_id)
                    if fourth_place_team:
                        fourth_place_team.final_rank = 4
                        ranked_teams_count += 1
                
            await session.commit()
           
            return {"teams_progressed": progressed_teams_count}