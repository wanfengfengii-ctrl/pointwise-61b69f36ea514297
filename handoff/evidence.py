from dataclasses import dataclass
from fractions import Fraction

from boards.labels import Label
from scoring.pairs import ModelPair
from storage import InvalidEvidence, InvalidInput, identifier


ScoreCounts = tuple[tuple[Fraction, int], ...]


@dataclass(frozen=True)
class EvidenceSource:
    origin: str
    station: str
    revision: str


@dataclass(frozen=True)
class BoardContribution:
    ticket: str
    label: Label
    columns: tuple[ScoreCounts, ScoreCounts]


@dataclass(frozen=True)
class StationEvidence:
    package_id: str
    source: EvidenceSource
    models: ModelPair
    contributions: tuple[BoardContribution, ...]


def _validate_column(column: ScoreCounts) -> tuple[ScoreCounts, int]:
    if not isinstance(column, tuple) or not column:
        raise InvalidEvidence('a score column must contain at least one score tally')
    scores = set()
    total = 0
    for tally in column:
        if not isinstance(tally, tuple) or len(tally) != 2:
            raise InvalidEvidence('each score tally needs a score and a count')
        score, count = tally
        if not isinstance(score, Fraction) or type(count) is not int or count <= 0:
            raise InvalidEvidence('a score tally needs an exact score and a positive integer count')
        if score in scores:
            raise InvalidEvidence('a score appears more than once in a column')
        scores.add(score)
        total += count
    return tuple(sorted(column)), total


def _normalize_contribution(bucket: BoardContribution) -> BoardContribution:
    if not isinstance(bucket, BoardContribution):
        raise InvalidEvidence('invalid board contribution')
    identifier(bucket.ticket, 'ticket number')
    if not isinstance(bucket.label, Label):
        raise InvalidEvidence('invalid contribution label')
    if not isinstance(bucket.columns, tuple) or len(bucket.columns) != 2:
        raise InvalidEvidence('each board and label needs two model columns')
    left, left_count = _validate_column(bucket.columns[0])
    right, right_count = _validate_column(bucket.columns[1])
    if left_count != right_count:
        raise InvalidEvidence('the two columns count different numbers of measurements')
    return BoardContribution(bucket.ticket, bucket.label, (left, right))


def validate_evidence(evidence: StationEvidence) -> StationEvidence:
    if not isinstance(evidence, StationEvidence) or not isinstance(evidence.source, EvidenceSource):
        raise InvalidEvidence('a station package with a source is required')
    if not isinstance(evidence.models, ModelPair):
        raise InvalidEvidence('a named model pair is required')
    if not isinstance(evidence.contributions, tuple) or not evidence.contributions:
        raise InvalidEvidence('station evidence is missing board contributions')
    try:
        identifier(evidence.package_id, 'package id')
        identifier(evidence.source.origin, 'source origin')
        identifier(evidence.source.station, 'station')
        identifier(evidence.source.revision, 'source revision')
        contributions = {}
        for bucket in evidence.contributions:
            normalized = _normalize_contribution(bucket)
            key = normalized.ticket, normalized.label.value
            if key in contributions:
                raise InvalidEvidence('a board and label appears more than once')
            contributions[key] = normalized
    except InvalidInput as exc:
        raise InvalidEvidence(str(exc)) from exc
    return StationEvidence(evidence.package_id, evidence.source, evidence.models,
                           tuple(contributions[key] for key in sorted(contributions)))
