from quart import Blueprint, jsonify, request
from src.services.cloudinary_service import CloudinaryService
from src.extensions import DATA_DIR
import json
from typing import Any, Union

static_data_bp = Blueprint("static-data", __name__, url_prefix='/static-data')

class StaticDataHandler:
    @staticmethod
    def load_json(filename: str) -> Union[list[Any], dict[str, Any]]:
        file_path = DATA_DIR / filename
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    @static_data_bp.get('/barangays')
    async def list_of_brgys():
        data = StaticDataHandler.load_json("barangay_list.json")
        return jsonify(data)
    
    @staticmethod
    @static_data_bp.get('/league-categories')
    async def list_of_league_categories():
        data = StaticDataHandler.load_json("league_categories.json")
        return jsonify(data)
    
    @staticmethod
    @static_data_bp.get('/organization-types')
    async def list_of_organization_types():
        data = StaticDataHandler.load_json("organization_types.json")
        return jsonify(data)
    
    @staticmethod
    @static_data_bp.post('/images')
    async def list_images():
        data = await request.get_json()
        data = await CloudinaryService.get_folder_urls(data=data)
        return jsonify(data)