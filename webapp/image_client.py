import base64
import time
import requests
from pathlib import Path
from config import config


def generate_image(prompt: str, save_dir: str = None, filename: str = None) -> str:
    """调用 AI 图片生成 API，保存到本地，返回文件路径"""
    if save_dir is None:
        save_dir = config.IMAGES_DIR
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    if filename is None:
        timestamp = int(time.time() * 1000)
        filename = f"img_{timestamp}.png"
    save_path = str(Path(save_dir) / filename)

    headers = {
        "Authorization": f"Bearer {config.IMAGE_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "dall-e-3",
        "prompt": f"{prompt}. Clean, professional, no watermark, suitable for social media card.",
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json",
    }

    resp = requests.post(config.IMAGE_API_URL, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    # 尝试多种响应格式
    b64 = None
    if "data" in data and data["data"]:
        b64 = data["data"][0].get("b64_json")
    if not b64:
        raise RuntimeError(f"图片 API 返回格式异常: {data}")

    with open(save_path, "wb") as f:
        f.write(base64.b64decode(b64))

    return save_path
