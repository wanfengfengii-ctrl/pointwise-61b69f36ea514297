import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from review import BoardTicket, EvidenceSource, ModelPair, accept_station, admit_board, open_archive, open_source, record_pair


MODELS = ModelPair('Line-A', 'Line-B')
ALIGNED_ROWS = (
    ('P', 'p-positive', 'positive', '2', '2'),
    ('P', 'p-negative', 'negative', '1', '1'),
    ('Q', 'q-positive', 'positive', '0', '0'),
    ('Q', 'q-negative', 'negative', '1', '1'),
)


def sample(name):
    path = Path(__file__).resolve().parents[1] / 'samples' / name
    return json.loads(path.read_text(encoding='utf-8'))


def named_scores(left, right, models=MODELS):
    return {models.first: left, models.second: right}


def report_numbers(report):
    return {
        'auc': [str(value) for value in report.auc],
        'deletions': [[row.ticket, str(row.auc[0]), str(row.auc[1])] for row in report.deletions],
        'covariance': str(report.covariance),
    }


def scenario(case_id, inputs, expected, actual, downstream_expected, downstream_actual, paths, oracle):
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


def reject_report_commit(db):
    # The trigger inserts an invalid deferred reference, checked when the issue transaction commits.
    db.execute('CREATE TABLE allowed_report_links (report_id INTEGER PRIMARY KEY)')
    db.execute('''
        CREATE TABLE pending_report_links (
            report_id INTEGER REFERENCES allowed_report_links(report_id) DEFERRABLE INITIALLY DEFERRED
        )
    ''')
    db.execute('''
        CREATE TRIGGER check_report_commit AFTER INSERT ON report_receipts
        BEGIN
            INSERT INTO pending_report_links(report_id) VALUES (NEW.report_id);
        END
    ''')


class ReviewTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='film-review-test-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.source_path = root / 'source.sqlite3'
        self.archive_path = root / 'archive.sqlite3'
        self.source = self._track(open_source(self.source_path, origin='test-center'))
        self.archive = self._track(open_archive(self.archive_path))

    def _track(self, db):
        self.addCleanup(db.close)
        return db

    def reopen_source(self):
        self.source.close()
        self.source = self._track(open_source(self.source_path))

    def reopen_archive(self):
        self.archive.close()
        self.archive = self._track(open_archive(self.archive_path))

    def admit(self, ticket, station):
        return admit_board(self.source, BoardTicket(ticket, f'film-{ticket}'), station)

    def seed_station(self, station, rows, models=MODELS):
        latest = None
        for ticket, occurrence, label, left, right in rows:
            self.admit(ticket, station)
            latest = record_pair(self.source, station, ticket, occurrence, label, models,
                                 named_scores(left, right, models))
        if latest is None:
            raise ValueError('a station fixture must contain measurements')
        return latest.revision

    def accept_partner(self, name):
        document = sample('foreign-stations.json')[name]
        return accept_station(self.archive, json.dumps(document), EvidenceSource(**document['source']))

    def record_counts(self):
        tables = ('reports', 'report_sources', 'report_receipts')
        return tuple(self.archive.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables)
