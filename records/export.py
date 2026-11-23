from dataclasses import asdict
from fractions import Fraction
import json

from records.provenance import ReportSource
from records.publication import PublishedReport
from records.receipts import ReportReceipt


def format_fraction(value: Fraction) -> dict[str, int]:
    return {'numerator': value.numerator, 'denominator': value.denominator}


def export_report(report: PublishedReport, sources: tuple[ReportSource, ...], receipt: ReportReceipt) -> str:
    payload = {
        'report_id': report.report_id,
        'models': report.models.names,
        'auc': [format_fraction(value) for value in report.auc],
        'deletions': [
            {'ticket': row.ticket, 'auc': [format_fraction(value) for value in row.auc]}
            for row in report.deletions
        ],
        'covariance': format_fraction(report.covariance),
        'sources': [asdict(source) for source in sources],
        'receipt': asdict(receipt),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
