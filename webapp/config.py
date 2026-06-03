import os
from pathlib import Path
from dataclasses import dataclass, field


def _load_env_file(env_path: Path):
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = value


def _env_list(list_name: str, fallback_name: str = "") -> list[str]:
    raw = os.environ.get(list_name, "")
    if not raw and fallback_name:
        raw = os.environ.get(fallback_name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


# 优先级：系统环境变量 > 项目根目录 .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_load_env_file(PROJECT_ROOT / ".env")


@dataclass
class Config:
    DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
    TAVILY_API_KEY: str = os.environ.get("TAVILY_API_KEY", "")
    TAVILY_API_KEYS: list[str] = field(
        default_factory=lambda: _env_list("TAVILY_API_KEYS", "TAVILY_API_KEY")
    )
    YOUTUBE_API_KEY: str = os.environ.get("YOUTUBE_API_KEY", "")
    GOOGLE_MAPS_API_KEY: str = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    PEXELS_API_KEY: str = os.environ.get("PEXELS_API_KEY", "")
    UNSPLASH_ACCESS_KEY: str = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    SCREENSHOT_PROVIDER: str = os.environ.get("SCREENSHOT_PROVIDER", "local")
    SCREENSHOT_API_URL: str = os.environ.get("SCREENSHOT_API_URL", "")
    SCREENSHOT_API_KEY: str = os.environ.get("SCREENSHOT_API_KEY", "")
    IMAGE_API_KEY: str = os.environ.get("IMAGE_API_KEY", "")
    IMAGE_API_URL: str = os.environ.get(
        "IMAGE_API_URL", "https://api.openai.com/v1/images/generations"
    )
    FLASK_PORT: int = int(os.environ.get("FLASK_PORT", "5050"))

    # 数据库路径，开发环境默认在当前项目 db/ 下
    DB_PATH_RESEARCH: str = os.environ.get(
        "DB_PATH_RESEARCH",
        str(PROJECT_ROOT / "db" / "research_db.sqlite"),
    )
    DB_PATH_FINAL: str = os.environ.get(
        "DB_PATH_FINAL",
        str(PROJECT_ROOT / "db" / "final_db.sqlite"),
    )
    DB_PATH_ASSETS: str = os.environ.get(
        "DB_PATH_ASSETS",
        str(PROJECT_ROOT / "db" / "assets_db.sqlite"),
    )
    IMAGES_DIR: str = os.environ.get(
        "IMAGES_DIR",
        str(PROJECT_ROOT / "images"),
    )

    # Playwright
    PLAYWRIGHT_CHROMIUM_PATH: str = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", "")

    # DeepSeek API
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/chat/completions"
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_FLASH_MODEL: str = "deepseek-v4-flash"


config = Config()
