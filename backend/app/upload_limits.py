from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

MAX_REQUEST = 26 * 1024 * 1024


class UploadLimitMiddleware:
    """Bound multipart traffic, including chunked requests without Content-Length."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        if not headers.get(b"content-type", b"").lower().startswith(b"multipart/form-data"):
            return await self.app(scope, receive, send)
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = 0
        if length > MAX_REQUEST:
            return await JSONResponse({"detail": "Dosyaların toplam boyutu en fazla 25 MB olabilir."}, 413)(scope, receive, send)
        size, exceeded = 0, False

        async def bounded_receive():
            nonlocal size, exceeded
            message = await receive()
            size += len(message.get("body", b""))
            if size > MAX_REQUEST:
                exceeded = True
                # Multipart parser closes its temporary files on this exception.
                raise MultiPartException("Dosyaların toplam boyutu en fazla 25 MB olabilir.")
            return message

        async def bounded_send(message):
            if exceeded and message["type"] == "http.response.start":
                message = {**message, "status": 413}
            await send(message)

        await self.app(scope, bounded_receive, bounded_send)
