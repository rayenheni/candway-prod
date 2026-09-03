import io
import logging

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts text from PDF bytes using pypdf.
    Returns empty string if parsing fails or pypdf is missing.
    """
    text = ""

    try:
        import pypdf

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
            return text.strip()
        except Exception as e:
            logger.warning(f"pypdf parsing failed: {e}")
    except ImportError:
        logger.error("pypdf is not installed.")

    return text.strip()
