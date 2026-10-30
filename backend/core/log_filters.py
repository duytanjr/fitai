"""Bộ lọc log: không để dữ liệu người dùng lọt vào log hệ thống."""
import logging


class StripQueryStringFilter(logging.Filter):
    """Bỏ query string khỏi access log của uvicorn.

    Query có thể chứa dữ liệu người dùng (vd. /foods?q=<từ khoá>, /meals?date=...).
    Bản ghi access của uvicorn có args = (client_addr, method, full_path, http_version, status).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], args[2].split("?", 1)[0], *args[3:])
        return True


def install_access_log_filter() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, StripQueryStringFilter) for f in access.filters):
        access.addFilter(StripQueryStringFilter())
