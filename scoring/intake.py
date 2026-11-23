from collections.abc import Mapping
import sqlite3

from boards.labels import Label
from boards.stations import require_admission
from scoring.ledger import ScoreLedger, ScoreRevision
from scoring.pairs import ModelPair, ScoreInput, normalize_pair
from scoring.revisions import Correction, apply_correction
from storage import Conflict, write_transaction


def record_pair(
    db: sqlite3.Connection,
    station: str,
    ticket: str,
    occurrence: str,
    label: str | Label,
    models: ModelPair,
    scores: Mapping[str, ScoreInput],
    *,
    correction: Correction | None = None,
) -> ScoreRevision:
    pair = normalize_pair(station, ticket, occurrence, label, models, scores)
    ledger = ScoreLedger(db)
    with write_transaction(db):
        require_admission(db, pair.station, pair.ticket)
        original = ledger.read_occurrence(pair.station, pair.occurrence)
        if correction is not None:
            return apply_correction(ledger, original, pair, correction)
        if original is None:
            return ledger.append_revision(pair)
        if original.pair != pair:
            raise Conflict('occurrence content differs from the original acceptance')
        return original
