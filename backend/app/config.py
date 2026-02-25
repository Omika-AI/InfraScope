from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    # Hetzner Cloud API
    hetzner_cloud_api_token: str = ""

    # Hetzner Robot API (for dedicated servers)
    hetzner_robot_user: str = ""
    hetzner_robot_password: str = ""

    # Agent authentication
    agent_secret: str = "change-me"

    # Collection intervals (seconds)
    collect_interval: int = 300       # 5 minutes
    analysis_interval: int = 3600     # 1 hour
    recommendation_interval: int = 86400  # 24 hours

    # Database
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'infrascope.db'}"

    # Demo mode
    demo_mode: bool = False

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = {
        "env_file": [BASE_DIR / ".env", BASE_DIR.parent / ".env"],
        "env_file_encoding": "utf-8",
    }


settings = Settings()
