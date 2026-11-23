# Nguyễn Tâm Bình - 2324801030003
import base64
import io
import json
import zipfile
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.config import get_settings
from app.models import AuditLog, OSImage, Plan
from app.services import advisor


@pytest.fixture
def gemini(monkeypatch, db, seed):
    monkeypatch.setattr(get_settings(), "gemini_api_key", SecretStr("fake-gemini-key"))
    monkeypatch.setattr(get_settings(), "gemini_retry_seconds", 0)
    db.add(Plan(ten="Postgres Nhỏ", dich_vu="postgres", vcpu=1, ram_mb=1024, disk_gb=10, gia_theo_gio=Decimal("400.00")))
    windows = OSImage(ma="windows11", ten="Windows 11", ho="windows", min_ram_mb=4096, min_disk_gb=64, ket_noi="rdp", thu_tu=2)
    db.add(windows)
    db.commit()
    calls = []
    state = {"answer": None, "status": 200}

    def post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "body": json})
        if state["status"] != 200:
            return httpx.Response(state["status"], request=httpx.Request("POST", url), json={"error": "upstream"})
        return httpx.Response(200, request=httpx.Request("POST", url), json={"candidates": [{"content": {"parts": [{"text": "suy nghĩ", "thought": True}, {"text": __import__("json").dumps(state["answer"])[:10]}, {"text": __import__("json").dumps(state["answer"])[10:], "thoughtSignature": "x"}]}}]})

    monkeypatch.setattr(advisor.httpx, "post", post)
    return calls, state


def docx_bytes(text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("word/document.xml", f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return buffer.getvalue()


def test_suggest_validates_and_orders(client, db, headers, seed, gemini):
    calls, state = gemini
    postgres = db.query(Plan).filter_by(dich_vu="postgres").one()
    state["answer"] = {"tom_tat": "Cửa hàng cần lưu đơn hàng", "goi_y": [{"plan_id": seed["plan"].id, "os_ma": "windows11", "ly_do": "Đủ cho web bán hàng nhỏ."}, {"plan_id": 9999, "ly_do": "Không tồn tại"}, {"plan_id": postgres.id, "os_ma": "debian13", "ly_do": "Lưu dữ liệu đơn hàng."}]}
    result = client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"mo_ta": "Cửa hàng 3 chi nhánh, sổ sách rời rạc"})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["tom_tat"] == "Cửa hàng cần lưu đơn hàng"
    assert [(g["dich_vu"], g["plan_id"], g["os_ma"]) for g in data["goi_y"]] == [("vps", seed["plan"].id, "debian13"), ("postgres", postgres.id, None)]
    assert calls[0]["headers"]["x-goog-api-key"] == "fake-gemini-key" and "gemini-3.5-flash-lite" in calls[0]["url"]
    assert "plan_id=" in calls[0]["body"]["contents"][0]["parts"][0]["text"] and "fake-gemini-key" not in result.text
    assert db.query(AuditLog).filter_by(action="ai.suggest").count() == 1


def test_suggest_reads_word_and_sends_pdf_inline(client, headers, seed, gemini):
    calls, state = gemini
    state["answer"] = {"tom_tat": "x", "goi_y": [{"plan_id": seed["plan"].id, "os_ma": "debian13", "ly_do": "y"}]}
    word = base64.b64encode(docx_bytes("Kho hàng hay thất lạc phiếu xuất")).decode()
    assert client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"tep_ten": "nhu_cau.docx", "tep_base64": word}).status_code == 200
    assert "Kho hàng hay thất lạc phiếu xuất" in calls[-1]["body"]["contents"][0]["parts"][0]["text"]
    pdf = base64.b64encode(b"%PDF-1.4 fake").decode()
    assert client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"mo_ta": "xem tệp", "tep_ten": "de_an.pdf", "tep_base64": pdf}).status_code == 200
    assert calls[-1]["body"]["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "application/pdf"


@pytest.mark.parametrize("body, status", [({}, 422), ({"tep_ten": "virus.exe", "tep_base64": base64.b64encode(b"MZ").decode()}, 422), ({"tep_ten": "a.pdf", "tep_base64": "khong-phai-base64!"}, 422), ({"tep_base64": base64.b64encode(b"abc").decode()}, 422)])
def test_suggest_rejects_bad_input(client, headers, gemini, body, status):
    assert client.post("/api/v1/ai/goi-y", headers=headers["user"], json=body).status_code == status


def test_suggest_limits_admin_upstream_and_quota(client, db, headers, seed, gemini, monkeypatch):
    calls, state = gemini
    assert client.post("/api/v1/ai/goi-y", headers=headers["admin"], json={"mo_ta": "x"}).status_code == 403
    state["status"] = 500
    failed = client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"mo_ta": "x"})
    assert failed.status_code == 503 and "upstream" not in failed.text
    state["status"], state["answer"] = 200, {"tom_tat": "x", "goi_y": []}
    assert client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"mo_ta": "x"}).status_code == 422
    monkeypatch.setattr(get_settings(), "ai_daily_limit", 1)
    assert client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"mo_ta": "x"}).status_code == 429
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    assert client.post("/api/v1/ai/goi-y", headers=headers["other"], json={"mo_ta": "x"}).status_code == 503


