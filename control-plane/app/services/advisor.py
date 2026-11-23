# Nguyễn Tâm Bình - 2324801030003
import base64
import io
import json
import logging
import re
import time
import zipfile
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import anthropic
import httpx
from fastapi import HTTPException
from sqlalchemy import func, select

from app.config import get_settings
from app.models import AuditLog, Node, NodeOSTemplate, OSImage, Plan

logger = logging.getLogger(__name__)
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
INLINE_TYPES = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
TEXT_TYPES = {"txt", "csv", "md"}
SERVICES = {"vps": "Máy chủ ảo VPS", "ai": "Máy chủ AI có GPU", "postgres": "Cơ sở dữ liệu PostgreSQL", "webapp": "Ứng dụng web từ Git"}
SCHEMA = {"type": "OBJECT", "properties": {"tom_tat": {"type": "STRING"}, "goi_y": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"plan_id": {"type": "INTEGER"}, "os_ma": {"type": "STRING"}, "ly_do": {"type": "STRING"}}, "required": ["plan_id", "ly_do"]}}}, "required": ["tom_tat", "goi_y"]}


def xml_text(data, tag):
    root = ElementTree.fromstring(data)
    return [node.text for node in root.iter() if node.tag.endswith(tag) and node.text]


def document_text(name, data):
    # Word, Excel đọc chữ từ XML trong gói zip; PDF và ảnh gửi nguyên cho mô hình đọc
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    try:
        if ext == "docx":
            with zipfile.ZipFile(io.BytesIO(data)) as package:
                return "\n".join(" ".join(xml_text(package.read(part), "}t")) for part in package.namelist() if re.fullmatch(r"word/(document|header\d*|footer\d*)\.xml", part)), None
        if ext == "xlsx":
            with zipfile.ZipFile(io.BytesIO(data)) as package:
                shared = xml_text(package.read("xl/sharedStrings.xml"), "}t") if "xl/sharedStrings.xml" in package.namelist() else []
                values = []
                for part in sorted(p for p in package.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", p)):
                    for cell in ElementTree.fromstring(package.read(part)).iter():
                        if cell.tag.endswith("}c") and cell.get("t") == "inlineStr":
                            values.append("".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t")))
                        elif cell.tag.endswith("}c"):
                            value = next((child.text for child in cell if child.tag.endswith("}v")), None)
                            if value is not None:
                                values.append(shared[int(value)] if cell.get("t") == "s" and value.isdigit() and int(value) < len(shared) else value)
                return " | ".join(values), None
        if ext in TEXT_TYPES:
            return data.decode("utf-8", errors="replace"), None
        if ext in INLINE_TYPES:
            return "", {"inline_data": {"mime_type": INLINE_TYPES[ext], "data": base64.b64encode(data).decode()}}
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, ValueError):
        raise HTTPException(status_code=422, detail="Không đọc được tệp. Hãy kiểm tra tệp có mở được không hoặc nhập mô tả bằng chữ.") from None
    raise HTTPException(status_code=422, detail="Chỉ nhận tệp Word (.docx), Excel (.xlsx), PDF, ảnh (PNG, JPG, WebP) hoặc văn bản (.txt).")


def catalog(db):
    plans = list(db.scalars(select(Plan).where(Plan.active.is_(True)).order_by(Plan.gia_theo_gio)))
    images = list(db.scalars(select(OSImage).where(OSImage.id.in_(select(NodeOSTemplate.os_image_id).join(Node, Node.id == NodeOSTemplate.node_id))).order_by(OSImage.thu_tu)))
    return plans, images


def service_of(plan):
    return "ai" if plan.gpu else plan.dich_vu


def prompt(plans, images, description, document):
    rows = "\n".join(f"- plan_id={p.id}: {p.ten}, dịch vụ={service_of(p)}, {p.vcpu} vCPU, {p.ram_mb} MB RAM, {p.disk_gb} GB ổ, GPU={p.gpu}, giá {int(p.gia_theo_gio)} đồng/giờ" for p in plans)
    oses = "\n".join(f"- os_ma={o.ma}: {o.ten}, cần tối thiểu {o.min_ram_mb} MB RAM, {o.min_disk_gb} GB ổ, {'chỉ dùng với gói có GPU' if o.chi_gpu else 'gói không GPU'}, đăng nhập {o.ket_noi.upper()}" for o in images)
    return f"""Bạn là trợ lý tư vấn của TBT Cloud, nhà cung cấp máy chủ ảo (IaaS) và dịch vụ nền tảng (PaaS) tính tiền theo giờ.
Đọc nhu cầu của khách (mô tả và tài liệu đính kèm nếu có) rồi chọn cấu hình phù hợp nhất trong danh mục dưới đây. Chỉ dùng plan_id và os_ma có trong danh mục.

Danh mục gói:
{rows}

Hệ điều hành (chỉ dùng cho dịch vụ vps và ai; postgres, webapp để os_ma rỗng):
{oses}

Quy tắc:
- goi_y xếp theo mức phù hợp giảm dần, tối đa 4 mục, mục đầu là lựa chọn tốt nhất; các mục sau là phương án liên quan (rẻ hơn, mạnh hơn, hoặc dịch vụ khác cũng đáp ứng được).
- Chọn gói đủ dùng với chi phí hợp lý, không chọn quá mạnh khi nhu cầu nhỏ. Cần GPU (huấn luyện, suy luận mô hình, xử lý ảnh, video) thì dùng gói có GPU với hệ điều hành chỉ dùng cho GPU.
- Hệ điều hành phải đủ RAM và ổ đĩa tối thiểu của gói đã chọn. Phần mềm chỉ chạy trên Windows thì chọn Windows.
- Chỉ cần cơ sở dữ liệu thì chọn gói postgres; chỉ cần đưa trang web hoặc ứng dụng Node.js từ Git lên thì chọn gói webapp.
- ly_do viết tiếng Việt, 1 - 2 câu, nói rõ vì sao cấu hình này hợp nhu cầu. tom_tat tóm nhu cầu của khách trong 1 câu tiếng Việt.

Mô tả của khách: {description.strip() or '(không có, xem tài liệu đính kèm)'}
{('Nội dung tài liệu khách gửi:' + chr(10) + document[:20000]) if document else ''}"""


def ask_gemini(text, inline):
    # Mô hình chính quá tải (429/500/503) thì thử lại có giãn cách, rồi chuyển lần lượt sang các mô hình dự phòng
    settings = get_settings()
    body = {"contents": [{"role": "user", "parts": [{"text": text}, *([inline] if inline else [])]}], "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "responseSchema": SCHEMA}}
    models = [settings.gemini_model, *(m.strip() for m in settings.gemini_fallback_models.split(",") if m.strip() and m.strip() != settings.gemini_model)]
    deadline = time.monotonic() + settings.gemini_budget
    for model in models:
        for attempt in range(2):
            if time.monotonic() >= deadline:
                logger.warning("Gemini quá %ss, chuyển sang mô hình dự phòng", settings.gemini_budget)
                return None
            try:
                response = httpx.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": settings.gemini_api_key.get_secret_value()}, json=body, timeout=max(1.0, min(settings.gemini_timeout, deadline - time.monotonic())))
                response.raise_for_status()
                # Câu trả lời có thể chia nhiều phần và kèm phần suy nghĩ: ghép các phần chữ
                parts = response.json()["candidates"][0]["content"]["parts"]
                text_out = "".join(part.get("text", "") for part in parts if not part.get("thought"))
                return json.loads(text_out[text_out.find("{"):text_out.rfind("}") + 1])
            except httpx.HTTPStatusError as error:
                logger.warning("Gemini %s trả mã %s", model, error.response.status_code)
                if error.response.status_code not in (429, 500, 503):
                    break
                time.sleep(settings.gemini_retry_seconds * (attempt + 1))
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as error:
                logger.warning("Gemini %s chưa trả lời được (%s)", model, type(error).__name__)
                break
    return None


CLAUDE_SCHEMA = {"type": "object", "properties": {"tom_tat": {"type": "string"}, "goi_y": {"type": "array", "items": {"type": "object", "properties": {"plan_id": {"type": "integer"}, "os_ma": {"type": "string"}, "ly_do": {"type": "string"}}, "required": ["plan_id", "os_ma", "ly_do"], "additionalProperties": False}}}, "required": ["tom_tat", "goi_y"], "additionalProperties": False}


def ask_claude(text, inline):
    # Tuyến dự phòng khi mọi mô hình Gemini đều lỗi; PDF gửi dạng document, ảnh dạng image
    settings = get_settings()
    if settings.anthropic_api_key is None:
        return None
    content = []
    if inline:
        data = inline["inline_data"]
        content.append({"type": "document" if data["mime_type"] == "application/pdf" else "image", "source": {"type": "base64", "media_type": data["mime_type"], "data": data["data"]}})
    content.append({"type": "text", "text": text})
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value(), timeout=45, max_retries=1)
    started = time.monotonic()
    logger.warning("Gemini lỗi, chuyển sang Claude %s", settings.claude_model)
    try:
        response = client.beta.messages.create(model=settings.claude_model, max_tokens=4000, betas=["server-side-fallback-2026-07-01"], fallbacks="default", output_config={"effort": "low", "format": {"type": "json_schema", "schema": CLAUDE_SCHEMA}}, messages=[{"role": "user", "content": content}])
    except anthropic.RateLimitError:
        logger.warning("Claude dự phòng bị giới hạn lượt gọi")
        return None
    except anthropic.APIStatusError as error:
        logger.warning("Claude dự phòng trả mã %s", error.status_code)
        return None
    except anthropic.APIConnectionError:
        logger.warning("Không kết nối được Claude dự phòng")
        return None
    logger.warning("Claude trả lời sau %.1fs", time.monotonic() - started)
    if response.stop_reason in ("refusal", "max_tokens"):
        logger.warning("Claude dự phòng dừng vì %s", response.stop_reason)
        return None
    text_out = next((block.text for block in response.content if block.type == "text"), "")
    try:
        return json.loads(text_out)
    except ValueError:
        logger.warning("Claude dự phòng trả JSON không hợp lệ")
        return None


def ask_model(text, inline):
    answer = ask_gemini(text, inline)
    if answer is None:
        answer = ask_claude(text, inline)
    if answer is None:
        raise HTTPException(status_code=503, detail="AI đang bận, chưa gợi ý được. Hãy thử lại sau ít phút hoặc tự chọn gói bên dưới.")
    return answer


def suggest(db, user, description, file_name=None, file_data=None):
    settings = get_settings()
    if settings.gemini_api_key is None:
        raise HTTPException(status_code=503, detail="Chức năng AI gợi ý chưa được bật.")
    if not description.strip() and not file_data:
        raise HTTPException(status_code=422, detail="Hãy mô tả nhu cầu hoặc đính kèm một tệp.")
    since = datetime.now(timezone.utc) - timedelta(days=1)
    if db.scalar(select(func.count(AuditLog.id)).where(AuditLog.user_id == user.id, AuditLog.action == "ai.suggest", AuditLog.created_at >= since)) >= settings.ai_daily_limit:
        raise HTTPException(status_code=429, detail=f"Bạn đã dùng hết {settings.ai_daily_limit} lượt gợi ý trong 24 giờ. Hãy thử lại sau.")
    document, inline = document_text(file_name, file_data) if file_data else ("", None)
    plans, images = catalog(db)
    answer = ask_model(prompt(plans, images, description, document), inline)
    by_plan, by_os = {p.id: p for p in plans}, {o.ma: o for o in images}
    result, seen = [], set()
    for item in answer.get("goi_y", []) if isinstance(answer, dict) else []:
        plan = by_plan.get(item.get("plan_id")) if isinstance(item, dict) else None
        if plan is None:
            continue
        service = service_of(plan)
        image = by_os.get(item.get("os_ma") or "") if service in ("vps", "ai") else None
        if service in ("vps", "ai"):
            fitting = [o for o in images if o.chi_gpu == (service == "ai") and plan.ram_mb >= o.min_ram_mb and plan.disk_gb >= o.min_disk_gb]
            if image not in fitting:
                image = fitting[0] if fitting else None
            if image is None:
                continue
        key = (plan.id, image.ma if image else None)
        if key in seen:
            continue
        seen.add(key)
        result.append({"dich_vu": service, "ten_dich_vu": SERVICES[service], "plan_id": plan.id, "ten_goi": plan.ten, "vcpu": plan.vcpu, "ram_mb": plan.ram_mb, "disk_gb": plan.disk_gb, "gpu": plan.gpu, "gia_theo_gio": plan.gia_theo_gio, "os_ma": image.ma if image else None, "ten_he_dieu_hanh": image.ten if image else None, "ly_do": str(item.get("ly_do") or "")[:400]})
        if len(result) == 4:
            break
    db.add(AuditLog(user_id=user.id, action="ai.suggest", resource=f"user:{user.id}", detail=f"{len(result)} gợi ý" + (f", tệp {file_name.rsplit('.', 1)[-1].lower()}" if file_name else "")))
    db.commit()
    if not result:
        raise HTTPException(status_code=422, detail="AI chưa tìm được cấu hình phù hợp. Hãy mô tả rõ hơn nhu cầu (phần mềm cần chạy, số người dùng, dung lượng dữ liệu).")
    return {"tom_tat": str(answer.get("tom_tat") or "")[:300], "goi_y": result}
