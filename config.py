"""
config.py — VerdictToValue Configuration
All tunable settings in one place.
"""
import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "verdicts.db"
SAMPLE_JUDGMENTS_DIR = BASE_DIR / "sample_judgments"
FRONTEND_DIR = BASE_DIR / "frontend"

# Create dirs if not exist
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

# ── Model Settings ─────────────────────────────────────────────────────────────
# HuggingFace models (all free)
SUMMARIZATION_MODEL = "facebook/bart-large-cnn"  # ~1.6GB, best free summarizer
NER_MODEL = "en_core_web_sm"                      # spaCy NER model

# Use smaller/faster model for low-RAM systems
FAST_MODE = os.getenv("FAST_MODE", "false").lower() == "true"
if FAST_MODE:
    SUMMARIZATION_MODEL = "sshleifer/distilbart-cnn-12-6"  # ~300MB, faster

# ── Processing Settings ────────────────────────────────────────────────────────
MAX_PDF_SIZE_MB = 50          # Reject PDFs larger than this
MAX_CHUNK_SIZE = 1000         # Characters per chunk
CHUNK_OVERLAP = 150           # Overlap between chunks
MAX_SUMMARY_LENGTH = 200      # Max summary tokens
MIN_SUMMARY_LENGTH = 60       # Min summary tokens

# ── Legal Domain Settings ──────────────────────────────────────────────────────

# Keywords that indicate a MANDATORY directive from the court
DIRECTIVE_KEYWORDS = [
    "directed", "hereby directed", "is directed", "are directed",
    "ordered", "hereby ordered", "is ordered",
    "shall", "must", "ought to",
    "mandated", "commanded",
    "instructed to", "required to",
    "writ of mandamus", "writ petition allowed",
    "petition is allowed", "allowed with directions",
    "compliance be filed", "compliance affidavit",
    "contempt", "coercive steps",
]

# Keywords indicating the petition was DISMISSED (no compliance needed)
DISMISSED_KEYWORDS = [
    "petition dismissed", "writ petition dismissed",
    "application dismissed", "stands dismissed",
    "appeal dismissed", "dismissed as withdrawn",
    "no merit", "lacks merit", "without merit",
    "petition fails", "petition is rejected",
]

# Keywords indicating APPEAL is advisable
APPEAL_INDICATORS = [
    "against the state", "financial liability",
    "retrospective effect", "policy matter",
    "large number of employees", "precedent",
    "public exchequer",
]

# Deadline extraction patterns (regex)
DEADLINE_PATTERNS = [
    r"within\s+(\w+)\s+(days?|weeks?|months?)",
    r"(\d+)\s+(days?|weeks?|months?)\s+from",
    r"within a period of\s+(\w+)\s+(days?|weeks?|months?)",
    r"not later than\s+(\d+)\s+(days?|weeks?|months?)",
    r"before\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    r"by\s+(\d{1,2}\s+\w+\s+\d{4})",
]

# Number words → integers
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "thirty": 30, "forty": 40, "sixty": 60, "ninety": 90,
}

# Department keyword mapping
DEPARTMENT_KEYWORDS = {
    "Revenue & Land Records": [
        "revenue", "land records", "patta", "khata", "survey", "mutation",
        "land acquisition", "tahsildar", "deputy commissioner", "dc office",
        "village accountant", "RTC", "RDO",
    ],
    "Finance": [
        "pension", "gratuity", "salary", "pay", "allowance", "arrears",
        "treasury", "accounts", "audit", "financial", "budget", "funds",
        "director of treasuries", "accountant general", "PAO",
    ],
    "Public Works": [
        "road", "building", "construction", "tender", "contractor",
        "PWD", "infrastructure", "bridge", "highway", "NHAI",
    ],
    "Health": [
        "hospital", "medical", "doctor", "nurse", "health", "AYUSH",
        "drug", "pharmaceutical", "patient", "treatment", "health dept",
    ],
    "Municipal": [
        "municipal", "BBMP", "GHMC", "corporation", "urban", "ward",
        "drainage", "sewage", "water supply", "property tax", "ULB",
    ],
    "Forest": [
        "forest", "wildlife", "encroachment", "tribal", "forest land",
        "forest department", "range forest officer",
    ],
    "Home / Police": [
        "police", "FIR", "arrest", "custody", "bail", "investigation",
        "transfer", "posting", "SP", "DGP", "IPS",
    ],
    "Education": [
        "school", "college", "university", "teacher", "professor",
        "appointment", "promotion", "UGC", "AICTE", "DEO",
    ],
    "Labour": [
        "labour", "employee", "workman", "factory", "ESI", "PF",
        "industrial dispute", "reinstatement", "termination", "dismissal",
    ],
    "General Administration": [
        "transfer", "posting", "promotion", "seniority", "IAS", "IPS",
        "government servant", "service matter", "disciplinary",
    ],
}

# Contempt risk: if deadline ≤ this many days, flag contempt risk
CONTEMPT_RISK_DAYS = 14

# ── API Settings ───────────────────────────────────────────────────────────────
API_TITLE = "VerdictToValue API"
API_VERSION = "1.0.0"
API_DESCRIPTION = "Agentic AI System for Court Judgment Action Plans"
ALLOWED_ORIGINS = ["*"]   # In production, restrict to your domain

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
