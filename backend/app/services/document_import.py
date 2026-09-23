"""Bounded text extraction for user-supplied resume and JD files."""

from io import BytesIO
from pathlib import PurePath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader

from app.core.errors import BusinessError

MAX_UPLOAD_BYTES = 5_000_000
MAX_EXTRACTED_BYTES = 200_000


def extract(filename: str, data: bytes) -> tuple[str, str]:
    name = PurePath(filename.replace("\\", "/")).name[:128]
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if len(data) > MAX_UPLOAD_BYTES:
        raise BusinessError("文件不能超过 5 MB", 400)
    try:
        if suffix in {"txt", "md"}:
            content = data.decode("utf-8-sig")
        elif suffix == "pdf":
            reader = PdfReader(BytesIO(data), strict=False)
            if reader.is_encrypted or len(reader.pages) > 30:
                raise BusinessError("PDF 已加密或超过 30 页", 400)
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
                if sum(len(part.encode("utf-8")) for part in pages) > MAX_EXTRACTED_BYTES:
                    raise BusinessError("提取文本超过 200 KB", 400)
            content = "\n".join(pages)
        elif suffix == "docx":
            with ZipFile(BytesIO(data)) as archive:
                members = archive.infolist()
                if len(members) > 500 or sum(item.file_size for item in members) > 20_000_000:
                    raise BusinessError("Word 文件结构过大", 400)
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            content = "\n".join(
                "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
                for paragraph in root.iter(namespace + "p")
            )
        else:
            raise BusinessError("仅支持 .txt、.md、.pdf、.docx 文件", 400)
    except BusinessError:
        raise
    except (UnicodeError, BadZipFile, KeyError, ElementTree.ParseError, ValueError, OSError):
        raise BusinessError("文件无法解析，请检查格式或改用粘贴文本", 400) from None
    except Exception:
        # PDF 解压/解析器可能抛出格式特定异常；不向客户端泄露内部细节。
        raise BusinessError("文件无法解析，请检查格式或改用粘贴文本", 400) from None
    content = content.strip()
    if not content:
        raise BusinessError("未提取到文本；扫描版文件请先 OCR 后粘贴", 400)
    if len(content.encode("utf-8")) > MAX_EXTRACTED_BYTES:
        raise BusinessError("提取文本超过 200 KB", 400)
    return name, content
