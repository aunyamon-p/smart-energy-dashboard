from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import Base, engine, ensure_schema_compatibility
from .routes import router


settings = get_settings()
if settings.app_env.lower() != "production":
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()

app = FastAPI(title="Smart Energy Intelligence API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
