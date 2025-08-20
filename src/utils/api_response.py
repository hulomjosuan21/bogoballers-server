from quart import jsonify, make_response, Response
from sqlalchemy.exc import IntegrityError, DataError, OperationalError
from werkzeug.exceptions import NotFound
class ApiException(Exception):
    def __init__(self, message="An error occurred", code=400):
        self.message = message
        self.status_code = code
        super().__init__(message)
class ApiResponse:
    @staticmethod
    def success(redirect=None,message="Success", payload=None, status_code=200):
        response = {
            "status": True,
            "message": message,
        }
        if payload is not None:
            response["payload"] = payload
        if redirect is not None:
            response["redirect"] = redirect
            
        return make_response(jsonify(response), status_code)
    
    @staticmethod
    async def success_with_cookie(message: str, cookies: dict) -> Response:
        response = jsonify({"success": True, "message": message})
        for name, options in cookies.items():
            response.set_cookie(
                key=name,
                value=options["value"],
                httponly=options.get("httponly", True),
                secure=options.get("secure", True),
                samesite=options.get("samesite", "Lax"),
                max_age=options.get("max-age"),
                path=options.get("path", "/"),
                domain=options.get("domain")
            )
        return response
    
    @staticmethod
    def payload(payload, status_code=200):
        return make_response(jsonify(payload), status_code)
    
    @staticmethod
    def html(template=None, status_code=200):
        return make_response(template, status_code)

    @staticmethod
    def error(error="An error occurred", status_code=None):
        message = "An error occurred"
        code = 500

        if isinstance(error, ApiException):
            message = error.message
            code = error.status_code
        elif isinstance(error, IntegrityError):
            message = "Duplicate entry or constraint violation"
            code = 409
        elif isinstance(error, DataError):
            message = "Invalid data format or length"
            code = 400
        elif isinstance(error, NotFound):
            message = "Resource not found"
            code = 404
        elif isinstance(error, OperationalError):
            message = "Database operational error"
            code = 503
        else:
            message = str(error) or message

        if status_code is not None:
            code = status_code

        response = {"status": False, "message": message}
        return make_response(jsonify(response), code)