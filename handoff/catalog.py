from dataclasses import replace
import sqlite3

from handoff.evidence import StationEvidence, validate_evidence
from handoff.package import decode_evidence, encode_evidence
from storage import InvalidEvidence, MissingItem, identifier, write_transaction


def initialize_handoff(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS station_packages (
            package_id TEXT PRIMARY KEY NOT NULL,
            origin TEXT NOT NULL,
            station TEXT NOT NULL,
            revision TEXT NOT NULL,
            payload TEXT NOT NULL,
            UNIQUE (origin, station, revision)
        )
    ''')


class StationCatalog:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def save(self, evidence: StationEvidence) -> StationEvidence:
        evidence = validate_evidence(evidence)
        source = evidence.source
        with write_transaction(self.db):
            row = self.db.execute(
                'SELECT payload FROM station_packages WHERE package_id = ?', (evidence.package_id,)
            ).fetchone()
            if row is not None:
                existing = decode_evidence(row[0])
                if existing != evidence:
                    raise InvalidEvidence('the package id already refers to different evidence')
                return existing
            row = self.db.execute('''
                SELECT payload FROM station_packages WHERE origin = ? AND station = ? AND revision = ?
            ''', (source.origin, source.station, source.revision)).fetchone()
            if row is not None:
                existing = decode_evidence(row[0])
                if replace(evidence, package_id=existing.package_id) != existing:
                    raise InvalidEvidence('the source revision already has different evidence')
                return existing
            self.db.execute('''
                INSERT INTO station_packages(package_id, origin, station, revision, payload)
                VALUES (?, ?, ?, ?, ?)
            ''', (evidence.package_id, source.origin, source.station, source.revision, encode_evidence(evidence)))
        return evidence

    def read(self, package_id: str) -> StationEvidence:
        identifier(package_id, 'package id')
        row = self.db.execute(
            'SELECT payload FROM station_packages WHERE package_id = ?', (package_id,)
        ).fetchone()
        if row is None:
            raise MissingItem(f'no such station package {package_id!r}')
        return decode_evidence(row[0])
