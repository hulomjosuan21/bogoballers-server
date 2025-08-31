import os
import asyncio
from urllib.parse import urlparse
from werkzeug.datastructures import FileStorage
from src.extensions import settings
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from datetime import datetime
import cloudinary.api

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

class CloudinaryException(Exception):
    def __init__(self, message="An error occurred", code=400):
        self.message = message
        self.status_code = code
        super().__init__(message)

class CloudinaryService:
    DEFAULT_FOLDER = "uploads"

    @staticmethod
    async def upload_file(file: FileStorage, folder: str = None, resource_type: str = "auto") -> str:
        folder = folder or CloudinaryService.DEFAULT_FOLDER

        try:
            response = await asyncio.to_thread(
                cloudinary.uploader.upload,
                file.stream,
                folder=folder,
                resource_type=resource_type
            )
            return response["secure_url"]
        except Exception as e:
            raise CloudinaryException(f"Upload failed")

    @staticmethod
    async def delete_file_by_url(file_url: str) -> bool:
        try:
            from urllib.parse import urlparse
            SAMPLE_TEAM_LOGO_URL = settings['default_team_logo']
            SAMPLE_LEAGUE_ADMIN_LOGO_URL = settings['default_league_admin_logo']
            SAMPLE_PLAYER_PROFILE_URL = settings['default_player_profile']

            if file_url in [SAMPLE_TEAM_LOGO_URL, SAMPLE_LEAGUE_ADMIN_LOGO_URL, SAMPLE_PLAYER_PROFILE_URL]:
                return True

            parsed_url = urlparse(file_url)
            path_parts = parsed_url.path.split("/")

            if "upload" not in path_parts:
                raise Exception("Invalid Cloudinary URL structure")

            upload_index = path_parts.index("upload")
            public_id_parts = path_parts[upload_index + 2:]
            if not public_id_parts:
                raise Exception("Could not extract public_id from URL")

            filename = public_id_parts[-1]
            ext = filename.rsplit(".", 1)[-1].lower()
            public_id_parts[-1] = filename.rsplit(".", 1)[0]
            public_id = "/".join(public_id_parts)

            if ext in ["jpg", "jpeg", "png", "gif", "webp"]:
                resource_type = "image"
            elif ext in ["mp4", "mov", "avi"]:
                resource_type = "video"
            else:
                resource_type = "raw"

            result = await asyncio.to_thread(
                cloudinary.uploader.destroy,
                public_id,
                resource_type=resource_type
            )

            return result.get("result") == "ok"
        except Exception as e:
            raise CloudinaryException(f"Delete failed")

    @staticmethod
    async def get_folder_urls(data: dict) -> list[str]:
        try:
            response = await asyncio.to_thread(
                cloudinary.api.resources,
                type="upload",
                prefix=data.get('folder'),
                max_results=data.get('limit'),
                direction="desc"
            )

            resources = response.get("resources", [])
            if data.get('start_datedata'):
                start_datetime = datetime.strptime(data.get('start_datedata'), "%Y-%m-%d").isoformat()
                resources = [r for r in resources if r["created_at"] >= start_datetime]

            return [r["secure_url"] for r in resources]

        except Exception as e:
            raise CloudinaryException(f"Fetch folder URLs failed: {str(e)}")