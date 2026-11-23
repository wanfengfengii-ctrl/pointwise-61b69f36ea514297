from dataclasses import dataclass

from scoring.ledger import ScoreLedger, ScoreRevision
from scoring.pairs import ScorePair
from storage import Conflict, InvalidInput, MissingItem, identifier


@dataclass(frozen=True)
class Correction:
    code: str


def apply_correction(
    ledger: ScoreLedger,
    original: ScoreRevision | None,
    pair: ScorePair,
    correction: Correction,
) -> ScoreRevision:
    if not isinstance(correction, Correction):
        raise InvalidInput('a named Correction is required')
    identifier(correction.code, 'correction code')
    existing = ledger.read_correction(pair.station, correction.code)
    if existing is not None:
        if existing.pair != pair:
            raise Conflict('correction code was already used for different content')
        return existing
    if original is None:
        raise MissingItem('a correction requires an accepted occurrence')
    if original.pair.ticket != pair.ticket or original.pair.models != pair.models:
        raise Conflict('a correction must preserve the ticket and ordered model pair')
    return ledger.append_revision(pair, correction.code)
