from dataclasses import dataclass
import sqlite3

from scoring.ledger import ScoreLedger, ScoreRevision
from scoring.pairs import ModelPair
from storage import MissingItem, identifier, require_sqlite_id


@dataclass(frozen=True)
class StationSnapshot:
    origin: str
    station: str
    revision: int
    models: ModelPair
    occurrences: tuple[ScoreRevision, ...]


def read_station_snapshot(db: sqlite3.Connection, station: str, revision: int) -> StationSnapshot:
    identifier(station, 'station')
    require_sqlite_id(revision, 'score revision')
    ledger = ScoreLedger(db)
    boundary = ledger.read_station_revision(station, revision)
    if boundary is None:
        raise MissingItem(f'no score revision {revision} for station {station!r}')
    latest = {}
    for version in ledger.read_versions_through(station, revision):
        latest[version.pair.occurrence] = version
    occurrences = tuple(latest[number] for number in sorted(latest))
    return StationSnapshot(ledger.source_origin(), station, revision, boundary.pair.models, occurrences)
