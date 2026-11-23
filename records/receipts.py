from dataclasses import dataclass
import sqlite3

from storage import MissingItem


@dataclass(frozen=True)
class ReportReceipt:
    report_id: int
    receipt_id: str


def initialize_receipts(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS report_receipts (
            report_id INTEGER PRIMARY KEY REFERENCES reports(report_id),
            receipt_id TEXT NOT NULL UNIQUE
        )
    ''')


def save_receipt(db: sqlite3.Connection, report_id: int) -> ReportReceipt:
    receipt = ReportReceipt(report_id, f'receipt-{report_id}')
    db.execute('INSERT INTO report_receipts(report_id, receipt_id) VALUES (?, ?)',
               (receipt.report_id, receipt.receipt_id))
    return receipt


def read_receipt(db: sqlite3.Connection, report_id: int) -> ReportReceipt:
    row = db.execute('SELECT receipt_id FROM report_receipts WHERE report_id = ?', (report_id,)).fetchone()
    if row is None:
        raise MissingItem(f'no receipt for report {report_id}')
    return ReportReceipt(report_id, row[0])
