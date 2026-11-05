"""Tests xác thực link YouTube (services/training/youtube.py) — hàm thuần, không gọi mạng."""
import pytest

from services.training.youtube import InvalidVideoUrl, canonical_url, parse_youtube_url

VID = "aB3_-9xYz0Q"
CANON = f"https://www.youtube.com/watch?v={VID}"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VID}",
    f"https://youtube.com/watch?v={VID}",
    f"https://m.youtube.com/watch?v={VID}",
    f"https://www.youtube.com/watch?v={VID}&t=30s&list=PL123",
    f"https://www.youtube.com/watch?feature=share&v={VID}",
    f"https://youtu.be/{VID}",
    f"https://youtu.be/{VID}?si=abcDEF&t=10",
    f"https://www.youtube.com/shorts/{VID}",
    f"https://youtube.com/shorts/{VID}/",
    f"https://www.youtube.com/watch?v={VID}#t=10",
    f"HTTPS://WWW.YOUTUBE.COM/watch?v={VID}",
])
def test_accepts_supported_forms(url):
    assert parse_youtube_url(url) == (VID, CANON)


def test_canonical_url():
    assert canonical_url(VID) == CANON


@pytest.mark.parametrize("url", [
    f"javascript:alert(1)//https://www.youtube.com/watch?v={VID}",
    "javascript:alert(document.cookie)",
    f"data:text/html,https://youtu.be/{VID}",
    f"http://www.youtube.com/watch?v={VID}",
    f"http://youtu.be/{VID}",
    f"//www.youtube.com/watch?v={VID}",
    f"www.youtube.com/watch?v={VID}",
    f"https://youtube.com@evil.com/watch?v={VID}",
    f"https://user:pass@www.youtube.com/watch?v={VID}",
    f"https://evil.com/watch?v={VID}",
    f"https://www.youtube.com.evil.com/watch?v={VID}",
    f"https://evilyoutube.com/watch?v={VID}",
    f"https://youtube.co/watch?v={VID}",
    f"https://music.youtube.com/watch?v={VID}",
    f"https://www.youtube-nocookie.com/embed/{VID}",
    f"https://evil.com#@www.youtube.com/watch?v={VID}",
    f"https://www.youtube.com:8443/watch?v={VID}",
    f"https://www.youtube.com/embed/{VID}",
    f"https://www.youtube.com/playlist?list=PL{VID}",
    "https://www.youtube.com/@kenh",
    f"https://www.youtube.com/watch?v={VID}&v=bbbbbbbbbbb",
    "https://www.youtube.com/watch",
    f"https://youtu.be/{VID}/extra",
    f"https://youtu.be/",
    f"https://www.youtube.com/watch?v= {VID}",
    f" https://www.youtube.com/watch?v={VID}",
    f"https://www.youtube.com/watch?v={VID}\n",
    f"https:\\\\www.youtube.com\\watch?v={VID}",
    f"https://www.yoütube.com/watch?v={VID}",
    "",
])
def test_rejects_other_urls(url):
    with pytest.raises(InvalidVideoUrl):
        parse_youtube_url(url)


@pytest.mark.parametrize("bad_id", ["aB3_-9xYz0", "aB3_-9xYz0QQ", "aB3_-9xYz0!", "aB3_-9xYz0%", "aB3 -9xYz0Q", ""])
def test_rejects_wrong_id(bad_id):
    for url in (f"https://www.youtube.com/watch?v={bad_id}", f"https://youtu.be/{bad_id}",
                f"https://www.youtube.com/shorts/{bad_id}"):
        with pytest.raises(InvalidVideoUrl):
            parse_youtube_url(url)


def test_rejects_non_string_and_too_long():
    with pytest.raises(InvalidVideoUrl):
        parse_youtube_url(None)  # type: ignore[arg-type]
    with pytest.raises(InvalidVideoUrl):
        parse_youtube_url(f"https://www.youtube.com/watch?v={VID}&x=" + "a" * 600)
