from enum import StrEnum

from storage import InvalidInput


class Label(StrEnum):
    POSITIVE = 'positive'
    NEGATIVE = 'negative'


def parse_label(value: object) -> Label:
    if isinstance(value, str):
        try:
            return Label(value)
        except ValueError:
            pass
    raise InvalidInput('label must be positive or negative')
