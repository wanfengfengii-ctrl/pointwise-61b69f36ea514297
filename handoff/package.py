import json

from boards.labels import parse_label
from handoff.evidence import BoardContribution, EvidenceSource, StationEvidence, validate_evidence
from scoring.pairs import ModelPair, parse_score
from storage import InvalidEvidence, InvalidInput


PACKAGE_VERSION = 1


def encode_evidence(evidence: StationEvidence) -> str:
    evidence = validate_evidence(evidence)
    payload = {
        'version': PACKAGE_VERSION,
        'package_id': evidence.package_id,
        'source': {
            'origin': evidence.source.origin,
            'station': evidence.source.station,
            'revision': evidence.source.revision,
        },
        'models': evidence.models.names,
        'contributions': [
            {
                'ticket': bucket.ticket,
                'label': bucket.label.value,
                'scores': [[(str(score), count) for score, count in column]
                           for column in bucket.columns],
            }
            for bucket in evidence.contributions
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _unique_fields(pairs: list) -> dict:
    result = {}
    for name, value in pairs:
        if name in result:
            raise InvalidEvidence(f'duplicate JSON field {name!r}')
        result[name] = value
    return result


def _object(value: object, fields: set[str], description: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise InvalidEvidence(f'invalid fields for {description}')
    return value


def _array(value: object, description: str, size: int | None = None) -> list:
    if not isinstance(value, list) or (size is not None and len(value) != size):
        raise InvalidEvidence(f'invalid array for {description}')
    return value


def _decode_column(value: object) -> tuple:
    tallies = []
    for entry in _array(value, 'score column'):
        raw_score, count = _array(entry, 'score tally', 2)
        if not isinstance(raw_score, str):
            raise InvalidEvidence('package scores must be rational strings')
        tallies.append((parse_score(raw_score), count))
    return tuple(tallies)


def _decode_bucket(value: object) -> BoardContribution:
    bucket = _object(value, {'ticket', 'label', 'scores'}, 'board contribution')
    first, second = _array(bucket['scores'], 'model columns', 2)
    return BoardContribution(bucket['ticket'], parse_label(bucket['label']),
                             (_decode_column(first), _decode_column(second)))


def decode_evidence(payload: str) -> StationEvidence:
    if not isinstance(payload, str):
        raise InvalidEvidence('station package must be JSON text')
    try:
        data = json.loads(payload, object_pairs_hook=_unique_fields)
    except (ValueError, RecursionError) as exc:
        raise InvalidEvidence('invalid station package JSON') from exc
    data = _object(data, {'version', 'package_id', 'models', 'source', 'contributions'}, 'station package')
    if type(data['version']) is not int or data['version'] != PACKAGE_VERSION:
        raise InvalidEvidence('unsupported station package version')
    source = _object(data['source'], {'origin', 'station', 'revision'}, 'package source')
    try:
        models = ModelPair(*_array(data['models'], 'model pair', 2))
        contributions = tuple(_decode_bucket(bucket) for bucket in _array(data['contributions'], 'contributions'))
    except InvalidInput as exc:
        raise InvalidEvidence(str(exc)) from exc
    return validate_evidence(StationEvidence(data['package_id'], EvidenceSource(**source), models, contributions))
