from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "app_error"
    message = "Ocurrió un error."

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "No se encontró el recurso solicitado."


class DomainValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Los datos enviados no son válidos."


class IncompleteInformationError(AppError):
    status_code = 422
    code = "incomplete_information"
    message = "Falta información para completar la operación."


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_error"
    message = "Credenciales inválidas."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "El recurso ya existe."


class InvalidFileError(AppError):
    status_code = 415
    code = "invalid_file"
    message = "El archivo no es válido o su formato no está soportado."


class ProcessingError(AppError):
    status_code = 500
    code = "processing_error"
    message = "No se pudo procesar la solicitud."


class AIUnavailableError(AppError):
    status_code = 503
    code = "ai_unavailable"
    message = "El servicio de IA no está disponible en este momento."


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
