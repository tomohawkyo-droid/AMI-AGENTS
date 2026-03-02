#!/usr/bin/env python3
"""
AMI Mail CLI - Enterprise Mail Operations
Supports SMTP sending (via local relay) and IMAP fetching.
"""

import argparse
import email
import imaplib
import mimetypes
import os
import smtplib
import sys
import time
from email.header import decode_header
from email.message import EmailMessage

# Default Local Relay Config (From env or alternative)

DEFAULT_SMTP_HOST = os.getenv("AMI_SMTP_HOST", "127.0.0.1")

DEFAULT_SMTP_PORT = int(
    os.getenv("AMI_SMTP_PORT", "2525")
)  # Default to 2525 (Mailpit/Dev)

DEFAULT_FROM = os.getenv("AMI_MAIL_FROM", "ami-cli@localhost")


def setup_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AMI Enterprise Mail CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # --- SEND Command ---
    send_parser = subparsers.add_parser("send", help="Send email via SMTP")
    _add_send_arguments(send_parser)

    # --- SEND-BLOCK Command ---
    block_parser = subparsers.add_parser(
        "send-block", help="Send email and block until reply is received"
    )
    _add_send_arguments(block_parser)
    block_parser.add_argument(
        "--imap-host",
        required=True,
        help="IMAP Host for polling (e.g., imap.gmail.com)",
    )
    block_parser.add_argument("--imap-user", required=True, help="IMAP Username")
    block_parser.add_argument("--imap-password", required=True, help="IMAP Password")
    block_parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Wait timeout in seconds (default: 300)",
    )
    block_parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Polling interval in seconds (default: 10)",
    )

    # --- FETCH Command ---
    fetch_parser = subparsers.add_parser("fetch", help="Fetch email via IMAP")
    fetch_parser.add_argument(
        "--host", required=True, help="IMAP Host (e.g., imap.gmail.com)"
    )
    fetch_parser.add_argument("--user", "-u", required=True, help="IMAP Username")
    fetch_parser.add_argument(
        "--password", "-p", required=True, help="IMAP Password (or App Password)"
    )
    fetch_parser.add_argument(
        "--folder", default="INBOX", help="Folder to search (default: INBOX)"
    )
    fetch_parser.add_argument(
        "--limit", type=int, default=5, help="Number of recent emails to fetch"
    )
    fetch_parser.add_argument(
        "--ssl", action="store_true", default=True, help="Use SSL (default: True)"
    )

    return parser


def _add_send_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("recipient", help="Recipient email address")
    parser.add_argument("--subject", "-s", required=True, help="Email subject")
    parser.add_argument("--body", "-b", required=True, help="Email body (text)")
    parser.add_argument("--html", action="store_true", help="Send as HTML")
    parser.add_argument(
        "--attachment",
        "-a",
        action="append",
        help="Path to file attachment (can be used multiple times)",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_SMTP_HOST,
        help=f"SMTP Host (default: {DEFAULT_SMTP_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SMTP_PORT,
        help=f"SMTP Port (default: {DEFAULT_SMTP_PORT})",
    )
    parser.add_argument(
        "--sender", default=DEFAULT_FROM, help=f"From address (default: {DEFAULT_FROM})"
    )


