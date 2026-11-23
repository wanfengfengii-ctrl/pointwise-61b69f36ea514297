from dataclasses import dataclass
from fractions import Fraction
import json
import sqlite3

from analysis.jackknife import BoardDeletion, PairedDeletionResult
from records.provenance import ReportSource, initialize_provenance, save_sources
from records.receipts import ReportReceipt, initialize_receipts, save_receipt
from scoring.pairs import ModelPair
from storage import MissingItem, PublicationFailed, require_sqlite_id, write_transaction


@dataclass(frozen=True)
class PublishedReport:
    report_id: int
    models: ModelPair
    auc: tuple[Fraction, Fraction]
    deletions: tuple[BoardDeletion, ...]
    covariance: Fraction


def initialize_records(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY,
            payload TEXT NOT NULL
        )
    ''')
    initialize_provenance(db)
    initialize_receipts(db)


def _encode_snapshot(models: ModelPair, full_auc: tuple[Fraction, Fraction], paired: PairedDeletionResult) -> str:
    return json.dumps({
        'models': models.names,
        'auc': [str(value) for value in full_auc],
        'deletions': [[row.ticket, str(row.auc[0]), str(row.auc[1])] for row in paired.deletions],
        'covariance': str(paired.covariance),
    }, ensure_ascii=False, separators=(',', ':'))


def publish_report(
    db: sqlite3.Connection,
    models: ModelPair,
    full_auc: tuple[Fraction, Fraction],
    paired: PairedDeletionResult,
    sources: tuple[ReportSource, ...],
) -> tuple[PublishedReport, ReportReceipt]:
    payload = _encode_snapshot(models, full_auc, paired)
    try:
        with write_transaction(db):
            cursor = db.execute('INSERT INTO reports(payload) VALUES (?)', (payload,))
            report_id = cursor.lastrowid
            save_sources(db, report_id, sources)
            receipt = save_receipt(db, report_id)
    except sqlite3.Error as exc:
        raise PublicationFailed('could not commit the comparison report') from exc
    return PublishedReport(report_id, models, full_auc, paired.deletions, paired.covariance), receipt


def read_report_snapshot(db: sqlite3.Connection, report_id: int) -> PublishedReport:
    require_sqlite_id(report_id, 'report id')
    row = db.execute('SELECT payload FROM reports WHERE report_id = ?', (report_id,)).fetchone()
    if row is None:
        raise MissingItem(f'no such report {report_id}')
    payload = json.loads(row[0])
    left, right = payload['auc']
    deletions = tuple(BoardDeletion(ticket, (Fraction(first), Fraction(second)))
                      for ticket, first, second in payload['deletions'])
    return PublishedReport(report_id, ModelPair(*payload['models']), (Fraction(left), Fraction(right)),
                           deletions, Fraction(payload['covariance']))
