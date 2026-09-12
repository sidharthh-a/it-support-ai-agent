import os
import sys
import random
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.db.session import engine, SessionLocal
from app.db.base import Base
import app.models  # Register all models

from app.models.user import User
from app.models.device import Device
from app.models.ticket import SupportTicket
from app.models.incident import Incident
from app.models.error_log import ErrorLog
from app.models.resolution import Resolution
from app.models.ticket_history import TicketHistory
from app.models.knowledge import KnowledgeDocument
from app.rag.service import RAGService


FIRST_NAMES = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry", "Isabella", "Jack", "Kate", "Liam", "Mia", "Noah", "Olivia", "Peter", "Quinn", "Rachel", "Sam", "Sophia", "Thomas", "Victoria", "William", "Xavier", "Yara", "Zack"]
LAST_NAMES = ["Smith", "Jones", "Williams", "Taylor", "Brown", "Davies", "Evans", "Wilson", "Thomas", "Roberts", "Johnson", "Miller", "Davis", "Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Anderson"]
DEPARTMENTS = ["Engineering", "Sales", "Human Resources", "Finance", "Marketing", "Legal", "Customer Success", "IT Operations"]
DEVICE_TYPES = [
    ("MacBook Pro 16", "macOS Sonoma 14.4", "C02"),
    ("ThinkPad X1 Carbon", "Windows 11 Enterprise", "PF-"),
    ("Dell Latitude 7440", "Windows 11 Enterprise", "DELL-"),
    ("Ubuntu Workstation Pro", "Ubuntu 22.04 LTS", "SYS-"),
    ("HP EliteBook 840", "Windows 11 Enterprise", "HP-")
]

CATEGORIES = ["network", "hardware", "software", "access", "security"]
PRIORITIES = ["low", "medium", "high", "critical"]
STATUSES = ["open", "in_progress", "resolved", "closed", "escalated"]

TICKET_TEMPLATES = [
    ("GlobalProtect VPN Gateway Timeout", "Unable to connect to US-East corporate VPN node. Client hangs at 98% and throws authentication handshake error ERR_VPN_AUTH_401.", "network"),
    ("Wi-Fi WPA3 Enterprise Certificate Revoked", "Corporate Wi-Fi disconnected automatically. Device reports 'Certificate not trusted' with error ERR_8021X_CERT_EXPIRED when attempting 802.1X re-auth.", "network"),
    ("Password Reset Request for Okta SSO", "Locked out of Okta SSO after 5 failed login attempts following password expiration.", "access"),
    ("Docker Desktop OOM Container Crash", "PostgreSQL local development container killed unexpectedly due to out of memory allocation ERR_OOM_KILLED on workstation.", "software"),
    ("Outlook SAML Token Authentication Expiration", "Microsoft Outlook constantly prompts for password credentials with ERR_OUTLOOK_SAML login failure.", "software"),
    ("Blue Screen Kernel Panic Crash", "Windows workstation crashed unexpectedly throwing BSOD error code ERR_BSOD_KERNEL_PANIC after latest driver update.", "hardware"),
    ("Print Spooler Offline Error", "Network office printer fails to print documents with error ERR_PRINTER_SPOOL_OFFLINE.", "hardware"),
    ("SSH Key Authorization Denied", "Unable to push git code to internal repository due to public SSH key rejection.", "security"),
]

ERROR_TEMPLATES = [
    ("GlobalProtect-Service", "ERR_VPN_AUTH_401", "TLS connection failed: Remote server closed handshake unexpectedly during SSL negotiations.", "at VPNClient.Connect() line 142\nat NetworkGateway.EstablishTunnel() line 88"),
    ("WLAN-Agent", "ERR_8021X_CERT_EXPIRED", "Radius server rejected client authentication token. Certificate thumbprint mismatch.", "at RadiusAgent.VerifyCert() line 51"),
    ("Docker-Engine", "ERR_OOM_KILLED", "Process postgres (pid 4012) killed by kernel oom-killer: memory limit 2GB exceeded.", "Linux Kernel Memory Allocator: cgroup memory limit exceeded"),
    ("Outlook-SAML-Auth", "ERR_OUTLOOK_SAML", "SAML token validation failed. Identity provider timestamp skew > 300s.", "at SAMLValidator.VerifyToken() line 90"),
    ("Kernel-Diagnostics", "ERR_BSOD_KERNEL_PANIC", "CRITICAL_PROCESS_DIED in ntoskrnl.exe after IRQL_NOT_LESS_OR_EQUAL fault.", "Stack Dump: 0x0000007A ntoskrnl.exe+0x3f5c00"),
    ("Printer-Spooler", "ERR_PRINTER_SPOOL_OFFLINE", "RPC connection to print server printer.internal lost.", "at SpoolerClient.SendJob() line 204")
]


