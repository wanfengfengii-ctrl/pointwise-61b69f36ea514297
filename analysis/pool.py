from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from analysis.selection import SelectedEvidence
from boards.labels import Label
from handoff.evidence import BoardContribution
from scoring.pairs import ModelPair


ModelDistribution = tuple[Counter[Fraction], Counter[Fraction]]


@dataclass(frozen=True)
class ComparisonPool:
    models: ModelPair
    contributions: tuple[tuple[str, BoardContribution], ...]
    tickets: tuple[str, ...]


def build_pool(selection: SelectedEvidence) -> ComparisonPool:
    contributions = tuple(
        (package.source.station, bucket)
        for package in selection.packages
        for bucket in package.contributions
    )
    tickets = tuple(sorted({bucket.ticket for _, bucket in contributions}))
    return ComparisonPool(selection.models, contributions, tickets)


def score_distributions(contributions: Iterable[BoardContribution]) -> tuple[ModelDistribution, ModelDistribution]:
    distributions = (Counter(), Counter()), (Counter(), Counter())
    for bucket in contributions:
        label_index = 0 if bucket.label == Label.POSITIVE else 1
        for column, counts in zip(bucket.columns, distributions, strict=True):
            histogram = counts[label_index]
            for score, count in column:
                histogram[score] += count
    return distributions
