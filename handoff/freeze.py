from collections import Counter
from hashlib import sha256
import json
import sqlite3

from handoff.catalog import StationCatalog
from handoff.evidence import BoardContribution, EvidenceSource, StationEvidence
from scoring.snapshots import read_station_snapshot


def _package_id(source: EvidenceSource) -> str:
    identity = json.dumps([source.origin, source.station, source.revision], separators=(',', ':'))
    return 'station-' + sha256(identity.encode('utf-8')).hexdigest()


def freeze_station(
    source_db: sqlite3.Connection, archive_db: sqlite3.Connection, station: str, revision: int
) -> StationEvidence:
    snapshot = read_station_snapshot(source_db, station, revision)
    tallies = {}
    for version in snapshot.occurrences:
        pair = version.pair
        key = pair.ticket, pair.label
        if key not in tallies:
            tallies[key] = Counter(), Counter()
        left, right = tallies[key]
        left[pair.scores[0]] += 1
        right[pair.scores[1]] += 1

    contributions = tuple(
        BoardContribution(ticket, label, (tuple(left.items()), tuple(right.items())))
        for (ticket, label), (left, right) in tallies.items()
    )
    source = EvidenceSource(snapshot.origin, snapshot.station, str(snapshot.revision))
    evidence = StationEvidence(_package_id(source), source, snapshot.models, contributions)
    return StationCatalog(archive_db).save(evidence)
