from contextlib import contextmanager
import sqlite3


class ReviewError(Exception):
    code = 'REVIEW_ERROR'


class InvalidInput(ReviewError):
    code = 'INVALID_INPUT'


class Conflict(ReviewError):
    code = 'CONFLICT'


class MissingItem(ReviewError):
    code = 'MISSING_ITEM'


class InvalidEvidence(ReviewError):
    code = 'INVALID_STATION_EVIDENCE'


class InvalidSelection(ReviewError):
    code = 'INVALID_SELECTION'


class InsufficientEvidence(ReviewError):
    code = 'INSUFFICIENT_EVIDENCE'


class PublicationFailed(ReviewError):
    code = 'PUBLICATION_FAILED'


def identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.isprintable() or value.strip() != value:
        raise InvalidInput(f'{field} must be a nonempty printable string without outer whitespace')
    return value


def require_sqlite_id(value: object, item: str) -> int:
    if type(value) is not int or value <= 0:
        raise InvalidInput(f'{item} must be a positive integer')
    if value >= 2**63:
        raise MissingItem(f'no such {item}')
    return value


def connect_database(path) -> sqlite3.Connection:
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.execute('PRAGMA foreign_keys = ON')
    except BaseException:
        db.close()
        raise
    return db


@contextmanager
def write_transaction(db: sqlite3.Connection):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
