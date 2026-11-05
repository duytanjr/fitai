"""Xác thực link YouTube cho video bài tập (hàm thuần, không gọi mạng).

Chỉ nhận https, host đúng một trong ALLOWED_HOSTS (so khớp nguyên chuỗi, không theo hậu tố), không userinfo,
không port; rút youtube_id từ /watch?v=, youtu.be/<id> hoặc /shorts/<id>. Mọi dạng khác bị từ chối.
"""
import re
from urllib.parse import parse_qs, urlsplit

ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
YOUTUBE_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")
CANONICAL = "https://www.youtube.com/watch?v={}"
MAX_URL_LEN = 500


class InvalidVideoUrl(ValueError):
    pass


def canonical_url(youtube_id: str) -> str:
    return CANONICAL.format(youtube_id)


def _video_id(value: str | None) -> str:
    if value is None or not YOUTUBE_ID_RE.fullmatch(value):
        raise InvalidVideoUrl("youtube_id phải gồm đúng 11 ký tự A-Z a-z 0-9 _ -")
    return value


def parse_youtube_url(url: str) -> tuple[str, str]:
    """Trả (youtube_id, url chuẩn https://www.youtube.com/watch?v=<id>); sai thì ném InvalidVideoUrl."""
    if not isinstance(url, str) or not url:
        raise InvalidVideoUrl("thiếu url")
    if len(url) > MAX_URL_LEN:
        raise InvalidVideoUrl("url quá dài")
    if not url.isascii() or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in url) or "\\" in url:
        raise InvalidVideoUrl("url chứa khoảng trắng, ký tự điều khiển hoặc ký tự không hợp lệ")
    if not url.lower().startswith("https://"):
        raise InvalidVideoUrl("chỉ chấp nhận link https://")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise InvalidVideoUrl("url không phân tích được") from exc
    netloc = parts.netloc.lower()
    if "@" in netloc or port is not None or ":" in netloc:
        raise InvalidVideoUrl("url không được chứa thông tin đăng nhập hay cổng")
    if netloc not in ALLOWED_HOSTS:
        raise InvalidVideoUrl("host không phải YouTube")

    path = parts.path
    if netloc == "youtu.be":
        segments = path.split("/")
        if len(segments) != 2 or segments[0] != "":
            raise InvalidVideoUrl("dạng youtu.be phải là https://youtu.be/<id>")
        return _ok(segments[1])
    if path in ("/watch", "/watch/"):
        values = parse_qs(parts.query, keep_blank_values=True).get("v", [])
        if len(values) != 1:
            raise InvalidVideoUrl("link watch phải có đúng một tham số v")
        return _ok(values[0])
    match = re.fullmatch(r"/shorts/([^/]*)/?", path)
    if match:
        return _ok(match.group(1))
    raise InvalidVideoUrl("chỉ nhận dạng /watch?v=, youtu.be/ hoặc /shorts/")


def _ok(candidate: str) -> tuple[str, str]:
    youtube_id = _video_id(candidate)
    return youtube_id, canonical_url(youtube_id)
