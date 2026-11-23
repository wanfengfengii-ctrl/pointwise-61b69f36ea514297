from dataclasses import dataclass
from fractions import Fraction

from analysis.auc import auc
from analysis.pool import ComparisonPool, score_distributions
from storage import InsufficientEvidence


@dataclass(frozen=True)
class BoardDeletion:
    ticket: str
    auc: tuple[Fraction, Fraction]


@dataclass(frozen=True)
class PairedDeletionResult:
    deletions: tuple[BoardDeletion, ...]
    covariance: Fraction


def evaluate_board_deletions(pool: ComparisonPool) -> PairedDeletionResult:
    deletions = []
    for ticket in pool.tickets:
        remaining = (bucket for _, bucket in pool.contributions if bucket.ticket != ticket)
        left, right = score_distributions(remaining)
        if not left[0] or not left[1]:
            # Each retained board and label has the same count in both columns.
            continue
        deletions.append(BoardDeletion(ticket, (auc(*left), auc(*right))))

    count = len(deletions)
    if count < 2:
        raise InsufficientEvidence('comparison requires at least two valid board deletions')
    left_mean = sum(row.auc[0] for row in deletions) / count
    right_mean = sum(row.auc[1] for row in deletions) / count
    cross_products = sum(
        (row.auc[0] - left_mean) * (row.auc[1] - right_mean) for row in deletions
    )
    return PairedDeletionResult(tuple(deletions), Fraction(count - 1, count) * cross_products)