def send_email_core(args: argparse.Namespace) -> None:
    """Core logic for sending email."""
    print(f"[*] Connecting to SMTP Relay at {args.host}:{args.port}...")
    msg = EmailMessage()
    msg["Subject"] = args.subject
    msg["From"] = args.sender
    msg["To"] = args.recipient

    if args.html:
        msg.add_alternative(args.body, subtype="html")
    else:
        msg.set_content(args.body)

    # Handle attachments
    if args.attachment:
        for filepath in args.attachment:
            if not os.path.exists(filepath):
                print(f"[-] Error: Attachment not found: {filepath}", file=sys.stderr)
                sys.exit(1)

            ctype, encoding = mimetypes.guess_type(filepath)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"

            maintype, subtype = ctype.split("/", 1)

            try:
                with open(filepath, "rb") as f:
                    file_data = f.read()
                    msg.add_attachment(
                        file_data,
                        maintype=maintype,
                        subtype=subtype,
                        filename=os.path.basename(filepath),
                    )
                print(f"[*] Attached: {filepath}")
            except Exception as e:
                print(f"[-] Error attaching {filepath}: {e}", file=sys.stderr)
                sys.exit(1)

    try:
        with smtplib.SMTP(args.host, args.port) as server:
            server.send_message(msg)
        print(f"[+] Email successfully sent to {args.recipient}")
    except Exception as e:
        print(f"[-] SMTP Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_send(args: argparse.Namespace) -> None:
    send_email_core(args)
    print("[*] Reminder: Run 'ami-mail fetch' manually if automation isn't set up.")


def _decode_payload(payload: object) -> str:
    """Decode an email payload to string."""
    if isinstance(payload, bytes):
        return payload.decode()
    if isinstance(payload, str):
        return payload
    return "(Could not decode payload)"


def extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get("Content-Disposition"))
            if ctype == "text/plain" and "attachment" not in cdispo:
                return _decode_payload(part.get_payload(decode=True))
        return "(No text body found)"
    return _decode_payload(msg.get_payload(decode=True))


def cmd_send_block(args: argparse.Namespace) -> None:
    # 1. Send the email
    send_email_core(args)

    print(f"[*] Blocking: Waiting for reply from {args.recipient} ({args.timeout}s)...")
    start_time = time.time()

    while (time.time() - start_time) < args.timeout:
        try:
            # Poll IMAP
            mail = imaplib.IMAP4_SSL(args.imap_host)
            mail.login(args.imap_user, args.imap_password)
            mail.select("INBOX")

            # Search for UNSEEN messages from recipient
            # We also check recent messages generally in case 'UNSEEN' flag was cleared
            status, messages = mail.search(None, f'(FROM "{args.recipient}")')

            if status == "OK":
                mail_ids = messages[0].split()
                if mail_ids:
                    # Check the latest email from this person
                    latest_id = mail_ids[-1]
                    _, msg_data = mail.fetch(latest_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding or "utf-8")

                            # Simple matching: Check if reply subject contains original
                            # subject or just accept it if it's new enough?
                            # Let's check date? Parsing date is annoying. Let's rely
                            # on Subject or assume the latest from them is the reply?
                            # Stricter: Check if Subject contains original (ignore Re:)
                            clean_reply_subj = (
                                subject.lower().replace("re:", "").strip()
                            )
                            clean_orig_subj = args.subject.lower().strip()

                            if clean_orig_subj in clean_reply_subj:
                                print("\n[+] Reply Received!")
                                print(f"From: {msg.get('From')}")
                                print(f"Subject: {subject}")
                                print("-" * 40)
                                body = extract_body(msg)
                                print(body)
                                print("-" * 40)
                                mail.close()
                                mail.logout()
                                return

            mail.close()
            mail.logout()

        except Exception as e:
            print(f"[!] Polling Error: {e}", file=sys.stderr)

        time.sleep(args.poll_interval)
        print(".", end="", flush=True)

    print("\n[-] Timeout reached. No reply received.")
    sys.exit(1)


def cmd_fetch(args: argparse.Namespace) -> None:
    print(f"[*] Connecting to IMAP Server {args.host}...")
    try:
        mail = imaplib.IMAP4_SSL(args.host) if args.ssl else imaplib.IMAP4(args.host)

        mail.login(args.user, args.password)
        mail.select(args.folder)

        # Search for all emails
        status, messages = mail.search(None, "ALL")
        if status != "OK":
            print("[-] No messages found or error searching.")
            return

        mail_ids = messages[0].split()
        total = len(mail_ids)
        print(f"[+] Found {total} messages in {args.folder}. Fetching {args.limit}...")

        # Fetch last N messages
        start = max(0, total - args.limit)

        for i in range(total - 1, start - 1, -1):
            email_id = mail_ids[i]
            _, msg_data = mail.fetch(email_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8")
                    from_ = msg.get("From")
                    print(f"  [{i + 1}] From: {from_} | Subject: {subject}")

        mail.close()
        mail.logout()
        print("[*] Done.")

    except Exception as e:
        print(f"[-] IMAP Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = setup_argparse()
    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args)
    elif args.command == "send-block":
        cmd_send_block(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
