from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import re
import warnings
from zipfile import ZipFile, BadZipFile
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException
from .config import settings
from .models import Attachment, uid

MAX_FILE = 10 * 1024 * 1024
MAX_TOTAL = 25 * 1024 * 1024
MAX_FILES = 5
Image.MAX_IMAGE_PIXELS = 20_000_000


@dataclass
class PreparedFile:
    filename: str
    content_type: str
    content: bytes


def verified_type(filename, content):
    ext = PurePosixPath(filename).suffix.lower()
    images = {".png": ("PNG", "image/png"), ".jpg": ("JPEG", "image/jpeg"), ".jpeg": ("JPEG", "image/jpeg"), ".webp": ("WEBP", "image/webp"), ".gif": ("GIF", "image/gif")}
    if ext in images:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if image.format != images[ext][0]:
                        raise ValueError("image format")
                    image.verify()
            return images[ext][1]
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(422, "Görsel dosyası geçerli değil veya çok büyük.")
    if ext == ".pdf" and content.startswith(b"%PDF-"):
        return "application/pdf"
    if ext in {".txt", ".csv"}:
        try:
            content.decode("utf-8-sig")
            if b"\x00" in content:
                raise ValueError("binary text")
            return "text/plain" if ext == ".txt" else "text/csv"
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(422, "Metin dosyası UTF-8 biçiminde olmalı.")
    if ext in {".docx", ".xlsx"}:
        try:
            with ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                expected = "word/document.xml" if ext == ".docx" else "xl/workbook.xml"
                if expected not in archive.namelist() or "[Content_Types].xml" not in archive.namelist() or any("vbaproject" in e.filename.lower() for e in entries) or sum(e.file_size for e in entries) > 100 * 1024 * 1024:
                    raise ValueError("invalid document")
            return "application/vnd.openxmlformats-officedocument." + ("wordprocessingml.document" if ext == ".docx" else "spreadsheetml.sheet")
        except (BadZipFile, ValueError):
            raise HTTPException(422, "Office dosyası geçerli değil. Makrolu dosyalar desteklenmiyor.")
    raise HTTPException(422, "PNG, JPG, WEBP, GIF, PDF, TXT, CSV, DOCX veya XLSX dosyası seçin.")


async def prepare_files(files):
    if len(files) > MAX_FILES:
        raise HTTPException(422, "Bir mesaja en fazla 5 dosya ekleyebilirsiniz.")
    result, total = [], 0
    for file in files:
        filename = re.sub(r'[\x00-\x1f\x7f]', "", (file.filename or "dosya").replace("\\", "/").split("/")[-1])[:200].strip()
        if not filename:
            raise HTTPException(422, "Dosya adı geçerli değil.")
        content = await file.read(MAX_FILE + 1)
        total += len(content)
        if len(content) > MAX_FILE or total > MAX_TOTAL:
            raise HTTPException(413, "Dosya başına 10 MB, mesaj başına toplam 25 MB sınırı vardır.")
        if not content:
            raise HTTPException(422, "Boş dosya yüklenemez.")
        result.append(PreparedFile(filename, verified_type(filename, content), content))
    return result


def store_files(db, ticket, message, files, written):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    for file in files:
        identifier = uid()
        path = settings.upload_dir / identifier
        written.append(path)
        with path.open("xb") as stream:
            stream.write(file.content)
        db.add(Attachment(id=identifier, tenant_id=ticket.tenant_id, ticket_id=ticket.id, message_id=message.id,
                          filename=file.filename, content_type=file.content_type, size=len(file.content)))


def attachment_view(item):
    return {"id": item.id, "filename": item.filename, "content_type": item.content_type, "size": item.size}
