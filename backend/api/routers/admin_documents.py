"""Quản trị tài liệu tri thức RAG (FR18). Mọi endpoint require_admin; mọi thao tác ghi tạo một dòng audit log
chỉ gồm id và tên trường (không tên file, tiêu đề hay nội dung).

File tải lên chỉ được lưu với tên ngẫu nhiên và chỉ được đọc bởi pdf_guard (tiến trình con); không endpoint nào
phục vụ file. Lỗi trả thông báo thân thiện kèm mã ngắn trong ngoặc.
"""
import asyncio
import hashlib
import os
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.admin import require_admin
from api.schemas.admin_documents import (
    DeleteOut,
    DocumentListOut,
    DocumentMetadataIn,
    DocumentOut,
    DocumentUpdate,
    PreviewOut,
)
from core.config import settings
from core.database import get_db
from models.admin_audit_log import AdminAuditLog
from models.knowledge_document import DocumentOrigin, DocumentStatus, KnowledgeDocument
from models.user import User
from services.knowledge import indexing
from services.knowledge.documents import document_path, safe_filename, upload_dir
from services.knowledge.pdf_guard import (
    ERR_FILE_MISSING,
    ERR_NOT_PDF,
    PdfGuardError,
    has_pdf_magic,
    inspect_pdf,
    parse_pdf,
)

router = APIRouter(prefix="/admin/documents", tags=["Admin"])

READ_BLOCK = 1 << 20
TARGET = "document"
CHUNK_FIELDS = ("title", "authors_org", "year", "language", "topic")   # có trong metadata của đoạn
ERR_TOO_LARGE = "qua_lon"
ERR_DUPLICATE = "trung_noi_dung"
ERR_BUSY = "dang_lap_chi_muc"
ERR_BUILTIN = "tai_lieu_co_san"
ERR_ALREADY = "da_lap_chi_muc"
ERR_STORE = "kho_tai_lieu_loi"

MESSAGES = {
    ERR_NOT_PDF: "File không phải PDF hợp lệ.",
    "pdf_ma_hoa": "PDF được mã hoá (có mật khẩu) nên không đọc được.",
    "qua_nhieu_trang": "PDF có quá nhiều trang.",
    "pdf_khong_doc_duoc": "Không đọc được nội dung PDF.",
    "het_thoi_gian_doc": "Đọc PDF quá thời gian cho phép.",
    "khong_co_doan": "PDF không có đoạn văn bản nào dùng được.",
    ERR_FILE_MISSING: "File của tài liệu không còn trên máy chủ.",
    ERR_TOO_LARGE: "File quá lớn.",
    ERR_DUPLICATE: "Đã có tài liệu với cùng nội dung file.",
    ERR_BUSY: "Đang có tài liệu được lập chỉ mục; vui lòng chờ xong rồi thử lại.",
    ERR_BUILTIN: "Tài liệu có sẵn chỉ được xem và bật/tắt; không xoá, không sửa thông tin, không lập chỉ mục lại.",
    ERR_ALREADY: "Tài liệu đã được lập chỉ mục; chọn \"lập chỉ mục lại\" nếu muốn làm lại.",
    ERR_STORE: "Kho tài liệu (ChromaDB) tạm thời không truy cập được.",
}


def _error(code_status: int, code: str, extra: str = "") -> HTTPException:
    return HTTPException(status_code=code_status, detail=f"{MESSAGES.get(code, 'Lỗi.')}{extra} ({code})")


async def _audit(db: AsyncSession, admin: User, action: str, doc_id: uuid.UUID, fields: list[str]) -> None:
    db.add(AdminAuditLog(admin_user_id=admin.id, action=action, target_type=TARGET, target_id=str(doc_id),
                         details={"fields": sorted(fields)}))


async def _get(db: AsyncSession, doc_id: uuid.UUID) -> KnowledgeDocument:
    doc = await db.get(KnowledgeDocument, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")
    return doc


async def _store(fn, *args):
    """Gọi thao tác ChromaDB (đồng bộ) trong thread; lỗi → 503 với mã ngắn."""
    try:
        collection = await asyncio.to_thread(indexing.deps["collection"])
        return await asyncio.to_thread(fn, collection, *args)
    except Exception:  # noqa: BLE001
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, ERR_STORE) from None


