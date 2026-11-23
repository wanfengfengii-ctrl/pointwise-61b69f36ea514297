import sqlite3

from boards.tickets import BoardTicket
from storage import Conflict


def initialize_boards(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS board_tickets (
            number TEXT PRIMARY KEY NOT NULL,
            entity TEXT NOT NULL UNIQUE
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS station_admissions (
            revision INTEGER PRIMARY KEY,
            ticket TEXT NOT NULL REFERENCES board_tickets(number),
            station TEXT NOT NULL,
            UNIQUE (ticket, station)
        )
    ''')


class BoardCatalog:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def read_ticket(self, number: str) -> BoardTicket | None:
        row = self.db.execute(
            'SELECT number, entity FROM board_tickets WHERE number = ?', (number,)
        ).fetchone()
        return BoardTicket(*row) if row is not None else None

    def read_admission(self, ticket: str, station: str) -> int | None:
        row = self.db.execute(
            'SELECT revision FROM station_admissions WHERE ticket = ? AND station = ?',
            (ticket, station),
        ).fetchone()
        return row[0] if row is not None else None

    def save_admission(self, ticket: BoardTicket, station: str) -> int:
        existing_number = self.db.execute(
            'SELECT number FROM board_tickets WHERE entity = ?', (ticket.entity,)
        ).fetchone()
        if existing_number is not None and existing_number[0] != ticket.number:
            raise Conflict('the board already has a different ticket')
        self.db.execute(
            'INSERT INTO board_tickets(number, entity) VALUES (?, ?) ON CONFLICT(number) DO NOTHING',
            (ticket.number, ticket.entity),
        )
        cursor = self.db.execute(
            'INSERT INTO station_admissions(ticket, station) VALUES (?, ?)',
            (ticket.number, station),
        )
        return cursor.lastrowid
