import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://adrianmoses@localhost:5432/comprende_ya")
    DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"

    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

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
