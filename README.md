# HackerEarth_AI_For_Bharat_VerdictToValue_v1
Court judgments contain critical decisions, but these are buried in lengthy legal text and require manual interpretation. Even with digital systems like CCMS, officers must identify directives, deadlines, and responsibilities themselves, creating risks of delay, inconsistent decisions,in high-pressure administrative workflows.


# VerdictToValue 🏛️
### Agentic AI System for Transforming Court Judgments into Verified Government Action Plans

> Aligned with: **eCourts Mission Mode Project** · **NIC/CCMS** · **Digital India** · **Karnataka/Telangana HC Judgments**

---

## Overview

VerdictToValue converts complex court judgment PDFs into structured, human-verified administrative action plans

---

## Tech Stack (All Free)

| Layer | Tool | Why |
|---|---|---|
| PDF Extraction | `pdfplumber` + `PyMuPDF (fitz)` | Best-in-class free PDF parsing |
| OCR (scanned PDFs) | `pytesseract` + `Tesseract` | Free OCR engine |
| NLP / AI | `transformers` (HuggingFace) + `spacy` | Free local models |
| Summarization | `facebook/bart-large-cnn` (HF) | Free summarization model |
| NER / Legal Terms | `en_core_web_sm` spaCy model | Free NER |
| Embeddings | `sentence-transformers` | Free semantic search |
| Web Framework | `FastAPI` | Fast, modern Python API |
| Frontend | Vanilla HTML/CSS/JS (existing) | No framework needed |
| Storage | SQLite (via `sqlite3`) | Zero-config DB |
| Document Intelligence | `docling` (IBM) | Free structured extraction |

---

## Project Structure

```
verdict_to_value/
├── README.md                    ← You are here
├── requirements.txt             ← All Python dependencies
├── setup.sh                     ← One-command setup script
│
├── backend/
│   ├── main.py                  ← FastAPI app entry point
│   ├── config.py                ← Configuration & constants
│   ├── database.py              ← SQLite schema & operations
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── extraction_agent.py      ← Pulls facts: case no, parties, dates
│   │   ├── legal_understanding_agent.py  ← Finds directives vs observations
│   │   ├── action_plan_agent.py         ← Generates comply/appeal + deadline
│   │   └── explainability_agent.py      ← Links outputs to source text
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── document_processor.py   ← PDF → structured text (pdfplumber + docling)
│   │   ├── chunker.py              ← Smart legal document chunking
│   │   └── orchestrator.py         ← Runs all agents in sequence
│   │
│   └── routers/
│       ├── __init__.py
│       ├── upload.py               ← POST /upload endpoint
│       ├── review.py               ← GET/POST /review endpoints
│       └── dashboard.py            ← GET /dashboard endpoint
│
├── frontend/
│   └── index.html               ← Full UI (enhanced from original)
│
├── sample_judgments/            ← Put your PDF files here
│   └── README.md
│
├── data/
│   └── verdicts.db              ← SQLite database (auto-created)
│
└── tests/
    └── test_pipeline.py         ← Basic tests
```

---

## Prerequisites

### System Requirements
- Python 3.9+
- 4GB RAM minimum (8GB recommended for HuggingFace models)
- ~2GB disk for models (downloaded once, cached)

### Install Tesseract OCR (for scanned PDFs)

**Ubuntu/Debian:**
```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

---

## Quick Start

### Step 1 — Clone / extract the project
```bash
cd verdict_to_value/
```

### Step 2 — Run setup (creates venv, installs deps)
```bash
chmod +x setup.sh
./setup.sh
```

OR manually:
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Step 3 — Add PDF judgments
```bash
# Copy your judgment PDFs to:
cp your_judgments/*.pdf sample_judgments/

# Or use our sample downloader (fetches from Indian Kanoon public domain):
python backend/utils/download_samples.py
```

### Step 4 — Start the backend
```bash
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

### Step 5 — Open the frontend
Open `frontend/index.html` in your browser **OR** visit:
```
http://localhost:8000
```
(Backend also serves the frontend)

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload PDF judgment for processing |
| `GET` | `/api/review` | Get all pending items for human review |
| `POST` | `/api/review/{id}/approve` | Approve AI output → moves to dashboard |
| `POST` | `/api/review/{id}/edit` | Edit + approve with corrections |
| `POST` | `/api/review/{id}/reject` | Reject → removes from queue |
| `GET` | `/api/dashboard` | Get all verified action plans |
| `GET` | `/api/dashboard/export/csv` | Export dashboard as CSV |
| `GET` | `/api/stats` | Aggregate statistics |
| `GET` | `/api/health` | System health check |

---

## How the AI Pipeline Works

```
PDF Upload
    ↓
[Document Processor]
  - pdfplumber extracts text from digital PDFs
  - pytesseract OCR handles scanned copies
  - Detects: case number, court name, date, judge name
    ↓
[Chunker]
  - Splits by legal sections (facts, findings, directions)
  - Creates overlapping chunks for context preservation
    ↓
[Extraction Agent]
  - spaCy NER: persons, organizations, dates, money
  - Regex patterns for Indian legal formats
  - Extracts: parties, case number, court, date of judgment
    ↓
[Legal Understanding Agent]
  - Identifies directive paragraphs vs observations
  - Keywords: "directed", "ordered", "shall", "within"
  - Classifies: mandatory order / advisory / dismissed
    ↓
[Action Plan Agent]
  - Determines: COMPLY vs APPEAL vs SEEK LEGAL REVIEW
  - Extracts deadlines (explicit + inferred from legal norms)
  - Maps to responsible government department
  - Flags contempt risk (if timeline < 14 days)
    ↓
[Explainability Layer]
  - Links every conclusion to source paragraph
  - Confidence scoring (rule-based + model-based)
  - Highlights citation text in original document
    ↓
[Human Verification UI]
  - Official reviews AI output
  - Can edit directive, deadline, department
  - Approve / Edit+Approve / Reject
    ↓
[Verified Dashboard]
  - Only approved cases appear
  - Searchable, filterable, exportable
```

---

## Government Integration Points

### eCourts / CIS Integration (Phase 2)
The system is designed for direct integration with:
- **CIS (Case Information System)** via NIC APIs
- **CCMS** document ingestion pipelines
- HC Karnataka / HC Telangana judgment repositories

### Indian Kanoon (Demo/Phase 1)
For hackathon demo, judgments can be sourced from:
- https://indiankanoon.org (public domain)
- High Court of Karnataka: https://hckinfo.kar.nic.in
- High Court of Telangana: https://hcts.gov.in

---

## Limitations & Notes

1. **Model accuracy** — The free HuggingFace models are good but not perfect. The human verification step is mandatory and compensates for this.
2. **First run is slow** — HuggingFace models (~1.5GB) download on first run. Subsequent runs use cache.
3. **Scanned PDFs** — OCR works but accuracy depends on scan quality. Digital PDFs give best results.
4. **Language** — Currently English only. Hindi/Kannada/Telugu support planned.

---

## Contributing / Hackathon Notes

This is built for:
- **Smart India Hackathon / State Hackathons**
- **eCourts Mission Mode Project** alignment
- **Digital India** e-governance goals

**We are not automating decisions — we are enabling faster, traceable governance.**
