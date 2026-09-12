import io
import re
from typing import List
from app.core.logging import logger

try:
    import pypdf
except ImportError:
    pypdf = None


def extract_text_from_file_bytes(file_bytes: bytes, filename: str) -> str:
    """Extracts text content from uploaded PDF, TXT, or Markdown file bytes."""
    fname_lower = filename.lower()

    if fname_lower.endswith(".pdf"):
        if not pypdf:
            raise ValueError("pypdf is not installed on the system.")
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            text_pages = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_pages.append(extracted)
            return "\n\n".join(text_pages)
        except Exception as e:
            logger.error(f"Error parsing PDF file {filename}: {e}")
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")

    # TXT, Markdown, or default text formats
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1", errors="replace")


# Regex to detect heading lines: Markdown headings OR short ALL-CAPS lines
_HEADING_RE = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Z0-9 :/-]{3,60})$")


def _is_heading(line: str) -> bool:
    """Returns True if the line looks like a section heading."""
    stripped = line.strip()
    if not stripped:
        return False
    return bool(_HEADING_RE.match(stripped))


def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 40,
) -> List[str]:
    """
    Splits text into overlapping word-based chunks.

    Strategy:
    - Split text into paragraphs (double newline boundaries) first, so headings
      and numbered steps that appear together stay together.
    - Accumulate paragraphs into a chunk until it reaches `chunk_size` words.
    - Start the next chunk with the last `overlap` words of the previous chunk
      so context carries across boundaries.
    - Headings always start a fresh chunk boundary (never buried mid-chunk).

    Parameters
    ----------
    text : str
        Raw extracted document text.
    chunk_size : int
        Maximum number of words per chunk (default 400 ≈ ~1 800 characters).
    overlap : int
        Number of words from the end of the previous chunk to prepend to the
        next one (default 40 words ≈ 2–3 sentences of context).

    Returns
    -------
    List[str]
        Non-empty, stripped chunk strings.
    """
    if not text:
        return []

    # Normalise excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: List[str] = []
    current_words: List[str] = []
    overlap_words: List[str] = []

    def _flush() -> None:
        """Save current_words as a chunk and prepare the overlap carry-over."""
        nonlocal current_words, overlap_words
        if current_words:
            chunk_text_str = " ".join(current_words).strip()
            if chunk_text_str:
                chunks.append(chunk_text_str)
            # Carry over the last `overlap` words into the next chunk
            overlap_words = current_words[-overlap:] if len(current_words) > overlap else list(current_words)
            current_words = []

    for para in paragraphs:
        para_words = para.split()
        if not para_words:
            continue

        # If the paragraph starts with a heading, flush the current chunk first.
        first_line = para.split("\n")[0].strip()
        if _is_heading(first_line) and current_words:
            _flush()
            # Start new chunk with overlap carry-over
            current_words = list(overlap_words)
            overlap_words = []

        # If adding this paragraph would exceed chunk_size, flush first.
        if current_words and (len(current_words) + len(para_words) > chunk_size):
            _flush()
            current_words = list(overlap_words)
            overlap_words = []

        # Handle a single paragraph that is itself larger than chunk_size.
        if len(para_words) > chunk_size:
            # Flush any accumulated words first
            if current_words:
                _flush()
                current_words = list(overlap_words)
                overlap_words = []
            # Split the large paragraph into word windows
            start = 0
            while start < len(para_words):
                window = para_words[start: start + chunk_size]
                # prepend overlap only for continuation windows
                if start > 0:
                    prefix = para_words[max(0, start - overlap): start]
                    window = prefix + window
                chunks.append(" ".join(window).strip())
                start += chunk_size
            overlap_words = para_words[-overlap:]
        else:
            current_words.extend(para_words)

    # Flush any remaining words
    if current_words:
        _flush()

    return [c for c in chunks if c]
