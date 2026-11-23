import json
import sqlite3

from review import Correction, freeze_station, issue_comparison, read_report, read_station_snapshot, record_pair
from storage import MissingItem, PublicationFailed
from tests.support import ALIGNED_ROWS, MODELS, ReviewTest, named_scores, reject_report_commit, report_numbers, sample, scenario


class PublicationTests(ReviewTest):
    def test_failed_commit_has_no_receipt(self):
        package = self.accept_partner('aligned')
        prior = issue_comparison(self.archive, [package.package_id])
        prior_id = prior.report.report_id
        counts_before = self.record_counts()
        self.assertEqual(counts_before, (1, 1, 1))
        reject_report_commit(self.archive)
        other = self.accept_partner('reverse')
        with self.assertRaises(PublicationFailed) as caught:
            issue_comparison(self.archive, [other.package_id])
        self.assertIsInstance(caught.exception.__cause__, sqlite3.IntegrityError)
        self.assertFalse(self.archive.in_transaction)
        self.reopen_archive()
        actual = self.record_counts()
        self.assertEqual(actual, counts_before)
        self.assertEqual(self.archive.execute('SELECT COUNT(*) FROM pending_report_links').fetchone()[0], 0)
        self.assertEqual(read_report(self.archive, prior_id), prior)
        with self.assertRaises(MissingItem):
            read_report(self.archive, prior_id + 1)
        scenario('v8.no_provenance', {'existing_report': prior_id, 'new_package': other.package_id,
                                      'constraint': 'deferred foreign key on receipt insertion'},
                 'PUBLICATION_FAILED', caught.exception.code, counts_before, actual,
                 ['analysis/comparison.py', 'records/publication.py', 'records/provenance.py', 'records/receipts.py'],
                 'The deferred constraint rejects the commit after all three report writes. Reopening must show only the old report.')

    def test_read_frozen_after_correction(self):
        revision = self.seed_station('East', ALIGNED_ROWS)
        old_station = freeze_station(self.source, self.archive, 'East', revision)
        old = issue_comparison(self.archive, [old_station.package_id])
        old_id = old.report.report_id
        old_export = read_report(self.archive, old_id, as_json=True)
        record_pair(self.source, 'East', 'P', 'p-positive', 'positive', MODELS, named_scores(2, 0),
                    correction=Correction('correct-p'))
        update = record_pair(self.source, 'East', 'Q', 'q-positive', 'positive', MODELS, named_scores(0, 2),
                             correction=Correction('correct-q'))
        self.reopen_source()
        self.reopen_archive()
        snapshot = read_station_snapshot(self.source, 'East', update.revision)
        current = {row.pair.occurrence: str(row.pair.scores[1]) for row in snapshot.occurrences}
        self.assertEqual((current['p-positive'], current['q-positive']), ('0', '2'))
        revised_station = freeze_station(self.source, self.archive, 'East', update.revision)
        self.assertNotEqual(revised_station.package_id, old_station.package_id)
        self.source.close()
        newer = issue_comparison(self.archive, [revised_station.package_id])
        self.assertNotEqual(newer.report.report_id, old_id)
        manual = sample('manual-ledger.json')
        self.assertEqual(report_numbers(newer.report), manual['reverse'])
        self.reopen_archive()
        restored = read_report(self.archive, old_id)
        self.assertEqual(restored, old)
        self.assertEqual(report_numbers(restored.report), manual['aligned'])
        restored_export = read_report(self.archive, old_id, as_json=True)
        self.assertEqual(restored_export, old_export)
        expected_export = {
            'report_id': old_id,
            'models': ['Line-A', 'Line-B'],
            'auc': [{'numerator': 1, 'denominator': 2}] * 2,
            'deletions': [
                {'ticket': 'P', 'auc': [{'numerator': 0, 'denominator': 1}] * 2},
                {'ticket': 'Q', 'auc': [{'numerator': 1, 'denominator': 1}] * 2},
            ],
            'covariance': {'numerator': 1, 'denominator': 4},
            'sources': [{'package_id': old_station.package_id, 'station': 'East', 'origin': 'test-center',
                         'revision': str(revision)}],
            'receipt': {'report_id': old_id, 'receipt_id': f'receipt-{old_id}'},
        }
        actual_export = json.loads(restored_export)
        self.assertEqual(actual_export, expected_export)
        scenario('v9.old_id_after_new_issue', {'requested_report': old_id, 'new_report': newer.report.report_id},
                 manual['aligned'], report_numbers(restored.report), expected_export, actual_export,
                 ['scoring/snapshots.py', 'records/publication.py', 'records/retrieval.py', 'records/export.py'],
                 'The first fixed station revision has aligned columns. The later signed report cannot change the older report, provenance or receipt.')

    def test_unknown_report_is_missing_in_both_delivery_modes(self):
        for as_json in (False, True):
            with self.assertRaises(MissingItem):
                read_report(self.archive, 991, as_json=as_json)
