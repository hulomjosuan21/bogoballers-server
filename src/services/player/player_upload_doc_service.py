import traceback
from typing import List
from quart import request
from sqlalchemy import select
from src.services.cloudinary_service import CloudinaryService
from src.models.player_valid_documents import PlayerValidDocument
from src.extensions import AsyncSession
from werkzeug.datastructures import FileStorage
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from src.utils.api_response import ApiException

class PlayerUploadDocService:
    async def upload(self, player_id: str):
        try:
            form = await request.form
            files: List[FileStorage] = (await request.files).getlist("files")

            document_type = form.get("document_type")
            document_format = form.get("document_format", "single")

            if not document_type:
                raise ApiException("Document type is required.")

            if not files or len(files) == 0:
                raise ApiException("At least one image file is required.")

            uploaded_urls = []

            async with AsyncSession() as session:
                stmt = select(PlayerValidDocument).where(
                    PlayerValidDocument.player_id == player_id,
                    PlayerValidDocument.document_type == document_type,
                )
                result = await session.execute(stmt)
                existing_doc = result.scalar_one_or_none()

                for file in files:
                    url = await CloudinaryService.upload_file(
                        file=file,
                        folder="valid_doc",
                        resource_type="image"
                    )
                    uploaded_urls.append(url)

                if existing_doc:
                    if existing_doc.document_urls:
                        for old_url in existing_doc.document_urls:
                            if CloudinaryService.is_cloudinary_url(old_url):
                                try:
                                    await CloudinaryService.delete_file_by_url(old_url)
                                except Exception:
                                    traceback.print_exc()

                    existing_doc.document_urls = uploaded_urls
                    existing_doc.document_format = document_format
                    await session.commit()

                    return f"{document_type} replaced successfully."

                new_doc = PlayerValidDocument(
                    player_id=player_id,
                    document_type=document_type,
                    document_urls=uploaded_urls,
                    document_format=document_format,
                )
                session.add(new_doc)
                await session.commit()

                return f"{document_type} uploaded successfully."
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e