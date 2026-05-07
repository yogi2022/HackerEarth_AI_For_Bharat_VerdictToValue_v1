#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# VerdictToValue — Setup Script
# ═══════════════════════════════════════════════════════════════
set -e

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║        VerdictToValue — Setup Script                ║"
echo "║   Agentic AI for Court Judgment Action Plans        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Python version check ──────────────────────────────────────
python3 --version 2>/dev/null || { echo "❌ Python 3 not found. Please install Python 3.9+"; exit 1; }
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python $PYTHON_VERSION found"

# ── Tesseract check ───────────────────────────────────────────
if command -v tesseract &> /dev/null; then
    echo "✅ Tesseract OCR found: $(tesseract --version 2>&1 | head -1)"
else
    echo "⚠️  Tesseract not found. OCR for scanned PDFs will be disabled."
    echo "   Install with: sudo apt-get install tesseract-ocr (Ubuntu)"
    echo "                 brew install tesseract (macOS)"
fi

# ── Create virtual environment ────────────────────────────────
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# ── Upgrade pip ───────────────────────────────────────────────
echo "⬆️  Upgrading pip..."
pip install --upgrade pip -q

# ── Install dependencies ──────────────────────────────────────
echo ""
echo "📥 Installing dependencies (this may take a few minutes)..."
echo "   Installing CPU-only PyTorch (saves ~1GB vs GPU version)..."

# Install CPU-only torch first to avoid downloading CUDA version
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu -q

echo "   Installing remaining packages..."
pip install -r requirements.txt -q

# ── spaCy model ───────────────────────────────────────────────
echo ""
echo "🧠 Downloading spaCy English model..."
python -m spacy download en_core_web_sm -q

# ── Create directories ────────────────────────────────────────
echo ""
echo "📁 Creating directories..."
mkdir -p sample_judgments data

# ── Initialize database ───────────────────────────────────────
echo "🗄️  Initializing SQLite database..."
python3 -c "from backend.database import init_db; init_db(); print('   Database initialized.')"

# ── Download HuggingFace models (optional, warn about size) ──
echo ""
echo "🤖 Pre-downloading AI models (first-time only, ~1.5GB)..."
echo "   This runs in background. The app will also download on first use."
python3 -c "
from transformers import pipeline
print('   Downloading summarization model...')
p = pipeline('summarization', model='facebook/bart-large-cnn', device=-1)
print('   ✅ BART model ready')
" 2>/dev/null || echo "   ⚠️  Model download skipped (will download on first use)"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║                 ✅ Setup Complete!                   ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  Next steps:                                         ║"
echo "║                                                      ║"
echo "║  1. Add PDF judgments to: sample_judgments/          ║"
echo "║                                                      ║"
echo "║  2. Start the server:                                ║"
echo "║     source venv/bin/activate                         ║"
echo "║     uvicorn backend.main:app --reload --port 8000    ║"
echo "║                                                      ║"
echo "║  3. Open browser:                                    ║"
echo "║     http://localhost:8000                            ║"
echo "║                                                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