@router.get("", response_model=DocumentListOut)
async def list_documents(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    docs = (await db.execute(select(KnowledgeDocument).order_by(
        KnowledgeDocument.origin, KnowledgeDocument.created_at.desc()))).scalars().all()
    return DocumentListOut(items=[DocumentOut.model_validate(d) for d in docs],
                           max_upload_mb=settings.KNOWLEDGE_MAX_UPLOAD_MB,
                           max_pages=settings.KNOWLEDGE_MAX_PDF_PAGES, max_chunks=settings.KNOWLEDGE_MAX_CHUNKS)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return DocumentOut.model_validate(await _get(db, doc_id))


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    authors_org: str = Form(...),
    year: int = Form(...),
    language: str = Form(...),
    topic: str = Form(...),
    license_note: str = Form(...),
    source_url: Optional[str] = Form(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    raw = {"title": title, "authors_org": authors_org, "year": year, "language": language, "topic": topic,
           "license_note": license_note, "source_url": source_url or None}
    try:
        meta = DocumentMetadataIn(**raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_input=False, include_context=False))
    original = safe_filename(file.filename)
    if not original.lower().endswith(".pdf"):
        raise _error(422, ERR_NOT_PDF)

    max_bytes = settings.KNOWLEDGE_MAX_UPLOAD_MB * 1024 * 1024
    folder = upload_dir()
    folder.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    stored = f"{doc_id}.pdf"                        # tên trên đĩa do server sinh — không dùng tên người dùng
    tmp = folder / f".{doc_id}.part"
    digest, size, head = hashlib.sha256(), 0, b""
    try:
        with open(tmp, "wb") as out:
            while block := await file.read(READ_BLOCK):
                size += len(block)
                if size > max_bytes:
                    raise _error(413, ERR_TOO_LARGE, f" Tối đa {settings.KNOWLEDGE_MAX_UPLOAD_MB} MB.")
                if len(head) < 5:
                    head += block[:5 - len(head)]
                digest.update(block)
                out.write(block)
        if not has_pdf_magic(head):
            raise _error(422, ERR_NOT_PDF)
        content_hash = digest.hexdigest()
        if (await db.execute(select(KnowledgeDocument.id).where(
                KnowledgeDocument.content_hash == content_hash))).first():
            raise _error(409, ERR_DUPLICATE)
        try:
            info = await asyncio.to_thread(inspect_pdf, tmp)
        except PdfGuardError as exc:
            extra = f" Tối đa {settings.KNOWLEDGE_MAX_PDF_PAGES} trang." if exc.code == "qua_nhieu_trang" else ""
            raise _error(422, exc.code, extra)
        doc = KnowledgeDocument(id=doc_id, origin=DocumentOrigin.UPLOAD, original_filename=original,
                                stored_name=stored, content_hash=content_hash, pages_total=info.pages_total,
                                status=DocumentStatus.UPLOADED, enabled=True, uploaded_by=admin.id,
                                **meta.model_dump())
        try:
            async with db.begin_nested():
                db.add(doc)
                await db.flush()
        except IntegrityError:
            raise _error(409, ERR_DUPLICATE) from None
        os.replace(tmp, folder / stored)
    finally:
        tmp.unlink(missing_ok=True)
    await _audit(db, admin, "document.upload", doc.id, ["file", *(k for k, v in raw.items() if v is not None)])
    await db.commit()
    await db.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.post("/{doc_id}/index", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def index_document(doc_id: uuid.UUID, background: BackgroundTasks,
                         force: bool = Query(False, description="Lập chỉ mục lại tài liệu đã indexed"),
                         admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Bắt đầu hoặc thử lại (chạy nền). Chỉ một việc lập chỉ mục tại một thời điểm (409 nếu đang có việc khác)."""
    doc = await _get(db, doc_id)
    if doc.origin == DocumentOrigin.BUILTIN:
        raise _error(403, ERR_BUILTIN)
    if doc.status == DocumentStatus.INDEXING:
        raise _error(409, ERR_BUSY)
    if doc.status == DocumentStatus.INDEXED and not force:
        raise _error(409, ERR_ALREADY)
    if not document_path(doc).is_file():
        raise _error(409, ERR_FILE_MISSING)
    try:
        async with db.begin_nested():
            doc.status, doc.error_code = DocumentStatus.INDEXING, None
            await db.flush()
    except IntegrityError:          # unique index một phần: đã có tài liệu khác đang indexing
        await db.refresh(doc)
        raise _error(409, ERR_BUSY) from None
    await _audit(db, admin, "document.index", doc.id, ["status"] + (["force"] if force else []))
    await db.commit()
    background.add_task(indexing.run_index_job, doc.id)
    return DocumentOut.model_validate(doc)


@router.get("/{doc_id}/preview", response_model=PreviewOut)
async def preview_document(doc_id: uuid.UUID, admin: User = Depends(require_admin),
                           db: AsyncSession = Depends(get_db)):
    """Tối đa 5 đoạn mẫu cách đều. Đã lập chỉ mục: lấy từ ChromaDB. Chưa: đọc PDF qua pdf_guard (KHÔNG nhúng)."""
    doc = await _get(db, doc_id)
    if doc.status == DocumentStatus.INDEXING:
        raise _error(409, ERR_BUSY)
    if doc.status == DocumentStatus.INDEXED:
        samples = await _store(indexing.preview_from_store, doc)
        return PreviewOut(source="store", pages_total=doc.pages_total, pages_kept=doc.pages_kept,
                          pages_skipped=(doc.pages_total - doc.pages_kept)
                          if None not in (doc.pages_total, doc.pages_kept) else None,
                          chunks_count=doc.chunks_count or 0, samples=samples)
    try:
        parsed = await asyncio.to_thread(parse_pdf, document_path(doc))
    except PdfGuardError as exc:
        raise _error(409 if exc.code == ERR_FILE_MISSING else 422, exc.code)
    return PreviewOut(source="parsed", pages_total=parsed.pages_total, pages_kept=parsed.pages_kept,
                      pages_skipped=parsed.pages_skipped, chunks_count=len(parsed.chunks),
                      samples=indexing.preview_from_parsed(parsed))


@router.patch("/{doc_id}", response_model=DocumentOut)
async def update_document(doc_id: uuid.UUID, body: DocumentUpdate, admin: User = Depends(require_admin),
                          db: AsyncSession = Depends(get_db)):
    """Sửa metadata (cập nhật metadata trích dẫn của các đoạn) và/hoặc bật tắt (doc_enabled). KHÔNG nhúng lại."""
    doc = await _get(db, doc_id)
    fields = body.model_dump(exclude_unset=True)
    if doc.origin == DocumentOrigin.BUILTIN and set(fields) - {"enabled"}:
        raise _error(403, ERR_BUILTIN)
    if doc.status == DocumentStatus.INDEXING:
        raise _error(409, ERR_BUSY)
    changed = [k for k, v in fields.items() if getattr(doc, k) != v]
    chunk_fields = {k: fields[k] for k in changed if k in CHUNK_FIELDS}
    if chunk_fields:
        await _store(indexing.update_chunks_metadata, doc, chunk_fields)
    if "enabled" in changed:
        await _store(indexing.set_chunks_enabled, doc, fields["enabled"])
    for k in changed:
        setattr(doc, k, fields[k])
    if changed:
        await _audit(db, admin, "document.update", doc.id, changed)
    await db.commit()
    await db.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.delete("/{doc_id}", response_model=DeleteOut)
async def delete_document(doc_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Chỉ tài liệu tải lên: xoá đoạn trong ChromaDB → file → bản ghi. ChromaDB lỗi thì giữ nguyên bản ghi (503)."""
    doc = await _get(db, doc_id)
    if doc.origin == DocumentOrigin.BUILTIN:
        raise _error(403, ERR_BUILTIN)
    if doc.status == DocumentStatus.INDEXING:
        raise _error(409, ERR_BUSY)
    deleted = await _store(indexing.delete_chunks, doc)
    path = document_path(doc)
    missing = not path.is_file()
    path.unlink(missing_ok=True)
    await db.delete(doc)
    await _audit(db, admin, "document.delete", doc_id, ["chunks", "file", "record"])
    await db.commit()
    return DeleteOut(deleted=True, chunks_deleted=deleted, file_missing=missing)
