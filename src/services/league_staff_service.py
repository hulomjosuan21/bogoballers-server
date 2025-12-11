import traceback
from sqlalchemy import select
from src.extensions import AsyncSession
from src.models.league_admin import LeagueStaffModel
from src.utils.api_response import ApiException
from sqlalchemy.exc import IntegrityError

class LeagueStaffService:
    async def get_by_id(self, staff_id: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueStaffModel).where(LeagueStaffModel.staff_id == staff_id)
            )
            return result.scalar_one_or_none()

    async def get_all_by_admin(self, league_admin_id: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueStaffModel)
                .where(LeagueStaffModel.league_administrator_id == league_admin_id)
            )
            staff_list = result.scalars().all()
            return [staff.to_json() for staff in staff_list]

    async def create_one(self, data: dict, league_administrator_id: str):
        async with AsyncSession() as session:
            try:
                new_staff = LeagueStaffModel(
                    username=data.get("username"),
                    full_name=data.get("full_name"),
                    contact_info=data.get("contact_info"),
                    role_label=data.get("role_label", "Staff"),
                    assigned_permissions=data.get("permissions", []),
                    league_administrator_id=league_administrator_id
                )

                pin = data.get("pin")
                if not pin:
                    raise ApiException("A PIN is required to create a staff account")
                
                new_staff.set_pin(pin)

                session.add(new_staff)
                await session.commit()
                
                await session.refresh(new_staff)

                return new_staff.to_json()

            except IntegrityError:
                await session.rollback()
                raise ApiException("Username already exists", 409)
            except ValueError as ve:
                await session.rollback()
                raise ApiException(str(ve), 400)
            except Exception as e:
                await session.rollback()
                raise ApiException(f"Could not create staff: {str(e)}", 500)

    async def authenticate_login(self, username: str, pin: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueStaffModel).where(LeagueStaffModel.username == username)
            )
            staff = result.scalar_one_or_none()

            if not staff or not staff.verify_pin(pin):
                raise ApiException("Invalid username or PIN", 401)
            
            claims = {
                "username": staff.username,
                "role": staff.role_label,
                "account_type": "League_Staff",
                "permissions": staff.assigned_permissions
            }

            return staff, claims
        
    async def get_manifest_for_sync(self, admin_id: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueStaffModel)
                .where(LeagueStaffModel.league_administrator_id == admin_id)
            )
            staff_list = result.scalars().all()

            manifest = []
            for staff in staff_list:
                manifest.append({
                    "staff_id": staff.staff_id,
                    "username": staff.username,
                    "role_label": staff.role_label,
                    "permissions": staff.assigned_permissions,
                    "auth_hash": staff.pin_hash 
                })
            return manifest
    
    async def update_one(self, staff_id: str, data: dict):
   
        async with AsyncSession() as session:
            try:
                result = await session.execute(
                    select(LeagueStaffModel).where(LeagueStaffModel.staff_id == staff_id)
                )
                staff = result.scalar_one_or_none()

                if not staff:
                    raise ApiException("Staff member not found", 404)

                if "username" in data:
                    staff.username = data["username"]
                if "full_name" in data:
                    staff.full_name = data["full_name"]
                if "contact_info" in data:
                    staff.contact_info = data["contact_info"]
                if "role_label" in data:
                    staff.role_label = data["role_label"]
                if "permissions" in data:
                    staff.assigned_permissions = data["permissions"]
                
                if "pin" in data and data["pin"]:
                    staff.set_pin(data["pin"])

                await session.commit()
                await session.refresh(staff)
            except IntegrityError:
                await session.rollback()
                raise ApiException("Username already exists", 409)
            except Exception as e:
                await session.rollback()
                if isinstance(e, ApiException):
                    raise e
                raise ApiException(f"Could not update staff: {str(e)}", 500)

    async def delete_one(self, staff_id: str):
        async with AsyncSession() as session:
            try:
                result = await session.execute(
                    select(LeagueStaffModel).where(LeagueStaffModel.staff_id == staff_id)
                )
                staff = result.scalar_one_or_none()

                if not staff:
                    raise ApiException("Staff member not found", 404)
                await session.delete(staff)
                await session.commit()
                return True

            except Exception as e:
                await session.rollback()
                if isinstance(e, ApiException):
                    raise e
                raise ApiException(f"Could not delete staff: {str(e)}", 500)

    async def get_super_staff_status(self, league_admin_id: str):
        async with AsyncSession() as session:
            query = select(1).where(
                LeagueStaffModel.league_administrator_id == league_admin_id,
                LeagueStaffModel.is_super == True
            )
            result = await session.execute(query)
            return {"exists": result.scalar() is not None}

    async def create_super_staff(self, data: dict, league_administrator_id: str):
        async with AsyncSession() as session:
            existing = await session.execute(
                select(LeagueStaffModel).where(
                    LeagueStaffModel.league_administrator_id == league_administrator_id,
                    LeagueStaffModel.is_super == True
                )
            )
            if existing.scalar_one_or_none():
                raise ApiException("Super Staff already exists", 400)

            new_staff = LeagueStaffModel(
                username=data.get("username"),
                full_name=data.get("full_name"),
                contact_info=data.get("contact_info"),
                role_label="Super Admin",
                assigned_permissions=["ManageLeagueAdmins", "ScoreGames", "ManageTeams", "ViewReports"],
                league_administrator_id=league_administrator_id,
                is_super=True
            )
            
            new_staff.set_pin(data.get("pin"))
            
            session.add(new_staff)
            await session.commit()
            claims = {
                "username": new_staff.username,
                "role": new_staff.role_label,
                "account_type": "League_Staff",
                "permissions": new_staff.assigned_permissions
            }
            return new_staff, claims

    async def verify_super_staff_credentials(self, username: str, pin: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueStaffModel).where(
                    LeagueStaffModel.username == username
                )
            )
            staff = result.scalar_one_or_none()
            if not staff:
                raise ApiException("Invalid credentials", 401)
            if staff.is_super is False:
                raise ApiException("User is not a Super Staff", 403)

            if not staff.verify_pin(pin):
                raise ApiException("Invalid PIN", 401)
                
            return True