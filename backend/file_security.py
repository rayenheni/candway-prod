"""
FILE UPLOAD SECURITY
P0-005 FIX: Comprehensive file upload validation and security.
Provides magic number detection, safe filename handling, and virus scanning interface.
"""

import hashlib
import logging
import os
import re
from typing import Optional, Tuple

from fastapi import UploadFile

logger = logging.getLogger(__name__)

try:
    import magic

    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    logger.warning("python-magic not installed - MIME detection disabled")

# Allowed file types and their MIME types
ALLOWED_FILE_TYPES = {
    # Documents
    "pdf": ["application/pdf"],
    "doc": ["application/msword"],
    "docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    "txt": ["text/plain"],
    "rtf": ["application/rtf"],
    "odt": ["application/vnd.oasis.opendocument.text"],
    # Images (for profile photos, course thumbnails)
    "jpg": ["image/jpeg"],
    "jpeg": ["image/jpeg"],
    "png": ["image/png"],
    "gif": ["image/gif"],
    "webp": ["image/webp"],
    # Video (for interview recordings)
    "mp4": ["video/mp4"],
    "webm": ["video/webm"],
    "mov": ["video/quicktime"],
    # Data/Other
    "json": ["application/json"],
    "xml": ["application/xml"],
    "csv": ["text/csv"],
    "zip": ["application/zip"],
    "xls": ["application/vnd.ms-excel"],
    "xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
}

# Maximum file sizes (in bytes)
MAX_FILE_SIZES = {
    "cv": 10 * 1024 * 1024,  # 10 MB for CV/resume
    "image": 5 * 1024 * 1024,  # 5 MB for images
    "video": 500 * 1024 * 1024,  # 500 MB for video
    "document": 25 * 1024 * 1024,  # 25 MB for other documents
    "default": 10 * 1024 * 1024,  # 10 MB default
}

# Dangerous file extensions that should never be allowed
BLOCKED_EXTENSIONS = {
    "exe",
    "scr",
    "bat",
    "cmd",
    "com",
    "pif",
    "msi",
    "dll",
    "jar",
    "sh",
    "bash",
    "bin",
    "app",
    "deb",
    "rpm",
    "php",
    "phtml",
    "php3",
    "php4",
    "php5",
    "php7",
    "php8",
    "asp",
    "aspx",
    "jsp",
    "jspx",
    "cgi",
    "pl",
    "py",
    "rb",
    "perl",
    "html",
    "htm",
    "xhtml",
    "shtml",
    "js",
    "ts",
    "jsx",
    "tsx",
    "css",
    "scss",
    "sass",
    "less",
    # FIX-4: removed "xml" and "webp" — they appear in ALLOWED_FILE_TYPES
    # and blocking them here caused silent upload rejections.
    "xsd",
    "xsl",
    "sql",
    "db",
    "sqlite",
    "mdb",
    "htaccess",
    "htpasswd",
    "svg",  # Can contain embedded scripts
    "ai",
    "psd",
    "eps",  # Can contain embedded code
    "bmp",
    "tiff",
    "tif",  # Can contain exploits
}

# Magic number signatures (file headers)
# FIX-5: MP4 and MOV use a 4-byte big-endian length + 4-byte box type (e.g. 'ftyp' or 'moov').
# The box type starts at byte offset 4, NOT at offset 0. We use a custom function
# to check at the correct offset rather than startswith().
MAGIC_SIGNATURES = {
    "pdf": b"%PDF",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG",
    "gif": b"GIF8",
    "webp": b"RIFF",
    "mp4": None,  # checked separately via offset-aware logic
    "webm": b"\x1aE",
    "mov": None,  # checked separately via offset-aware logic
    "txt": None,  # Plain text has no specific magic number
    "doc": b"\xd0\xcf\x11\xe0",
    "docx": b"PK\x03\x04",  # ZIP-based (like docx)
    "zip": b"PK\x03\x04",
    "json": None,  # No magic number
    "xml": b"<?xml",
}

# Video formats that store the box type at a variable offset (4 bytes in for mp4/mov)
MP4_BOX_TYPES = {b"ftyp", b"moov", b"mdat", b"free", b"skip"}
MOV_BOX_TYPES = {b"moov", b"ftyp", b"free", b"mdat", b"wide"}