def test_retry_then_fallback_model(client, headers, seed, gemini, monkeypatch):
    calls, state = gemini
    state["answer"] = {"tom_tat": "x", "goi_y": [{"plan_id": seed["plan"].id, "os_ma": "debian13", "ly_do": "y"}]}
    original = advisor.httpx.post
    def flaky(url, headers, json, timeout):
        if "flash-lite" in url:
            calls.append({"url": url, "headers": headers, "body": json})
            return httpx.Response(503, request=httpx.Request("POST", url))
        return original(url, headers=headers, json=json, timeout=timeout)
    monkeypatch.setattr(advisor.httpx, "post", flaky)
    result = client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"mo_ta": "x"})
    assert result.status_code == 200
    assert [c["url"].split("/models/")[1].split(":")[0] for c in calls] == ["gemini-3.5-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash"]


def test_claude_fallback_when_gemini_fails(client, headers, seed, gemini, monkeypatch):
    calls, state = gemini
    state["status"] = 503
    sent = {}
    answer = {"tom_tat": "từ Claude", "goi_y": [{"plan_id": seed["plan"].id, "os_ma": "debian13", "ly_do": "Claude chọn."}]}

    class Messages:
        def create(self, **kwargs):
            sent.update(kwargs)
            return SimpleNamespace(stop_reason=state.get("claude_stop", "end_turn"), content=[SimpleNamespace(type="text", text=json.dumps(answer))])

    class FakeClient:
        def __init__(self, api_key, timeout, max_retries):
            sent["api_key"] = api_key
            self.beta = SimpleNamespace(messages=Messages())

    monkeypatch.setattr(advisor.anthropic, "Anthropic", FakeClient)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)
    assert client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"mo_ta": "x"}).status_code == 503
    monkeypatch.setattr(get_settings(), "anthropic_api_key", SecretStr("fake-claude-key"))
    pdf = base64.b64encode(b"%PDF-1.4").decode()
    result = client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"mo_ta": "x", "tep_ten": "a.pdf", "tep_base64": pdf})
    assert result.status_code == 200 and result.json()["tom_tat"] == "từ Claude"
    assert sent["model"] == "claude-sonnet-5-5" and sent["api_key"] == "fake-claude-key" and sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["messages"][0]["content"][0]["type"] == "document" and sent["messages"][0]["content"][-1]["type"] == "text"
    state["claude_stop"] = "refusal"
    assert client.post("/api/v1/ai/goi-y", headers=headers["user"], json={"mo_ta": "x"}).status_code == 503


def test_reads_excel_shared_and_inline_strings():
    buffer = io.BytesIO()
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("xl/sharedStrings.xml", f'<sst {ns}><si><t>Lịch hẹn trùng</t></si></sst>')
        package.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData><row><c t="s"><v>0</v></c><c t="inlineStr"><is><t>Hồ sơ thất lạc</t></is></c><c><v>40</v></c></row></sheetData></worksheet>')
    text, inline = advisor.document_text("phong_kham.xlsx", buffer.getvalue())
    assert text == "Lịch hẹn trùng | Hồ sơ thất lạc | 40" and inline is None
