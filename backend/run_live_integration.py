import os
import sys
import json
import io
from datetime import datetime, timezone, timedelta

# Fix Windows console Unicode print encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Load dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from sqlalchemy.orm import Session, sessionmaker
from app.db.session import engine, SessionLocal
from app.db.base import Base
import app.models  # Register all models

from app.models.user import User
from app.models.device import Device
from app.models.ticket import SupportTicket
from app.models.error_log import ErrorLog
from app.rag.service import RAGService
from app.agents.agent_graph import build_and_run_agent
from app.tools.agent_tools import create_agent_tools


def run_live_integration():
    print("=" * 80)
    print("🚀 LIVE INTEGRATION TEST: REAL PDF INGESTION, VECTOR RAG, SQL TOOLS & AGENT")
    print("=" * 80)

    # Check Gemini API Key status
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        print(f"✅ GEMINI_API_KEY detected: {gemini_key[:6]}...{gemini_key[-4:]}")
        print(f"🤖 Gemini Model: {os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')}")
    else:
        print("⚠️ GEMINI_API_KEY is NOT set in environment or .env file.")
        print("ℹ️ Running live integration test using Grounded Dual-Retrieval Agent Engine.")

    print("\n--- STEP 1: DATABASE INITIALIZATION & SEED ---")

    # Print embedding configuration
    from app.rag.embeddings import embedding_service
    print(f"🔢 Embedding Provider: {embedding_service.provider}")
    print(f"🔢 Embedding Dimension: {embedding_service.dimension}")
    if embedding_service.provider == "local":
        from app.core.config import settings
        print(f"🤖 Local Embedding Model: {settings.LOCAL_EMBEDDING_MODEL}")

    # Connect to PostgreSQL — do NOT fall back to SQLite for the real integration test
    test_engine = engine
    try:
        with engine.connect() as conn:
            conn.execute(__import__('sqlalchemy').text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        print("✅ PostgreSQL connection verified on port 5432 with pgvector extension enabled.")
    except Exception as pg_err:
        print(f"❌ PostgreSQL connection FAILED: {pg_err}")
        print("   Ensure the Docker container is running: docker compose up -d db")
        print("   Then run migrations: alembic upgrade head")
        raise SystemExit(1)

    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db: Session = TestingSession()


    try:
        # Create user & device if missing
        user = db.query(User).filter_by(email="alice.test@acme-corp.com").first()
        if not user:
            user = User(email="alice.test@acme-corp.com", full_name="Alice Smith", role="user", department="Engineering")
            db.add(user)
            db.commit()
            db.refresh(user)

        device = db.query(Device).filter_by(serial_number="C02LIVE12345").first()
        if not device:
            device = Device(user_id=user.id, device_name="Alice-MacBookPro-16", serial_number="C02LIVE12345", os="macOS Sonoma 14.4", status="active")
            db.add(device)
            db.commit()
            db.refresh(device)

        # Seed historical ticket
        existing_ticket = db.query(SupportTicket).filter_by(ticket_number="TICK-LIVE-9001").first()
        if not existing_ticket:
            existing_ticket = SupportTicket(
                ticket_number="TICK-LIVE-9001",
                title="GlobalProtect VPN Gateway Timeout ERR_VPN_AUTH_401",
                description="Unable to connect to US-East corporate VPN node. Client hangs at 98% throwing ERR_VPN_AUTH_401.",
                status="resolved",
                priority="high",
                category="network",
                user_id=user.id,
                device_id=device.id
            )
            db.add(existing_ticket)

        # Seed error log
        existing_log = db.query(ErrorLog).filter_by(error_code="ERR_VPN_AUTH_401").first()
        if not existing_log:
            existing_log = ErrorLog(
                device_id=device.id,
                ticket_id=existing_ticket.id if existing_ticket else None,
                service_name="GlobalProtect-Service",
                error_code="ERR_VPN_AUTH_401",
                log_message="TLS connection failed: Remote server closed handshake unexpectedly during SSL negotiations.",
                stack_trace="at VPNClient.Connect() line 142\nat NetworkGateway.EstablishTunnel() line 88",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=2)
            )
            db.add(existing_log)

        db.commit()
        print("✅ Database prepared with synthetic user, device, ticket (TICK-LIVE-9001), and log (ERR_VPN_AUTH_401).")

        print("\n--- STEP 2: REAL PDF DOCUMENT INGESTION & VECTOR RAG ---")
        rag = RAGService(db)
        pdf_path = os.path.join("sample_docs", "vpn_troubleshooting_guide.pdf")
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at {pdf_path}")

        print(f"📄 Reading PDF file: {pdf_path}")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        ingested_doc = rag.ingest_file_bytes(
            title="Corporate VPN Setup & Troubleshooting Guide (PDF)",
            category="Network",
            file_bytes=pdf_bytes,
            filename="vpn_troubleshooting_guide.pdf",
            source_url="https://wiki.acme-corp.internal/net/vpn-pdf"
        )
        print(f"✅ Ingested PDF Document ID: {ingested_doc.id}")
        print(f"   Title: {ingested_doc.title}")
        print(f"   Chunks Created: {len(ingested_doc.chunks)}")

        print("\n--- STEP 3: PERFORM VECTOR SEMANTIC RETRIEVAL ---")
        rag_results = rag.search_knowledge("How do I fix ERR_VPN_AUTH_401 in GlobalProtect?", limit=2)
        print(f"🔍 Vector Search Results ({len(rag_results)} matches):")
        for idx, r in enumerate(rag_results):
            print(f"   [{idx+1}] Match Score: {r.get('score', 0.95)*100:.1f}% | Doc: '{r['title']}'")
            print(f"       Chunk Content: {r['content'][:180]}...\n")

        print("\n--- STEP 4: EXECUTE CONTROLLED SQL REPOSITORY TOOL CALLS ---")
        tools = create_agent_tools(db)
        tool_map = {t.name: t for t in tools}

        sql_tickets_res = tool_map["search_tickets"].invoke({"query": "ERR_VPN_AUTH_401"})
        print("🛠 Tool Call: search_tickets(query='ERR_VPN_AUTH_401')")
        print(f"   Output:\n{sql_tickets_res}\n")

        sql_logs_res = tool_map["search_error_logs"].invoke({"error_code": "ERR_VPN_AUTH_401"})
        print("🛠 Tool Call: search_error_logs(error_code='ERR_VPN_AUTH_401')")
        print(f"   Output:\n{sql_logs_res}\n")

        print("\n--- STEP 5: COMBINED RAG + SQL AGENT QUERY ---")
        user_query = "My VPN keeps disconnecting with ERR_VPN_AUTH_401. Has this happened before and how do I fix it?"
        print(f"🗣 User Prompt: \"{user_query}\"\n")

        response = build_and_run_agent(db, user_query)

        print("📋 AGENT TOOL EXECUTIONS:")
        for t in response.tools_used:
            print(f"   • Tool: {t.tool_name}")
            print(f"     Args: {t.arguments}")
            print(f"     Summary: {t.result_summary[:120]}...\n")

        print("=" * 80)
        print("💬 FINAL GROUNDED AGENT RESPONSE:")
        print("=" * 80)
        print(response.answer)
        print("=" * 80)

    except Exception as e:
        print(f"❌ Error during live integration test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    run_live_integration()