def get_file_category(file_extension: str) -> str:
    """Determine file category based on extension"""
    ext = file_extension.lower().lstrip(".")

    if ext in ("pdf", "doc", "docx", "txt", "rtf", "odt"):
        return "document"
    elif ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
        return "image"
    elif ext in ("mp4", "webm", "mov", "avi", "mkv"):
        return "video"
    elif ext in ("xls", "xlsx", "csv"):
        return "document"
    else:
        return "default"


def get_max_file_size(category: str) -> int:
    """Get maximum allowed file size for category"""
    return MAX_FILE_SIZES.get(category, MAX_FILE_SIZES["default"])


def validate_filename(filename: str) -> Tuple[bool, str]:
    """
    Validate and sanitize filename to prevent path traversal and other attacks.

    Returns:
        (is_valid, sanitized_filename)
    """
    if not filename:
        return False, ""

    # Get just the filename, not any path
    basename = os.path.basename(filename)

    # Check for path traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename:
        logger.warning(f"Path traversal attempt detected: {filename}")
        return False, ""

    # Remove any null bytes
    basename = basename.replace("\x00", "")

    # Get extension
    _, ext = os.path.splitext(basename)
    ext = ext.lower().lstrip(".")

    # Check against blocked extensions
    if ext in BLOCKED_EXTENSIONS:
        logger.warning(f"Blocked file extension attempted: {ext}")
        return False, ""

    # Create safe filename with timestamp prefix to prevent overwrites
    import time

    safe_name = f"{int(time.time())}_{basename}"

    # Remove any characters that could be problematic
    safe_name = re.sub(r"[^\w\s\-.]", "", safe_name)

    return True, safe_name


def detect_mime_type(file_content: bytes) -> Optional[str]:
    """
    Detect actual MIME type using magic numbers.
    More reliable than trusting client-provided Content-Type.
    """
    if not HAS_MAGIC:
        return None
    try:
        mime = magic.Magic(mime=True)
        detected = mime.from_buffer(file_content)
        return detected
    except Exception as e:
        logger.error(f"MIME detection failed: {e}")
        return None


def validate_file_content(
    file_content: bytes, expected_extension: str, max_size: int
) -> Tuple[bool, str]:
    """
    Comprehensive file content validation.

    Checks:
    - File size
    - Magic number signatures
    - MIME type consistency

    Returns:
        (is_valid, error_message)
    """
    # Check file size
    if len(file_content) > max_size:
        return (
            False,
            f"File size exceeds maximum allowed ({max_size // (1024 * 1024)} MB)",
        )

    if len(file_content) < 8:
        return False, "File too small to be valid"

    # Detect actual MIME type
    detected_mime = detect_mime_type(file_content)

    if not detected_mime:
        return False, "Could not determine file type"

    # Get allowed MIME types for extension
    allowed_mimes = ALLOWED_FILE_TYPES.get(expected_extension.lower(), [])

    # Check if detected MIME matches allowed
    if allowed_mimes and detected_mime not in allowed_mimes:
        # Special case: ZIP-based formats (docx, xlsx, etc.)
        if expected_extension.lower() in ("docx", "xlsx", "pptx", "odt"):
            if detected_mime == "application/zip":
                return True, ""  # Accept ZIP as these are ZIP-based

        logger.warning(
            f"MIME type mismatch: expected {allowed_mimes}, got {detected_mime}"
        )
        return (
            False,
            f"File type mismatch: expected {expected_extension}, detected {detected_mime}",
        )

    # Verify magic number signature
    expected_sig = MAGIC_SIGNATURES.get(expected_extension.lower())
    if expected_sig and not file_content.startswith(expected_sig):
        logger.warning(f"Magic number mismatch for {expected_extension}")
        return False, f"Invalid file signature for {expected_extension} file"

    # FIX-5: Offset-aware video container check (mp4/mov box type at byte offset 4)
    ext_lower = expected_extension.lower()
    if ext_lower == "mp4" and len(file_content) >= 8:
        box_type = file_content[4:8]
        if box_type not in MP4_BOX_TYPES:
            logger.warning(f"MP4 box type mismatch: {box_type}")
            return False, "Invalid MP4 file structure"
    elif ext_lower == "mov" and len(file_content) >= 8:
        box_type = file_content[4:8]
        if box_type not in MOV_BOX_TYPES:
            logger.warning(f"MOV box type mismatch: {box_type}")
            return False, "Invalid MOV file structure"

    return True, ""


