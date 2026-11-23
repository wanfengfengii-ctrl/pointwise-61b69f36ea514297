from dataclasses import dataclass

from storage import Conflict, InvalidInput, identifier


@dataclass(frozen=True)
class BoardTicket:
    number: str
    entity: str


def validate_ticket(ticket: BoardTicket) -> None:
    if not isinstance(ticket, BoardTicket):
        raise InvalidInput('a BoardTicket is required')
    identifier(ticket.number, 'ticket number')
    identifier(ticket.entity, 'board identity')


def check_ticket_consistency(existing: BoardTicket | None, proposed: BoardTicket) -> None:
    if existing is not None and existing != proposed:
        raise Conflict('the ticket already identifies a different board')
