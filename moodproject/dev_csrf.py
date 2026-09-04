"""
Dev-only CSRF middleware: trusts any localhost / 127.0.0.1 origin (any port)
when DEBUG=True. Useful for the Windsurf browser-preview proxy which uses a
random port on each run. Never enable this in production.
"""
from urllib.parse import urlparse
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware


_LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "[::1]"}


def _is_local_origin(origin: str) -> bool:
    if not origin:
        return False
    try:
        host = urlparse(origin).hostname
    except Exception:
        return False
    return host in _LOCAL_HOSTS


class DevPermissiveCsrfMiddleware(CsrfViewMiddleware):
    """Allow any localhost origin while DEBUG=True; otherwise behave normally.

    Also bypasses CSRF token verification entirely when the request comes from
    a local origin in DEBUG mode (useful for browser-preview proxies whose
    random ports invalidate session cookies).
    """

    def _origin_verified(self, request):
        if settings.DEBUG:
            origin = request.META.get("HTTP_ORIGIN")
            if _is_local_origin(origin):
                return True
        return super()._origin_verified(request)

    def process_view(self, request, callback, callback_args, callback_kwargs):
        if settings.DEBUG:
            origin = request.META.get("HTTP_ORIGIN") or request.META.get("HTTP_REFERER")
            host = request.get_host().split(":")[0]
            if _is_local_origin(origin) or host in _LOCAL_HOSTS:
                return None
        return super().process_view(request, callback, callback_args, callback_kwargs)


class ForceUtf8ContentTypeMiddleware:
    """Ensure every HTML response advertises charset=utf-8.

    Some reverse-proxies (e.g. dev browser-preview tunnels) strip the charset
    parameter, which causes browsers to fall back to Latin-1 and renders
    UTF-8 characters like the curly apostrophe (’) as mojibake (â€™).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        ctype = response.get("Content-Type", "")
        if ctype.startswith("text/html") and "charset" not in ctype.lower():
            response["Content-Type"] = "text/html; charset=utf-8"
        return response
