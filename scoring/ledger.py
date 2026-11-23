from dataclasses import dataclass
from fractions import Fraction
import sqlite3
from uuid import uuid4

from boards.labels import Label
from scoring.pairs import ModelPair, ScorePair
from storage import Conflict, identifier


@dataclass(frozen=True)
class ScoreRevision:
    revision: int
    pair: ScorePair
    correction_code: str | None


def initialize_scoring(db: sqlite3.Connection, *, origin: str | None = None) -> None:
    if origin is not None:
        identifier(origin, 'source origin')
    db.execute('''
        CREATE TABLE IF NOT EXISTS score_origin (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            origin TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS station_model_pairs (
            station TEXT PRIMARY KEY NOT NULL,
            first_model TEXT NOT NULL,
            second_model TEXT NOT NULL,
            CHECK (first_model <> second_model)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS score_occurrences (
            station TEXT NOT NULL REFERENCES station_model_pairs(station),
            occurrence TEXT NOT NULL,
            ticket TEXT NOT NULL,
            PRIMARY KEY (station, occurrence),
            FOREIGN KEY (ticket, station) REFERENCES station_admissions(ticket, station)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS score_versions (
            revision INTEGER PRIMARY KEY,
            station TEXT NOT NULL,
            occurrence TEXT NOT NULL,
            label TEXT NOT NULL CHECK (label IN ('positive', 'negative')),
            first_score TEXT NOT NULL,
            second_score TEXT NOT NULL,
            correction_code TEXT,
            UNIQUE (station, correction_code),
            FOREIGN KEY (station, occurrence) REFERENCES score_occurrences(station, occurrence)
        )
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS score_versions_by_occurrence
        ON score_versions(station, occurrence, revision)
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS score_versions_by_station
        ON score_versions(station, revision)
    ''')
    row = db.execute('SELECT origin FROM score_origin WHERE singleton = 1').fetchone()
    if row is None:
        db.execute('INSERT INTO score_origin(singleton, origin) VALUES (1, ?)', (origin or uuid4().hex,))
    elif origin is not None and row[0] != origin:
        raise Conflict('the source database already has a different origin')


_VERSION_QUERY = '''
    SELECT v.revision, v.station, o.ticket, v.occurrence, v.label,
           m.first_model, m.second_model, v.first_score, v.second_score, v.correction_code
    FROM score_versions AS v
    JOIN score_occurrences AS o ON o.station = v.station AND o.occurrence = v.occurrence
    JOIN station_model_pairs AS m ON m.station = v.station
'''


def _read_version(row: tuple) -> ScoreRevision:
    revision, station, ticket, occurrence, label, first, second, left, right, correction = row
    pair = ScorePair(station, ticket, occurrence, Label(label), ModelPair(first, second),
                     (Fraction(left), Fraction(right)))
    return ScoreRevision(revision, pair, correction)


class ScoreLedger:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def source_origin(self) -> str:
        return self.db.execute('SELECT origin FROM score_origin WHERE singleton = 1').fetchone()[0]

    def read_occurrence(self, station: str, occurrence: str) -> ScoreRevision | None:
        row = self.db.execute(
            _VERSION_QUERY + ' WHERE v.station = ? AND v.occurrence = ? ORDER BY v.revision LIMIT 1',
            (station, occurrence),
        ).fetchone()
        return _read_version(row) if row is not None else None

    def read_correction(self, station: str, code: str) -> ScoreRevision | None:
        row = self.db.execute(
            _VERSION_QUERY + ' WHERE v.station = ? AND v.correction_code = ?', (station, code)
        ).fetchone()
        return _read_version(row) if row is not None else None

    def read_station_revision(self, station: str, revision: int) -> ScoreRevision | None:
        row = self.db.execute(
            _VERSION_QUERY + ' WHERE v.station = ? AND v.revision = ?', (station, revision)
        ).fetchone()
        return _read_version(row) if row is not None else None

    def read_versions_through(self, station: str, revision: int) -> tuple[ScoreRevision, ...]:
        rows = self.db.execute(
            _VERSION_QUERY + ' WHERE v.station = ? AND v.revision <= ? ORDER BY v.revision',
            (station, revision),
        )
        return tuple(_read_version(row) for row in rows)

    def _establish_occurrence(self, pair: ScorePair) -> None:
        registered = self.db.execute(
            'SELECT first_model, second_model FROM station_model_pairs WHERE station = ?',
            (pair.station,),
        ).fetchone()
        if registered is None:
            self.db.execute(
                'INSERT INTO station_model_pairs(station, first_model, second_model) VALUES (?, ?, ?)',
                (pair.station, *pair.models.names),
            )
        elif registered != pair.models.names:
            raise Conflict('the station already uses a different ordered model pair')
        self.db.execute(
            'INSERT INTO score_occurrences(station, occurrence, ticket) VALUES (?, ?, ?)',
            (pair.station, pair.occurrence, pair.ticket),
        )

    def append_revision(self, pair: ScorePair, correction_code: str | None = None) -> ScoreRevision:
        if correction_code is None:
            self._establish_occurrence(pair)
        cursor = self.db.execute('''
            INSERT INTO score_versions(station, occurrence, label, first_score, second_score, correction_code)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (pair.station, pair.occurrence, pair.label.value, str(pair.scores[0]),
              str(pair.scores[1]), correction_code))
        return ScoreRevision(cursor.lastrowid, pair, correction_code)
