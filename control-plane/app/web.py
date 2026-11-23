# Nguyễn Tâm Bình - 2324801030003
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse


def serve_web(application, directory):
    root = Path(directory).resolve()
    if not root.is_dir() or not (root / "index.html").is_file():
        raise ValueError("WEB_DIR phải trỏ tới thư mục web có index.html.")
    if not (root / "index.html").resolve().is_relative_to(root):
        raise ValueError("WEB_DIR không được trỏ index.html ra ngoài thư mục web.")

    @application.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def web_file(path: str):
        if path.startswith(("api", "docs", "openapi.json", "redoc", "health")):
            raise HTTPException(status_code=404, detail="Không tìm thấy đường dẫn.")
        relative = Path(path)
        target = (root / relative).resolve()
        if not target.is_relative_to(root) or any(part.startswith(".") for part in relative.parts):
            raise HTTPException(status_code=404, detail="Không tìm thấy tệp.")
        if not target.is_file():
            target = (root / "index.html").resolve()
        if not target.is_relative_to(root) or any(part.startswith(".") for part in target.relative_to(root).parts):
            raise HTTPException(status_code=404, detail="Không tìm thấy tệp.")
        # Mã web, trang, icon, font (font icon được cắt theo từng bản build) luôn hỏi lại bản mới, không đổi thì 304; chỉ canvaskit giữ lâu
        cache = "public, max-age=86400" if target.relative_to(root).parts[0] == "canvaskit" else "no-cache"
        return FileResponse(target, headers={"Cache-Control": cache, "X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin"})
