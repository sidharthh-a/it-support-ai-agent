import io
import pytest


def test_valid_pdf_upload(client):
    """Test valid PDF upload through POST /api/v1/knowledge/upload."""
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 70 >>\nstream\nBT /F1 12 Tf 50 750 Td (Valid PDF document content for upload test) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000113 00000 n \n0000000236 00000 n \n0000000357 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n428\n%%EOF\n"
    )
    
    response = client.post(
        "/api/v1/knowledge/upload",
        data={"title": "Test PDF Guide", "category": "Network"},
        files={"file": ("guide.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test PDF Guide"
    assert data["file_type"] == "pdf"


def test_oversized_upload_rejected(client):
    """Test upload exceeding 10 MB limit is rejected with HTTP 400."""
    # 10 MB + 1 byte
    large_bytes = b"A" * (10 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/knowledge/upload",
        data={"title": "Large File", "category": "General"},
        files={"file": ("large.txt", io.BytesIO(large_bytes), "text/plain")}
    )
    assert response.status_code == 400
    assert "10 MB" in response.json()["detail"]


def test_unsupported_extension_rejected(client):
    """Test upload with unsupported extension (e.g., .exe) is rejected with HTTP 400."""
    response = client.post(
        "/api/v1/knowledge/upload",
        data={"title": "Executable File", "category": "General"},
        files={"file": ("malicious.exe", io.BytesIO(b"binary content"), "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_invalid_pdf_content_rejected(client):
    """Test PDF upload with invalid header content is rejected with HTTP 400."""
    response = client.post(
        "/api/v1/knowledge/upload",
        data={"title": "Fake PDF", "category": "General"},
        files={"file": ("fake.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")}
    )
    assert response.status_code == 400
    assert "does not match a valid PDF document" in response.json()["detail"]