def seed_database():
    print("Initializing PostgreSQL database schema with pgvector...")
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # Check existing count
        existing_users = db.query(User).count()
        if existing_users >= 50:
            print(f"Database already contains {existing_users} users. Skipping seed.")
            return

        print("Seeding 55 Synthetic Users...")
        users = []
        for i in range(55):
            fname = random.choice(FIRST_NAMES)
            lname = random.choice(LAST_NAMES)
            email = f"{fname.lower()}.{lname.lower()}{i}@acme-corp.com"
            role = "admin" if i == 0 else ("technician" if i <= 5 else "user")
            dept = random.choice(DEPARTMENTS)
            user = User(email=email, full_name=f"{fname} {lname}", role=role, department=dept)
            users.append(user)

        db.add_all(users)
        db.commit()
        for u in users:
            db.refresh(u)

        technicians = [u for u in users if u.role in ["technician", "admin"]]

        print("Seeding 55 Synthetic Managed Hardware Devices...")
        devices = []
        for i, u in enumerate(users):
            dname, dos, dprefix = random.choice(DEVICE_TYPES)
            dev = Device(
                user_id=u.id,
                device_name=f"{u.full_name.split()[0]}-{dname}",
                serial_number=f"{dprefix}{random.randint(100000, 999999)}",
                os=dos,
                status="active" if i % 10 != 0 else "maintenance",
                ip_address=f"192.168.1.{10 + i}"
            )
            devices.append(dev)

        db.add_all(devices)
        db.commit()
        for d in devices:
            db.refresh(d)

        print("Seeding 110 Historical Support Tickets & Resolutions...")
        now = datetime.now(timezone.utc)
        tickets = []
        histories = []
        resolutions = []

        for i in range(110):
            tmpl_title, tmpl_desc, tmpl_cat = random.choice(TICKET_TEMPLATES)
            creator = random.choice(users)
            assigned_tech = random.choice(technicians)
            dev = random.choice(devices)
            
            prio = random.choice(PRIORITIES)
            status = "resolved" if i < 60 else random.choice(STATUSES)
            created_dt = now - timedelta(days=random.randint(1, 45), hours=random.randint(0, 23))

            t_num = f"TICK-{2000 + i + 1}"
            ticket = SupportTicket(
                ticket_number=t_num,
                title=f"{tmpl_title} #{i+1}",
                description=tmpl_desc,
                status=status,
                priority=prio,
                category=tmpl_cat,
                user_id=creator.id,
                assigned_to_id=assigned_tech.id,
                device_id=dev.id,
                created_at=created_dt,
                updated_at=created_dt + timedelta(hours=2)
            )
            tickets.append(ticket)

        db.add_all(tickets)
        db.commit()
        for t in tickets:
            db.refresh(t)

        for t in tickets:
            # Audit history entry
            h = TicketHistory(
                ticket_id=t.id,
                changed_by_id=t.user_id,
                field_changed="status",
                old_value=None,
                new_value="open",
                timestamp=t.created_at
            )
            histories.append(h)

            if t.status == "resolved":
                res = Resolution(
                    ticket_id=t.id,
                    solution_summary=f"Resolved issue by applying standard IT procedure for {t.category}.",
                    steps_taken="1. Diagnosed client log error code.\n2. Verified identity and credentials.\n3. Applied fix and verified service restored.",
                    resolved_by_id=t.assigned_to_id or technicians[0].id,
                    resolved_at=t.updated_at
                )
                resolutions.append(res)

        db.add_all(histories)
        db.add_all(resolutions)
        db.commit()

        print("Seeding 110 System Error Logs...")
        error_logs = []
        for i in range(110):
            svc, err_code, msg, stack = random.choice(ERROR_TEMPLATES)
            dev = random.choice(devices)
            linked_ticket = tickets[i] if i < len(tickets) else None
            log = ErrorLog(
                device_id=dev.id,
                ticket_id=linked_ticket.id if linked_ticket else None,
                service_name=svc,
                error_code=err_code,
                log_message=msg,
                stack_trace=stack,
                timestamp=now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            )
            error_logs.append(log)

        db.add_all(error_logs)
        db.commit()

        print("Seeding Incidents...")
        incidents = [
            Incident(
                title="US-East Corporate VPN Node Gateway Degradation",
                description="Primary VPN gateway node experiencing TLS handshake timeouts affecting remote users.",
                severity="P1",
                status="investigating",
                ticket_id=tickets[0].id,
                affected_service="Corporate VPN Network",
                started_at=now - timedelta(hours=6)
            ),
            Incident(
                title="Okta SAML SSO Authentication Latency Spike",
                description="Intermittent authentication latency spikes affecting Okta SSO logins.",
                severity="P2",
                status="identified",
                ticket_id=tickets[2].id,
                affected_service="SSO Authentication Service",
                started_at=now - timedelta(hours=14)
            )
        ]
        db.add_all(incidents)
        db.commit()

        print("Ingesting Sample RAG Documentation (PDF, TXT, MD)...")
        rag = RAGService(db)

        # Ingest TXT guide
        txt_path = os.path.join("sample_docs", "wifi_certificate_guide.txt")
        if os.path.exists(txt_path):
            with open(txt_path, "rb") as f:
                rag.ingest_file_bytes(
                    title="Enterprise Wi-Fi (802.1X) Certificate Fix",
                    category="Network",
                    file_bytes=f.read(),
                    filename="wifi_certificate_guide.txt",
                    source_url="https://wiki.acme-corp.internal/net/wifi-cert"
                )

        # Ingest MD guide
        md_path = os.path.join("sample_docs", "sso_okta_policy.md")
        if os.path.exists(md_path):
            with open(md_path, "rb") as f:
                rag.ingest_file_bytes(
                    title="Okta SSO & SAML Authentication Policy",
                    category="Access",
                    file_bytes=f.read(),
                    filename="sso_okta_policy.md",
                    source_url="https://wiki.acme-corp.internal/sec/okta-policy"
                )

        # Ingest PDF guide
        pdf_path = os.path.join("sample_docs", "vpn_troubleshooting_guide.pdf")
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                rag.ingest_file_bytes(
                    title="Corporate VPN Setup & Troubleshooting Guide (PDF)",
                    category="Network",
                    file_bytes=f.read(),
                    filename="vpn_troubleshooting_guide.pdf",
                    source_url="https://wiki.acme-corp.internal/net/vpn-pdf"
                )

        print("Database Seed Successfully Populated!")

    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
