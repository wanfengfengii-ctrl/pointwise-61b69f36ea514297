import sqlite3

from handoff.catalog import StationCatalog
from handoff.evidence import EvidenceSource, StationEvidence
from handoff.package import decode_evidence
from storage import InvalidEvidence


def accept_station(db: sqlite3.Connection, payload: str, declared_source: EvidenceSource) -> StationEvidence:
    evidence = decode_evidence(payload)
    if not isinstance(declared_source, EvidenceSource) or evidence.source != declared_source:
        raise InvalidEvidence('the declared source does not match the station package')
    return StationCatalog(db).save(evidence)
