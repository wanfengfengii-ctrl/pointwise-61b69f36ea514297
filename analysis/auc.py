from collections.abc import Mapping
from fractions import Fraction

from storage import InsufficientEvidence


def auc(positive: Mapping[Fraction, int], negative: Mapping[Fraction, int]) -> Fraction:
    """Evaluate a single model over two validated histograms of record counts."""
    pairs = sum(positive.values()) * sum(negative.values())
    if pairs == 0:
        raise InsufficientEvidence('AUC requires both positive and negative measurements')
    doubled_wins = 0
    for positive_score, positive_count in positive.items():
        for negative_score, negative_count in negative.items():
            multiplicity = positive_count * negative_count
            if positive_score > negative_score:
                doubled_wins += 2 * multiplicity
            elif positive_score == negative_score:
                doubled_wins += multiplicity
    return Fraction(doubled_wins, 2 * pairs)
