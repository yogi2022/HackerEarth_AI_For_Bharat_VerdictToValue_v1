"""
document_processor.py — PDF → Structured Text
Handles: digital PDFs, scanned PDFs (OCR), mixed PDFs
Tools: pdfplumber (primary), PyMuPDF (fallback/images), pytesseract (OCR)
"""
import re
import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    logger.warning("pdfplumber not available")

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    logger.warning("PyMuPDF not available")

try:
    import pytesseract
    from PIL import Image
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    logger.warning("pytesseract not available — scanned PDF support disabled")


@dataclass
class ExtractedDocument:
    """Result of document processing."""
    raw_text: str                     # Full text
    pages: List[str]                  # Per-page text
    page_count: int
    
    # Structural sections
    header_text: str = ""             # First ~500 chars (court header)
    body_text: str = ""               # Main body
    directions_section: str = ""     # Paragraph with "directed"/"ordered"
    
    # Metadata extracted from header
    court_from_header: str = ""
    case_number_raw: str = ""
    date_raw: str = ""
    judge_raw: str = ""
    
    # Quality
    is_scanned: bool = False
    extraction_method: str = "pdfplumber"
    char_count: int = 0
    warnings: List[str] = field(default_factory=list)


def process_pdf(filepath: str | Path) -> ExtractedDocument:
    """
    Main entry point: process a PDF file and return extracted document.
    Automatically falls back from pdfplumber → PyMuPDF → OCR.
    """
    filepath = Path(filepath)
    logger.info(f"Processing PDF: {filepath.name}")

    text = ""
    pages = []
    method = "unknown"
    is_scanned = False

    # ── Step 1: Try pdfplumber (best for digital PDFs) ─────────────────────────
    if HAS_PDFPLUMBER:
        try:
            text, pages = _extract_with_pdfplumber(filepath)
            method = "pdfplumber"
            logger.debug(f"pdfplumber extracted {len(text)} chars")
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}")

    # ── Step 2: If text is too short, try PyMuPDF ─────────────────────────────
    if len(text.strip()) < 200 and HAS_FITZ:
        try:
            text2, pages2 = _extract_with_fitz(filepath)
            if len(text2) > len(text):
                text, pages = text2, pages2
                method = "pymupdf"
                logger.debug(f"PyMuPDF extracted {len(text)} chars")
        except Exception as e:
            logger.warning(f"PyMuPDF failed: {e}")

    # ── Step 3: If still sparse, assume scanned → OCR ─────────────────────────
    if len(text.strip()) < 200:
        if HAS_TESSERACT and HAS_FITZ:
            logger.info("PDF appears to be scanned — running OCR...")
            try:
                text, pages = _extract_with_ocr(filepath)
                method = "tesseract_ocr"
                is_scanned = True
                logger.debug(f"OCR extracted {len(text)} chars")
            except Exception as e:
                logger.error(f"OCR failed: {e}")
        else:
            logger.warning("PDF is likely scanned but OCR not available")

    # ── Step 4: Clean and structure ───────────────────────────────────────────
    text = _clean_text(text)
    doc = _structure_document(text, pages, method, is_scanned)

    logger.info(
        f"Extracted {doc.char_count} chars via {doc.extraction_method} "
        f"({'scanned' if doc.is_scanned else 'digital'})"
    )
    return doc


