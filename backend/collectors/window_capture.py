from __future__ import annotations

import base64
import ctypes
import io
from dataclasses import dataclass

import mss
from PIL import Image

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int


def list_windows() -> list[WindowInfo]:
    if user32 is None:
        return []

    windows: list[WindowInfo] = []

    def callback(hwnd: int, _: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if not title:
            return True
        if title in {"Program Manager", "Windows 输入体验", "设置"}:
            return True
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
        width = max(0, right - left)
        height = max(0, bottom - top)
        if width < 300 or height < 200:
            return True
        windows.append(WindowInfo(hwnd, title, left, top, width, height))
        return True

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)(callback)
    user32.EnumWindows(enum_proc, 0)
    return sorted(windows, key=lambda item: item.title)


def find_window(keyword: str, hwnd: int | None = None) -> WindowInfo | None:
    all_windows = list_windows()
    if hwnd:
        for item in all_windows:
            if item.hwnd == hwnd:
                return item
    keyword = (keyword or "").lower().strip()
    if not keyword:
        return None
    for item in all_windows:
        if keyword in item.title.lower():
            return item
    return None


def capture_window(hwnd: int) -> tuple[Image.Image, WindowInfo]:
    info = find_window("", hwnd=hwnd)
    if info is None:
        raise ValueError("window_not_found")
    with mss.mss() as sct:
        shot = sct.grab(
            {
                "left": info.left,
                "top": info.top,
                "width": info.width,
                "height": info.height,
            }
        )
    image = Image.frombytes("RGB", shot.size, shot.rgb)
    return image, info


def crop_by_ratio(
    image: Image.Image,
    x_ratio: float,
    y_ratio: float,
    width_ratio: float,
    height_ratio: float,
    safety_margin: float,
) -> tuple[Image.Image, dict[str, int]]:
    safety_margin = max(0.0, min(0.08, float(safety_margin or 0.0)))
    img_w, img_h = image.size
    x = int(x_ratio * img_w)
    y = int(y_ratio * img_h)
    w = int(width_ratio * img_w)
    h = int(height_ratio * img_h)
    margin_x = int(w * safety_margin)
    margin_y = int(h * safety_margin)
    left = max(0, x - margin_x)
    top = max(0, y - margin_y)
    right = min(img_w, x + w + margin_x)
    bottom = min(img_h, y + h + margin_y)
    return image.crop((left, top, right, bottom)), {
        "x": left,
        "y": top,
        "width": max(1, right - left),
        "height": max(1, bottom - top),
    }


def image_to_data_url(image: Image.Image, max_width: int | None = None) -> str:
    if max_width and image.width > max_width:
        scale = max_width / image.width
        image = image.resize((max_width, int(image.height * scale)))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def save_thumbnail(image: Image.Image, path: str, max_width: int = 480) -> None:
    if image.width > max_width:
        scale = max_width / image.width
        image = image.resize((max_width, int(image.height * scale)))
    image.save(path, format="PNG")
