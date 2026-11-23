from dataclasses import dataclass
import sqlite3

from boards.catalog import BoardCatalog
from boards.tickets import BoardTicket, check_ticket_consistency, validate_ticket
from storage import MissingItem, identifier, write_transaction


@dataclass(frozen=True)
class StationAdmission:
    ticket: BoardTicket
    station: str
    revision: int


def admit_board(db: sqlite3.Connection, ticket: BoardTicket, station: str) -> StationAdmission:
    validate_ticket(ticket)
    identifier(station, 'station')
    catalog = BoardCatalog(db)
    with write_transaction(db):
        existing = catalog.read_ticket(ticket.number)
        check_ticket_consistency(existing, ticket)
        revision = catalog.read_admission(ticket.number, station)
        if revision is None:
            revision = catalog.save_admission(ticket, station)
    return StationAdmission(ticket, station, revision)


def require_admission(db: sqlite3.Connection, station: str, ticket: str) -> int:
    catalog = BoardCatalog(db)
    revision = catalog.read_admission(ticket, station)
    if revision is None:
        raise MissingItem(f'ticket {ticket!r} has no admission at station {station!r}')
    return revision