def _extract_with_pdfplumber(filepath: Path) -> Tuple[str, List[str]]:
    pages_text = []
    with pdfplumber.open(str(filepath)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            pages_text.append(page_text)
    full_text = "\n\n".join(pages_text)
    return full_text, pages_text


def _extract_with_fitz(filepath: Path) -> Tuple[str, List[str]]:
    pages_text = []
    doc = fitz.open(str(filepath))
    for page in doc:
        pages_text.append(page.get_text("text"))
    doc.close()
    return "\n\n".join(pages_text), pages_text


def _extract_with_ocr(filepath: Path) -> Tuple[str, List[str]]:
    """Render PDF pages as images and OCR them."""
    pages_text = []
    doc = fitz.open(str(filepath))
    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at 300 DPI for good OCR quality
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        page_text = pytesseract.image_to_string(
            img,
            lang="eng",
            config="--psm 6 --oem 3"   # Assume uniform block of text
        )
        pages_text.append(page_text)
    doc.close()
    return "\n\n".join(pages_text), pages_text


def _clean_text(text: str) -> str:
    """Clean extracted text: normalize whitespace, fix common OCR errors."""
    if not text:
        return ""
    # Normalize line breaks
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\r', '\n', text)
    # Remove excessive blank lines (keep max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Fix common OCR artifacts
    text = re.sub(r'[|l]{2,}', '', text)          # | | | artifacts
    text = re.sub(r'(?<=[a-z])- (?=[a-z])', '', text)  # hyphenated line breaks
    # Normalize spaces
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Fix joined words from bad extraction (e.g., "thedirected" → keep as-is, too risky)
    return text.strip()


def _structure_document(
    text: str, pages: List[str], method: str, is_scanned: bool
) -> ExtractedDocument:
    """Split text into semantic sections for better downstream processing."""
    warnings = []
    
    if not text:
        warnings.append("Empty document — extraction may have failed")

    # Header = first ~600 chars (court, bench, case no, date)
    header_text = text[:600]
    body_text = text[600:] if len(text) > 600 else text

    # Find the "directions" / "order" section
    directions_section = _find_directions_section(text)

    # Extract structured metadata from header
    court = _extract_court_name(header_text)
    case_number = _extract_case_number(text)
    date = _extract_date_from_header(header_text)
    judge = _extract_judge_name(header_text)

    if not case_number:
        warnings.append("Could not extract case number from document")
    if not date:
        warnings.append("Could not extract date of judgment")

    return ExtractedDocument(
        raw_text=text,
        pages=pages,
        page_count=len(pages),
        header_text=header_text,
        body_text=body_text,
        directions_section=directions_section,
        court_from_header=court,
        case_number_raw=case_number,
        date_raw=date,
        judge_raw=judge,
        is_scanned=is_scanned,
        extraction_method=method,
        char_count=len(text),
        warnings=warnings,
    )


def _find_directions_section(text: str) -> str:
    """
    Find the paragraph(s) containing the actual court orders/directions.
    Searches for the conclusory part of the judgment.
    """
    # Common section markers in Indian judgments
    markers = [
        r"(?i)(in\s+the\s+result|in\s+the\s+circumstances|for\s+the\s+foregoing\s+reasons)",
        r"(?i)(accordingly[,\s].*?(?:directed|ordered))",
        r"(?i)(the\s+(?:writ\s+petition|appeal|revision)\s+is\s+(?:allowed|dismissed))",
        r"(?i)(it\s+is\s+(?:hereby\s+)?(?:directed|ordered|declared))",
        r"(?i)(we\s+(?:hereby\s+)?(?:direct|order|allow|dismiss))",
        r"(?i)(ORDER\s*:?\s*\n)",
        r"(?i)(DIRECTIONS?\s*:?\s*\n)",
        r"(?i)(CONCLUSION\s*:?\s*\n)",
    ]

    best_pos = len(text)
    for pattern in markers:
        match = re.search(pattern, text)
        if match:
            best_pos = min(best_pos, match.start())

    if best_pos < len(text):
        # Return from that position to end (or 2000 chars max)
        section = text[best_pos:best_pos + 3000]
        return section.strip()

    # Fallback: return last 1500 chars (orders are usually at the end)
    return text[-1500:].strip() if len(text) > 1500 else text


def _extract_court_name(header: str) -> str:
    """Extract court name from document header."""
    patterns = [
        r"(?i)(HIGH COURT OF [A-Z\s]+)",
        r"(?i)(IN THE HIGH COURT OF [A-Z\s]+)",
        r"(?i)(SUPREME COURT OF INDIA)",
        r"(?i)(DISTRICT COURT[,\s]+[A-Z\s]+)",
    ]
    for pat in patterns:
        m = re.search(pat, header)
        if m:
            return m.group(1).strip()[:80]
    return ""


def _extract_case_number(text: str) -> str:
    """Extract case number (WP, W.P.C., CWP, etc.)."""
    patterns = [
        r"(?i)(W\.?P\.?\s*(?:No\.?|Petition)?\s*[\(\[]?\s*(?:Civil|Crl|C)?\s*[\)\]]?\s*\d+\s*/\s*\d{4})",
        r"(?i)(CWP[-\s]*\d+/\d{4})",
        r"(?i)(WRIT\s+PETITION\s+(?:CIVIL\s+)?NO\.?\s*\d+\s+OF\s+\d{4})",
        r"(?i)((?:Civil|Criminal)\s+Appeal\s+(?:No\.?)?\s*\d+\s+(?:of|/)\s*\d{4})",
        r"(?i)(S\.?L\.?P\.?\s*(?:\(Civil\))?\s*(?:No\.?)?\s*\d+\s+(?:of|/)\s*\d{4})",
        r"(?i)(O\.?S\.?\s*(?:No\.?)?\s*\d+\s*/\s*\d{4})",
        r"(?i)(R\.?S\.?A\.?\s*(?:No\.?)?\s*\d+\s*/\s*\d{4})",
        # Generic case number pattern
        r"(?i)([A-Z]{1,4}[\.\s]*\d+[\s/]+\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text[:2000])  # Usually in first 2000 chars
        if m:
            return m.group(1).strip()
    return ""


def _extract_date_from_header(header: str) -> str:
    """Extract date from judgment header."""
    patterns = [
        # "Dated this the 15th day of March, 2024"
        r"(?i)dated?\s+(?:this\s+)?(?:the\s+)?\d{1,2}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(\w+[,\s]+\d{4})",
        # "15.03.2024" or "15/03/2024"
        r"\b(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})\b",
        # "15 March 2024"
        r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
        # "March 15, 2024"
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
    ]
    for pat in patterns:
        m = re.search(pat, header, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_judge_name(header: str) -> str:
    """Extract judge name(s)."""
    patterns = [
        r"(?i)(?:HON'?BLE|BEFORE(?:\s+THE\s+HON'?BLE)?)\s+(?:MR\.?|MS\.?|MRS\.?\s+)?(?:JUSTICE\s+)?([A-Z][A-Z\.\s]+(?:J\.|JUDGE|JUSTICE)?)",
        r"(?i)(JUSTICE\s+[A-Z][A-Z\.\s,]+)",
        r"(?i)(CORAM\s*:\s*[A-Z][A-Z\.\s,J\.]+)",
    ]
    for pat in patterns:
        m = re.search(pat, header)
        if m:
            return m.group(1).strip()[:100]
    return ""
