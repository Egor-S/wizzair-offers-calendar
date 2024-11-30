import argparse
import email
import imaplib
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.header import decode_header
from pathlib import Path



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="imap.gmail.com:993")
    parser.add_argument("--username", type=str, required=True)
    parser.add_argument("--password", type=str, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    hostname, _, port = args.host.partition(":")
    with imaplib.IMAP4_SSL(hostname, int(port or 993)) as imap:
        imap.login(args.username, args.password)
        offers = collect(imap, args.cache)

    with args.output.open("w") as f:
        render(offers, f)


def collect(imap: imaplib.IMAP4, cache_dir: Path | None) -> list["Offer"]:
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
    offers = []

    imap.select("INBOX")
    _, data = imap.search(None, "FROM", "offers@travel.wizznews.com")
    search_results = data[0].split()
    logging.info(f"Found {len(search_results)} emails, fetching")
    for msgnum in search_results:
        path = None if cache_dir is None else cache_dir / f"{msgnum.decode()}.eml"

        if path and path.exists():
            with path.open("rb") as f:
                message = email.message_from_bytes(f.read())
        else:
            _, data = imap.fetch(msgnum, "(RFC822)")
            message = email.message_from_bytes(data[0][1])
            if path:
                with path.open("wb") as f:
                    f.write(data[0][1])

        subject, encoding = decode_header(message.get("Subject"))[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or "utf-8")
        logging.info("Subject: %s", subject)
        timestamp = datetime.strptime(message.get("Date"), "%a, %d %b %Y %H:%M:%S %z")
        offers.append(Offer(timestamp=timestamp, subject=subject))

    return offers


def render(offers: list["Offer"], f):
    current_date = offers[0].timestamp.date()
    current_date -= timedelta(days=current_date.weekday())  # move to the Monday before the first offer
    end_date = offers[-1].timestamp.date()
    end_date += timedelta(days=7 - end_date.weekday())  # move to the Monday after the last offer

    oid = 0
    rows = []
    while current_date < end_date:
        row: list[DateCell] = []
        for _ in range(7):
            current_date += timedelta(days=1)
            cell = DateCell(current_date, [])
            while oid < len(offers) and offers[oid].timestamp.date() == current_date:
                cell.subjects.append(offers[oid].subject)
                oid += 1
            row.append(cell)
        months = Counter(cell.date.strftime("%Y %B") for cell in row)
        rows.append("<tr><td>{}</td>{}</tr>".format(
            months.most_common(1)[0][0],
            "".join(str(cell) for cell in row)
        ))

    print("<table><thead>", file=f)
    print("<tr><th>Month</th>%s</tr>" % "".join(f"<th>{d}</th>" for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]), file=f)
    print("</thead><tbody>", file=f)
    for row in rows:
        print(row, file=f)
    print("</tbody></table>", file=f)


@dataclass
class Offer:
    timestamp: datetime
    subject: str


@dataclass
class DateCell:
    date: date
    subjects: list[str]

    def __str__(self) -> str:
        if not self.subjects:
            return f"<td>{self.date.day}</td>"
        subjects = "; ".join(self.subjects)
        return f'<td title="{subjects}">{self.date.day} 🏷️</td>'


if __name__ == "__main__":
    main()
