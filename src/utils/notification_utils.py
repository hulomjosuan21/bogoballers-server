from typing import Dict, List, Optional
from dataclasses import dataclass
from sqlalchemy import select
from src.models.player import LeaguePlayerModel, PlayerModel, PlayerTeamModel
from src.models.match import LeagueMatchModel
from src.models.team import LeagueTeamModel, TeamModel
from sqlalchemy.orm import joinedload

@dataclass(frozen=True, slots=True)
class FCMUser:
    user_id: str
    fcm_token: str

@dataclass(frozen=True, slots=True)
class MatchFCMRecipients:
    home: List[FCMUser]
    away: List[FCMUser]

async def get_valid_fcm_for_match(
    session,
    league_match_id: str,
    limit: Optional[int] = None
) -> MatchFCMRecipients:
    result = await session.execute(
        select(LeagueMatchModel)
        .options(
            joinedload(LeagueMatchModel.home_team)
            .joinedload(LeagueTeamModel.team)
            .joinedload(TeamModel.user),
            joinedload(LeagueMatchModel.home_team)
            .selectinload(LeagueTeamModel.league_players)
            .joinedload(LeaguePlayerModel.player_team)
            .joinedload(PlayerTeamModel.player)
            .joinedload(PlayerModel.user),

            joinedload(LeagueMatchModel.away_team)
            .joinedload(LeagueTeamModel.team)
            .joinedload(TeamModel.user),
            joinedload(LeagueMatchModel.away_team)
            .selectinload(LeagueTeamModel.league_players)
            .joinedload(LeaguePlayerModel.player_team)
            .joinedload(PlayerTeamModel.player)
            .joinedload(PlayerModel.user),
        )
        .where(LeagueMatchModel.league_match_id == league_match_id)
    )

    match = result.scalars().first()
    if not match:
        return MatchFCMRecipients(home=[], away=[])

    home_candidates = []
    away_candidates = []
    seen = set()

    def collect(user, target_list):
        if not user or not user.user_id or user.user_id in seen:
            return
        if not user.fcm_token or not user.fcm_token.strip():
            return
        if user.user_id in seen:
            return
        seen.add(user.user_id)
        target_list.append(FCMUser(user_id=user.user_id, fcm_token=user.fcm_token.strip()))

    for league_team, target in [
        (match.home_team, home_candidates),
        (match.away_team, away_candidates)
    ]:
        if not league_team or not league_team.team:
            continue
        collect(league_team.team.user, target)
        for lp in league_team.league_players:
            pt = lp.player_team
            if pt and pt.player and pt.player.user and pt.is_accepted in ("Accepted", "Guest"):
                collect(pt.player.user, target)

    home_users: List[FCMUser] = []
    away_users: List[FCMUser] = []

    i, j = 0, 0
    while (i < len(home_candidates) or j < len(away_candidates)):
        if limit is not None and len(home_users) + len(away_users) >= limit:
            break

        if i < len(home_candidates):
            home_users.append(home_candidates[i])
            i += 1

        if limit is not None and len(home_users) + len(away_users) >= limit:
            break

        if j < len(away_candidates):
            away_users.append(away_candidates[j])
            j += 1

    return MatchFCMRecipients(home=home_users, away=away_users)