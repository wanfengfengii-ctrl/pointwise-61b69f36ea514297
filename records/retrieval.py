from dataclasses import dataclass
import sqlite3

from records.export import export_report
from records.provenance import ReportSource, read_sources
from records.publication import PublishedReport, read_report_snapshot
from records.receipts import ReportReceipt, read_receipt


@dataclass(frozen=True)
class ReportDelivery:
    report: PublishedReport
    sources: tuple[ReportSource, ...]
    receipt: ReportReceipt


def read_report(db: sqlite3.Connection, report_id: int, *, as_json: bool = False) -> ReportDelivery | str:
    report = read_report_snapshot(db, report_id)
    sources = read_sources(db, report_id)
    receipt = read_receipt(db, report_id)
    if as_json:
        return export_report(report, sources, receipt)
    return ReportDelivery(report, sources, receipt)
