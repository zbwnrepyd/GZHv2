import os
from pathlib import Path
from dataclasses import dataclass

# 尝试加载 ~/.env，不存在则跳过
env_path = Path.home() / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                # 去掉引号
                value = value.strip().strip('"').strip("'")
                if key not in os.environ:
                    os.environ[key] = value


@dataclass
class Config:
    DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
    TAVILY_API_KEY: str = os.environ.get("TAVILY_API_KEY", "")
    YOUTUBE_API_KEY: str = os.environ.get("YOUTUBE_API_KEY", "")
    IMAGE_API_KEY: str = os.environ.get("IMAGE_API_KEY", "")
    IMAGE_API_URL: str = os.environ.get(
        "IMAGE_API_URL", "https://api.openai.com/v1/images/generations"
    )
    FLASK_PORT: int = int(os.environ.get("FLASK_PORT", "5050"))

    # 数据库路径，开发环境默认在当前项目 db/ 下
    DB_PATH_RESEARCH: str = os.environ.get(
        "DB_PATH_RESEARCH",
        str(Path(__file__).resolve().parent.parent / "db" / "research_db.sqlite"),
    )
    DB_PATH_FINAL: str = os.environ.get(
        "DB_PATH_FINAL",
        str(Path(__file__).resolve().parent.parent / "db" / "final_db.sqlite"),
    )
    IMAGES_DIR: str = os.environ.get(
        "IMAGES_DIR",
        str(Path(__file__).resolve().parent.parent / "images"),
    )

    # DeepSeek API
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/chat/completions"
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_FLASH_MODEL: str = "deepseek-v4-flash"


config = Config()
