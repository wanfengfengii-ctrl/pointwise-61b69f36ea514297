from collections.abc import Iterable
from dataclasses import dataclass

from handoff.catalog import StationCatalog
from handoff.evidence import StationEvidence
from scoring.pairs import ModelPair
from storage import InvalidInput, InvalidSelection, MissingItem, identifier


@dataclass(frozen=True)
class SelectedEvidence:
    packages: tuple[StationEvidence, ...]
    models: ModelPair


def select_evidence(catalog: StationCatalog, package_ids: Iterable[str]) -> SelectedEvidence:
    if not isinstance(package_ids, Iterable) or isinstance(package_ids, (str, bytes, bytearray)):
        raise InvalidSelection('provide a collection of station package ids')
    try:
        ids = {identifier(package_id, 'package id') for package_id in package_ids}
        packages = [catalog.read(package_id) for package_id in sorted(ids)]
    except (InvalidInput, MissingItem) as exc:
        raise InvalidSelection(str(exc)) from exc
    if not packages:
        raise InvalidSelection('select at least one station package')

    models = packages[0].models
    stations = set()
    for package in packages:
        station = package.source.station
        if station in stations:
            raise InvalidSelection(f'more than one package selected for station {station!r}')
        if package.models != models:
            raise InvalidSelection('selected packages have different ordered model pairs')
        stations.add(station)
    packages.sort(key=lambda package: package.source.station)
    return SelectedEvidence(tuple(packages), models)