def validate_upload(
    file: UploadFile, expected_extension: str, category: str = "default"
) -> Tuple[bool, str]:
    """
    Synchronous wrapper for file upload validation.
    NOTE: This only validates the filename. File content validation requires
    the async `validate_upload_async()` because the file must be read.
    When content validation is needed in a sync context, read content first
    and call `validate_file_content()` directly.

    Returns:
        (is_valid, error_message)
    """
    # FIX-3: Was previously always returning True without any content check.
    # Now correctly validates filename and returns a helpful note if content
    # validation is still needed via the async path.
    is_valid, safe_filename = validate_filename(file.filename)
    if not is_valid:
        return False, "Invalid filename"

    # Check extension not in blocked list (filename-level only)
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower().lstrip(".")
    if ext in BLOCKED_EXTENSIONS:
        return False, f"File type '{ext}' is not allowed"

    # Caller must use validate_upload_async() for full MIME + magic byte checks
    return True, ""


async def validate_upload_async(
    file: UploadFile, expected_extension: str, category: str = "default"
) -> Tuple[bool, str]:
    """
    Async version of file upload validation.

    Args:
        file: FastAPI UploadFile object
        expected_extension: Expected file extension (e.g., "pdf", "jpg")
        category: File category for size limits

    Returns:
        (is_valid, error_message)
    """
    # Validate filename
    is_valid, safe_filename = validate_filename(file.filename)
    if not is_valid:
        return False, "Invalid filename"

    # Get max size for category
    max_size = get_max_file_size(category)

    # Read file content (up to max_size + buffer)
    content = b""
    read_size = 0
    chunk_size = 8192

    while read_size < max_size + chunk_size:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content += chunk
        read_size += len(chunk)

        # If we've read past max size, that's an issue
        if read_size > max_size:
            # Put back the extra
            await file.seek(0)
            return (
                False,
                f"File size exceeds maximum allowed ({max_size // (1024 * 1024)} MB)",
            )

    # Reset file pointer
    await file.seek(0)

    # Validate content
    is_valid, error_msg = validate_file_content(content, expected_extension, max_size)

    if not is_valid:
        return False, error_msg

    return True, ""


async def scan_file_for_malware(file: UploadFile) -> Tuple[bool, str]:
    """
    Placeholder for virus/malware scanning.

    In production, integrate with ClamAV or similar:
    - clamd (ClamAV daemon)
    - python-clamd-client
    - VirusTotal API

    Returns:
        (is_safe, error_message)
    """
    # TODO: Implement actual virus scanning
    # For now, just log the file info for monitoring
    file_size = 0
    content = b""

    while True:
        chunk = await file.read(8192)
        if not chunk:
            break
        content += chunk
        file_size += len(chunk)

        # Check size limit (100MB max for scanning)
        if file_size > 100 * 1024 * 1024:
            return False, "File too large for malware scanning"

    await file.seek(0)

    # Calculate hash for monitoring
    file_hash = hashlib.sha256(content).hexdigest()
    logger.info(f"File scanned: {file.filename}, hash: {file_hash[:16]}...")

    # TODO: Add actual virus scanning here
    # Example with ClamAV:
    # import clamd
    # cd = clamd.ClamdNetworkSocket()
    # result = cd.instream(content)
    # if result[0] == 'FOUND':
    #     return False, f"Malware detected: {result[1]}"

    return True, ""


def get_safe_content_type(filename: str) -> str:
    """
    Get safe content type for serving files.
    Prevents MIME type confusion attacks.
    """
    ext = os.path.splitext(filename)[1].lower().lstrip(".")

    safe_types = {
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "mp4": "video/mp4",
        "webm": "video/webm",
    }

    return safe_types.get(ext, "application/octet-stream")


