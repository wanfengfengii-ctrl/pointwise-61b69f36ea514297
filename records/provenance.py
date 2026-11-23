from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class ReportSource:
    package_id: str
    station: str
    origin: str
    revision: str


def initialize_provenance(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS report_sources (
            report_id INTEGER NOT NULL REFERENCES reports(report_id),
            position INTEGER NOT NULL,
            package_id TEXT NOT NULL REFERENCES station_packages(package_id),
            station TEXT NOT NULL,
            origin TEXT NOT NULL,
            revision TEXT NOT NULL,
            PRIMARY KEY (report_id, position),
            UNIQUE (report_id, station)
        )
    ''')


def save_sources(db: sqlite3.Connection, report_id: int, sources: tuple[ReportSource, ...]) -> None:
    db.executemany('''
        INSERT INTO report_sources(report_id, position, package_id, station, origin, revision)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ((report_id, index, source.package_id, source.station, source.origin, source.revision)
          for index, source in enumerate(sources)))


def read_sources(db: sqlite3.Connection, report_id: int) -> tuple[ReportSource, ...]:
    rows = db.execute('''
        SELECT package_id, station, origin, revision FROM report_sources
        WHERE report_id = ? ORDER BY position
    ''', (report_id,))
    return tuple(ReportSource(*row) for row in rows)
