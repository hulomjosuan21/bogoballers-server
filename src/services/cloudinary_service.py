import os
import asyncio
from urllib.parse import urlparse
from werkzeug.datastructures import FileStorage

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

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
            raise Exception(f"Upload failed: {str(e)}")

    @staticmethod
    async def delete_file_by_url(file_url: str) -> bool:
        try:
            from urllib.parse import urlparse
            SAMPLE_TEAM_LOGO_URL = os.getenv("SAMPLE_TEAM_LOGO_URL")
            SAMPLE_LEAGUE_ADMIN_LOGO_URL = os.getenv("SAMPLE_LEAGUE_ADMIN_LOGO_URL")
            SAMPLE_PLAYER_PROFILE_URL = os.getenv("SAMPLE_PLAYER_PROFILE_URL")

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
            raise Exception(f"Delete failed: {str(e)}")
