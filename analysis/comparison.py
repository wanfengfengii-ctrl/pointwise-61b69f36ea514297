from collections.abc import Iterable
import sqlite3

from analysis.auc import auc
from analysis.jackknife import evaluate_board_deletions
from analysis.pool import build_pool, score_distributions
from analysis.selection import select_evidence
from handoff.catalog import StationCatalog
from records.provenance import ReportSource
from records.publication import publish_report
from records.retrieval import ReportDelivery


def issue_comparison(db: sqlite3.Connection, package_ids: Iterable[str]) -> ReportDelivery:
    selected = select_evidence(StationCatalog(db), package_ids)
    pool = build_pool(selected)
    left, right = score_distributions(bucket for _, bucket in pool.contributions)
    full_auc = auc(*left), auc(*right)
    paired = evaluate_board_deletions(pool)
    sources = tuple(
        ReportSource(package.package_id, package.source.station, package.source.origin, package.source.revision)
        for package in selected.packages
    )
    report, receipt = publish_report(db, pool.models, full_auc, paired, sources)
    return ReportDelivery(report, sources, receipt)