def scan_for_malware(content: bytes, filename: str) -> Tuple[bool, str]:
    """
    Scan file content for malware indicators.
    Returns (is_safe, reason).

    NOTE: This is a lightweight heuristic scanner. For production,
    integrate with ClamAV or a cloud malware scanning service.
    """
    if not content or len(content) < 100:
        return True, ""

    # 1. Check for suspicious magic bytes / file signatures
    # PDF active-content security checks.
    #
    # IMPORTANT:
    # /OpenAction and /AA are not malicious by themselves. Legitimate PDFs
    # can use these entries for viewer behavior. We therefore inspect the
    # parsed PDF objects and reject only genuinely dangerous actions.
    if content[:5] == b"%PDF-":
        try:
            from io import BytesIO
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content), strict=False)

            def check_pdf_object(obj, seen=None):
                if seen is None:
                    seen = set()

                try:
                    obj_id = id(obj)
                    if obj_id in seen:
                        return None
                    seen.add(obj_id)

                    # Resolve indirect objects where possible.
                    if hasattr(obj, "get_object"):
                        obj = obj.get_object()

                    if isinstance(obj, dict):
                        # JavaScript action.
                        if "/JavaScript" in obj or "/JS" in obj:
                            return "PDF contains embedded JavaScript"

                        # Launch action can execute an external application.
                        action = obj.get("/S")
                        if action is not None:
                            try:
                                action = action.get_object()
                            except Exception:
                                pass

                        if str(action) in ("/Launch", "Launch"):
                            return "PDF contains a Launch action"

                        # Recurse through nested PDF objects.
                        for value in obj.values():
                            result = check_pdf_object(value, seen)
                            if result:
                                return result

                    elif isinstance(obj, (list, tuple)):
                        for value in obj:
                            result = check_pdf_object(value, seen)
                            if result:
                                return result

                except Exception:
                    # Parsing failures are handled separately below.
                    pass

                return None

            for page in reader.pages:
                result = check_pdf_object(page)
                if result:
                    return False, result

            # Check document-level objects, including OpenAction/AA.
            root = reader.trailer.get("/Root")
            if root is not None:
                result = check_pdf_object(root)
                if result:
                    return False, result

        except Exception as e:
            logger.warning(
                f"PDF security parsing failed; falling back to signature checks: {e}"
            )

    # Embedded executables in any format
    if b"MZ" in content[:2] or b"\x4d\x5a" in content[:2]:  # PE executable header
        return False, "Embedded executable detected"

    # OLE compound documents (old Office exploits)
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return False, "OLE compound document (potential exploit)"

    # 2. Check for suspicious content patterns
    try:
        text_content = content[:10000].decode("utf-8", errors="ignore").lower()

        # PowerShell scripts
        if "powershell" in text_content and (
            "-command" in text_content or "-c " in text_content
        ):
            if "invoke-expression" in text_content or "iex " in text_content:
                return False, "Suspicious PowerShell command"

        # VBScript
        if "<script" in text_content and (
            "vbscript" in text_content or "vbs:" in text_content
        ):
            return False, "VBScript detected"

        # Shell commands
        suspicious_cmds = [
            "wget ",
            "curl ",
            "nc -",
            "nmap",
            "meterpreter",
            "metasploit",
        ]
        for cmd in suspicious_cmds:
            if cmd in text_content:
                return False, f"Suspicious command: {cmd}"

    except Exception:
        pass  # Binary content - skip text check

    # 3. File extension mismatch check (basic heuristic)
    ext = os.path.splitext(filename)[1].lower()

    # If filename says PDF but content is not PDF
    if ext == ".pdf":
        if not content.startswith(b"%PDF-"):
            return False, "File extension mismatch"

    # 4. Archive bombs (zip bombs, tar bombs) - basic check
    if ext in [".zip", ".gz", ".tar", ".7z"]:
        # Check compression ratio - unrealistic ratios indicate zip bomb
        if len(content) < 1000 and "PK" in content[:4]:  # Zip identifier
            return True, ""  # Small zip - likely ok

    # 5. Executable content in wrong places
    dangerous_starts = [b"MZ", b"\x89PNG", b"\xff\xd8\xff", b"GIF", b"PK"]
    for header in dangerous_starts:
        if content[:10].startswith(header):
            # Known good format
            return True, ""

    # Check for other executable markers
    if b"#!/" in content[:100]:  # Shebang
        return False, "Executable script embedded"

    return True, ""
