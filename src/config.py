import os

from dotenv import load_dotenv

load_dotenv()

# Orígenes permitidos por defecto en desarrollo (frontend en :3000). En
# producción se sobreescriben con ALLOWED_ORIGINS (033 — deployment readiness).
DEFAULT_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://0.0.0.0:3000",
]


def parse_allowed_origins(raw: str | None) -> list[str]:
    """Convierte ALLOWED_ORIGINS (lista separada por comas) en orígenes CORS.

    Sin valor (o sólo espacios) cae a los orígenes de desarrollo, de modo que
    `pnpm dev` sigue funcionando sin configuración. Tolera espacios y comas
    sobrantes. Nunca usar "*": la app envía `allow_credentials=True`.
    """
    if not raw or not raw.strip():
        return list(DEFAULT_DEV_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class Settings:
    # API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://adrianmoses@localhost:5432/comprende_ya")
    DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"

    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

    # CORS (033). Lista separada por comas del/los origen(es) público(s) del
    # frontend. Debe ser el origen accesible desde el navegador, NO el nombre
    # interno del servicio de compose (p. ej. http://api:8000).
    ALLOWED_ORIGINS = parse_allowed_origins(os.getenv("ALLOWED_ORIGINS"))

    # Modelos Claude (026). Un nivel de "generación" para preguntas/marcadores/
    # autopsias/consignas, y uno más barato de "clasificación" para el dialecto.
    CLAUDE_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    CLAUDE_MODEL_CLASSIFY = os.getenv("ANTHROPIC_MODEL_CLASSIFY", "claude-haiku-4-5")

    # Validar que existen las API keys
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY no está configurado")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not está configurado")
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY no está configurado")

    # Directorios
    TEMP_DIR = "temp"
    RECORDINGS_DIR = os.getenv("RECORDINGS_DIR", "recordings")  # grabaciones de Mis frases (021)
    MAX_VIDEO_DURATION = 3600  # 1 hour


settings = Settings()


os.makedirs(settings.TEMP_DIR, exist_ok=True)
os.makedirs(settings.RECORDINGS_DIR, exist_ok=True)
