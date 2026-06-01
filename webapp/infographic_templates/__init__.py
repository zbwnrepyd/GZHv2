"""SVG 信息图模板加载 / 注册 / 上传管理"""
import importlib.util
import re
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent
_USER_DIR = _TEMPLATE_DIR / "_user_uploaded"
_USER_DIR.mkdir(exist_ok=True)

_registry: dict[str, object] = {}
_SAFE_TEMPLATE_FILENAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*\.py$")


def _load_file(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _register(path: Path):
    try:
        m = _load_file(path)
        if hasattr(m, "META") and hasattr(m, "build"):
            _registry[m.META["id"]] = m
    except Exception as e:
        print(f"[templates] 加载失败 {path.name}: {e}")


def load_all():
    """扫描内置模板目录，注册全部模板。"""
    _registry.clear()
    for path in sorted(_TEMPLATE_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        _register(path)


def get_all() -> list[dict]:
    """返回全部模板的 META 列表"""
    return [m.META for m in _registry.values()]


def get(template_id: str):
    """获取模板 module；未找到返回 None"""
    return _registry.get(template_id)


def upload(filename: str, content: bytes) -> dict:
    """保存用户上传的模板文件，验证后注册。返回 META 或抛出 ValueError。"""
    if not filename or not _SAFE_TEMPLATE_FILENAME.match(filename):
        raise ValueError("模板文件名只能包含英文字母、数字、下划线、点和连字符，并且必须以 .py 结尾")
    if not content:
        raise ValueError("模板文件为空")

    _USER_DIR.mkdir(exist_ok=True)
    dest = _USER_DIR / filename
    dest.write_bytes(content)
    try:
        m = _load_file(dest)
        if not hasattr(m, "META") or not hasattr(m, "build"):
            dest.unlink()
            raise ValueError("模板文件缺少 META 或 build 函数")
        if not isinstance(m.META, dict) or not m.META.get("id") or not m.META.get("asset_key"):
            dest.unlink()
            raise ValueError("模板 META 必须包含 id 和 asset_key")
        m.META["builtin"] = False
        m.__template_path__ = dest
        _registry[m.META["id"]] = m
        return m.META
    except ValueError:
        raise
    except Exception as e:
        if dest.exists():
            dest.unlink()
        raise ValueError(f"模板解析失败：{e}")


def delete(template_id: str) -> bool:
    """删除用户上传的模板（内置模板不可删）"""
    m = _registry.get(template_id)
    if not m or m.META.get("builtin"):
        return False
    path = Path(getattr(m, "__template_path__", _USER_DIR / f"{template_id}.py"))
    if path.exists() and path.resolve().parent == _USER_DIR.resolve():
        path.unlink()
    del _registry[template_id]
    return True


# 模块加载时自动注册
load_all()
