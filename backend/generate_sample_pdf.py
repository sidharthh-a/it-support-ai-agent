"""
Generate a valid sample PDF for IT support VPN troubleshooting.

Uses fpdf2 (if available) for a proper PDF, otherwise constructs a
byte-exact raw PDF with correctly calculated xref offsets.

Run from the backend/ directory:
    python generate_sample_pdf.py
"""
import os
import struct

os.makedirs("sample_docs", exist_ok=True)
pdf_path = os.path.join("sample_docs", "vpn_troubleshooting_guide.pdf")


def _generate_with_fpdf() -> bool:
    """Try generating a proper PDF using fpdf2."""
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Corporate VPN Setup and Troubleshooting Guide", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Error: ERR_VPN_AUTH_401 — Gateway Authentication Timeout", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font("Helvetica", size=11)
        steps = [
            "Symptom: GlobalProtect client hangs at 98% connection with ERR_VPN_AUTH_401.",
            "",
            "Resolution Steps:",
            "1. Open GlobalProtect Client and click Disconnect.",
            "2. Flush DNS cache:",
            "   - Windows: ipconfig /flushdns",
            "   - macOS:   sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder",
            "3. Verify your domain credentials are not expired (check Okta SSO).",
            "4. Ensure your 802.1X certificate is valid: Settings > Certificates > ACME-Root-CA-2026.crt",
            "5. Reconnect GlobalProtect and select nearest gateway (us-east-1 or eu-west-1).",
            "6. If issue persists, collect debug logs: GlobalProtect > Troubleshooting > Collect Logs.",
            "",
            "Error Code Reference:",
            "  ERR_VPN_AUTH_401  — TLS handshake failed / certificate not trusted",
            "  ERR_VPN_TIMEOUT   — Gateway unreachable (check firewall rules on port 443/4501)",
            "  ERR_VPN_NO_ROUTE  — Routing table conflict; disable local split-tunnel adapters",
            "",
            "Escalation: If unresolved after steps above, raise ticket category=network priority=high.",
        ]
        for line in steps:
            pdf.multi_cell(0, 6, line)

        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Wi-Fi 802.1X Certificate Issues", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("Helvetica", size=11)
        wifi_steps = [
            "Symptom: Wi-Fi disconnects or prompts for credentials repeatedly.",
            "",
            "Resolution:",
            "1. Download and install ACME-Root-CA-2026.crt from https://it.acme-corp.internal/certs",
            "2. Trust the certificate in Keychain Access (macOS) or Certificate Manager (Windows).",
            "3. Reconnect to ACME-CORP-SECURE SSID.",
        ]
        for line in wifi_steps:
            pdf.multi_cell(0, 6, line)

        pdf.output(pdf_path)
        print(f"[fpdf2] Generated valid PDF at {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[fpdf2] Failed: {e}")
        return False


def _generate_raw_pdf() -> None:
    """
    Generate a byte-exact valid PDF with correctly computed xref offsets.
    No external dependencies required — only stdlib.
    """
    content_stream = (
        b"BT\n"
        b"/F1 14 Tf\n"
        b"50 750 Td\n"
        b"(Corporate VPN Setup & Troubleshooting Guide) Tj\n"
        b"0 -24 Td\n"
        b"/F1 11 Tf\n"
        b"(Error ERR_VPN_AUTH_401: TLS Handshake / Gateway Auth Timeout) Tj\n"
        b"0 -18 Td\n"
        b"(1. Disconnect GlobalProtect client completely.) Tj\n"
        b"0 -16 Td\n"
        b"(2. Flush DNS: ipconfig /flushdns  OR  sudo dscacheutil -flushcache) Tj\n"
        b"0 -16 Td\n"
        b"(3. Verify Okta credentials are not expired.) Tj\n"
        b"0 -16 Td\n"
        b"(4. Reinstall ACME-Root-CA-2026.crt certificate.) Tj\n"
        b"0 -16 Td\n"
        b"(5. Reconnect and select nearest gateway.) Tj\n"
        b"0 -16 Td\n"
        b"(6. Collect debug logs if issue persists.) Tj\n"
        b"ET\n"
    )
    content_len = len(content_stream)

    # Build objects as bytes first so we can compute exact offsets
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        b"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
    )
    obj4 = (
        f"4 0 obj\n<< /Length {content_len} >>\nstream\n"
    ).encode() + content_stream + b"endstream\nendobj\n"
    obj5 = (
        b"5 0 obj\n"
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica\n"
        b"   /Encoding /WinAnsiEncoding >>\n"
        b"endobj\n"
    )

    header = b"%PDF-1.4\n"

    # Compute offsets
    off1 = len(header)
    off2 = off1 + len(obj1)
    off3 = off2 + len(obj2)
    off4 = off3 + len(obj3)
    off5 = off4 + len(obj4)
    xref_offset = off5 + len(obj5)

    xref = (
        b"xref\n"
        b"0 6\n"
        b"0000000000 65535 f \n"
        + f"{off1:010d} 00000 n \n".encode()
        + f"{off2:010d} 00000 n \n".encode()
        + f"{off3:010d} 00000 n \n".encode()
        + f"{off4:010d} 00000 n \n".encode()
        + f"{off5:010d} 00000 n \n".encode()
    )
    trailer = (
        f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode()

    pdf_data = header + obj1 + obj2 + obj3 + obj4 + obj5 + xref + trailer

    with open(pdf_path, "wb") as f:
        f.write(pdf_data)
    print(f"[raw] Generated valid PDF at {pdf_path} ({len(pdf_data)} bytes)")


if not _generate_with_fpdf():
    _generate_raw_pdf()
