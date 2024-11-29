import argparse
from dataclasses import dataclass
import email
import imaplib
import json
import logging
from datetime import datetime
from email.header import decode_header
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="imap.gmail.com:993")
    parser.add_argument("--username", type=str)
    parser.add_argument("--password", type=str)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.json and args.json.exists():
        logging.info(f"Loading offers from {args.json}")
        with args.json.open("r") as f:
            offers = [
                Offer(timestamp=datetime.fromisoformat(o["timestamp"]), subject=o["subject"])
                for o in json.load(f)
            ]
    else:
        hostname, _, port = args.host.partition(":")
        with imaplib.IMAP4_SSL(hostname, int(port or 993)) as imap:
            imap.login(args.username, args.password)
            offers = collect(imap)
        if args.json:
            with args.json.open("w") as f:
                json.dump(
                    [
                        {"timestamp": o.timestamp.isoformat(), "subject": o.subject}
                        for o in offers
                    ],
                    f,
                    indent=2,
                    ensure_ascii=False,
                )


def collect(imap: imaplib.IMAP4) -> list["Offer"]:
    emails = []

    imap.select("INBOX")
    _, data = imap.search(None, "FROM", "offers@travel.wizznews.com")
    search_results = data[0].split()
    logging.info(f"Found {len(search_results)} emails, fetching")
    for msgnum in search_results:
        _, data = imap.fetch(msgnum, "(RFC822.HEADER)")
        message = email.message_from_bytes(data[0][1])

        subject, encoding = decode_header(message.get("Subject"))[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or "utf-8")

        timestamp = datetime.strptime(message.get("Date"), "%a, %d %b %Y %H:%M:%S %z")

        emails.append(Offer(timestamp=timestamp, subject=subject))

    return emails


@dataclass
class Offer:
    timestamp: datetime
    subject: str


if __name__ == "__main__":
    main()
