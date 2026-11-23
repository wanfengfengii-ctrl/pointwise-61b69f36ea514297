import argparse
from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.comparison import issue_comparison as issue_comparison
from boards.catalog import initialize_boards
from boards.stations import admit_board as admit_board
from boards.tickets import BoardTicket as BoardTicket
from handoff.catalog import StationCatalog as StationCatalog
from handoff.catalog import initialize_handoff
from handoff.evidence import EvidenceSource as EvidenceSource
from handoff.exchange import accept_station as accept_station
from handoff.freeze import freeze_station as freeze_station
from handoff.package import encode_evidence as encode_evidence
from records.publication import initialize_records
from records.retrieval import read_report as read_report
from scoring.intake import record_pair as record_pair
from scoring.ledger import initialize_scoring
from scoring.pairs import ModelPair as ModelPair
from scoring.revisions import Correction as Correction
from scoring.snapshots import read_station_snapshot as read_station_snapshot
from storage import connect_database, write_transaction


def open_source(path, *, origin: str | None = None):
    db = connect_database(path)
    try:
        with write_transaction(db):
            initialize_boards(db)
            initialize_scoring(db, origin=origin)
    except BaseException:
        db.close()
        raise
    return db


def open_archive(path):
    db = connect_database(path)
    try:
        with write_transaction(db):
            initialize_handoff(db)
            initialize_records(db)
    except BaseException:
        db.close()
        raise
    return db


def _sample(name: str):
    return json.loads((Path(__file__).resolve().parent / 'samples' / name).read_text(encoding='utf-8'))


def _freeze_shift(source, archive, shift: dict) -> dict[str, str]:
    models = ModelPair(*shift['models'])
    for board in shift['tickets']:
        ticket = BoardTicket(board['number'], board['entity'])
        for station in board['stations']:
            admit_board(source, ticket, station)
    packages = {}
    for station, measurements in shift['measurements'].items():
        latest = None
        for ticket, occurrence, label, left, right in measurements:
            scores = dict(zip(models.names, (left, right), strict=True))
            latest = record_pair(source, station, ticket, occurrence, label, models, scores)
        if latest is None:
            raise ValueError(f'no sample measurements for {station}')
        packages[station] = freeze_station(source, archive, station, latest.revision).package_id
    return packages


def _numbers(report) -> dict:
    return {
        'auc': [str(value) for value in report.auc],
        'deletions': [[row.ticket, *(str(value) for value in row.auc)] for row in report.deletions],
        'covariance': str(report.covariance),
    }


def _show_comparison(archive, case_id, inputs, ids, expected, expected_ids, oracle, paths):
    delivery = issue_comparison(archive, ids)
    report_id = delivery.report.report_id
    received = read_report(archive, report_id)
    actual = _numbers(delivery.report)
    downstream_expected = {'package_ids': expected_ids, 'complete_receipt': True}
    downstream_actual = {
        'package_ids': [source.package_id for source in received.sources],
        'complete_receipt': received == delivery and received.receipt.report_id == report_id,
    }
    if actual != expected or downstream_actual != downstream_expected:
        raise RuntimeError(f'{case_id}: comparison or its archived receipt disagrees with the hand ledger')
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id,
        'input': inputs,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': paths,
        'oracle': oracle,
    }, ensure_ascii=False, sort_keys=True))
    print(read_report(archive, report_id, as_json=True))


def run_demo() -> None:
    shift = _sample('shift.json')
    manual = _sample('manual-ledger.json')
    partner = _sample('foreign-stations.json')['reverse']
    with TemporaryDirectory(prefix='film-review-') as directory:
        root = Path(directory)
        with closing(open_archive(root / 'archive.sqlite3')) as archive:
            with closing(open_source(root / 'source.sqlite3', origin=shift['origin'])) as source:
                ids = _freeze_shift(source, archive, shift)
            _show_comparison(
                archive, 'v6.reversed_selection',
                {'measurements': shift['measurements'], 'station_order': ['West', 'East']},
                [ids['West'], ids['East']], manual['cross_station'], [ids['East'], ids['West']],
                manual['oracles']['cross_station'],
                ['handoff/freeze.py', 'analysis/pool.py', 'analysis/jackknife.py', 'records/retrieval.py'],
            )
            imported = accept_station(archive, json.dumps(partner), EvidenceSource(**partner['source']))
            _show_comparison(
                archive, 'v5.aligned_pairs', partner, [imported.package_id], manual['reverse'],
                [partner['package_id']], manual['oracles']['reverse'],
                ['handoff/exchange.py', 'analysis/jackknife.py', 'records/publication.py', 'records/retrieval.py'],
            )


def main() -> None:
    parser = argparse.ArgumentParser(description='Paired film inspection review')
    parser.add_argument('command', choices=['demo'])
    parser.parse_args()
    run_demo()


if __name__ == '__main__':
    main()
