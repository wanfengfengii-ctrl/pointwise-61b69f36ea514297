from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from boards.labels import Label, parse_label
from storage import InvalidInput, identifier


ScoreInput = int | str | Fraction


@dataclass(frozen=True)
class ModelPair:
    first: str
    second: str

    def __post_init__(self):
        identifier(self.first, 'first model')
        identifier(self.second, 'second model')
        if self.first == self.second:
            raise InvalidInput('the model names must be distinct')

    @property
    def names(self) -> tuple[str, str]:
        return self.first, self.second


@dataclass(frozen=True)
class ScorePair:
    station: str
    ticket: str
    occurrence: str
    label: Label
    models: ModelPair
    scores: tuple[Fraction, Fraction]


def parse_score(value: ScoreInput) -> Fraction:
    if type(value) is int or isinstance(value, (str, Fraction)):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError):
            pass
    raise InvalidInput('score must be an exact rational number')


def normalize_pair(
    station: str,
    ticket: str,
    occurrence: str,
    label: str | Label,
    models: ModelPair,
    scores: Mapping[str, ScoreInput],
) -> ScorePair:
    identifier(station, 'station')
    identifier(ticket, 'ticket number')
    identifier(occurrence, 'occurrence number')
    if not isinstance(models, ModelPair):
        raise InvalidInput('a named ModelPair is required')
    if not isinstance(scores, Mapping) or set(scores) != set(models.names):
        raise InvalidInput('provide one score for each named model')
    normalized = parse_score(scores[models.first]), parse_score(scores[models.second])
    return ScorePair(station, ticket, occurrence, parse_label(label), models, normalized)
