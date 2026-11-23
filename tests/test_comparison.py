from fractions import Fraction

from analysis.auc import auc
from analysis.pool import score_distributions
from review import ModelPair, freeze_station, issue_comparison, read_report
from storage import InsufficientEvidence, InvalidSelection
from tests.support import ALIGNED_ROWS, ReviewTest, report_numbers, sample, scenario


class ComparisonTests(ReviewTest):
    def test_paired_covariance(self):
        self.source.close()
        manual = sample('manual-ledger.json')
        for name in ('aligned', 'reverse'):
            with self.subTest(name=name):
                package = self.accept_partner(name)
                delivery = issue_comparison(self.archive, [package.package_id])
                self.assertEqual(delivery.report.auc, (Fraction(1, 2), Fraction(1, 2)))
                self.assertEqual(str(delivery.report.covariance), manual[name]['covariance'], 'PAIRED_AUC_COVARIANCE')
                actual = report_numbers(delivery.report)
                self.assertEqual(actual, manual[name])
                received = read_report(self.archive, delivery.report.report_id)
                self.assertEqual(received, delivery)
                self.assertEqual([source.package_id for source in received.sources], [package.package_id])
                scenario('v5.aligned_pairs', sample('foreign-stations.json')[name], manual[name], actual,
                         [package.package_id], [source.package_id for source in received.sources],
                         ['handoff/exchange.py', 'analysis/jackknife.py', 'records/retrieval.py'],
                         manual['oracles'][name])

    def test_delete_board_across_stations(self):
        shift = sample('shift.json')
        packages = []
        for station in ('East', 'West'):
            revision = self.seed_station(station, shift['measurements'][station])
            packages.append(freeze_station(self.source, self.archive, station, revision).package_id)
        self.source.close()
        forward = issue_comparison(self.archive, packages)
        reverse = issue_comparison(self.archive, reversed(packages))
        repeated = issue_comparison(self.archive, [packages[1], packages[0], packages[1]])
        manual = sample('manual-ledger.json')
        expected = manual['cross_station']
        for delivery in (forward, reverse, repeated):
            self.assertEqual(report_numbers(delivery.report), expected)
            self.assertEqual(delivery.sources, forward.sources)
        actual_ids = [source.package_id for source in read_report(self.archive, reverse.report.report_id).sources]
        self.assertEqual(actual_ids, packages)
        scenario('v6.reversed_selection', {'measurements': shift['measurements'], 'selection': packages[::-1]},
                 expected, report_numbers(reverse.report), packages, actual_ids,
                 ['handoff/freeze.py', 'analysis/selection.py', 'analysis/pool.py', 'analysis/jackknife.py'],
                 manual['oracles']['cross_station'])

    def test_insufficient_valid_deletions(self):
        rows = ALIGNED_ROWS[:2] + ALIGNED_ROWS[3:]
        revision = self.seed_station('East', rows)
        fixed = freeze_station(self.source, self.archive, 'East', revision)
        self.source.close()
        left, right = score_distributions(fixed.contributions)
        self.assertEqual((auc(*left), auc(*right)), (Fraction(1), Fraction(1)))
        with self.assertRaises(InsufficientEvidence) as caught:
            issue_comparison(self.archive, [fixed.package_id])
        self.assertIn('at least two valid board deletions', str(caught.exception))
        counts = self.record_counts()
        self.assertEqual(counts, (0, 0, 0))
        scenario('v7.no_publication', rows, 'INSUFFICIENT_EVIDENCE', caught.exception.code,
                 [0, 0, 0], counts, ['analysis/jackknife.py', 'analysis/comparison.py', 'records/publication.py'],
                 'Removing P erases the only positive. Removing Q is valid, leaving just one deletion row.')

    def test_full_missing_class(self):
        rows = ALIGNED_ROWS[1::2]
        revision = self.seed_station('East', rows)
        fixed = freeze_station(self.source, self.archive, 'East', revision)
        with self.assertRaises(InsufficientEvidence) as caught:
            issue_comparison(self.archive, [fixed.package_id])
        self.assertIn('both positive and negative', str(caught.exception))
        self.assertEqual(self.record_counts(), (0, 0, 0))

    def test_equal_scores_and_cross_station_pairs(self):
        rows = (
            ('P', 'p1', 'positive', '1/3', '5/7'), ('P', 'p2', 'negative', '2/6', '10/14'),
            ('Q', 'q1', 'positive', '1/3', '5/7'), ('Q', 'q2', 'negative', '2/6', '10/14'),
        )
        revision = self.seed_station('Tie', rows)
        tie = freeze_station(self.source, self.archive, 'Tie', revision)
        tied_report = issue_comparison(self.archive, [tie.package_id]).report
        self.assertEqual(tied_report.auc, (Fraction(1, 2), Fraction(1, 2)))
        self.assertEqual([row.auc for row in tied_report.deletions], [(Fraction(1, 2),) * 2] * 2)
        self.assertEqual(tied_report.covariance, 0)

        east_rows = ALIGNED_ROWS[:2]
        west_rows = (('Q', 'q1', 'positive', '4', '4'), ('Q', 'q2', 'negative', '3', '3'))
        packages = []
        for station, measurements in (('East', east_rows), ('West', west_rows)):
            revision = self.seed_station(station, measurements)
            package = freeze_station(self.source, self.archive, station, revision)
            self.assertEqual(tuple(auc(*column) for column in score_distributions(package.contributions)),
                             (Fraction(1), Fraction(1)))
            packages.append(package.package_id)
        self.source.close()
        pooled = issue_comparison(self.archive, packages)
        self.assertEqual(pooled.report.auc, (Fraction(3, 4), Fraction(3, 4)))
        self.assertEqual([row.auc for row in pooled.report.deletions], [(Fraction(1),) * 2] * 2)
        self.assertEqual(pooled.report.covariance, 0)
        received = read_report(self.archive, pooled.report.report_id)
        self.assertEqual(received, pooled)
        scenario('v10.cross_station_pairs', {'East': east_rows, 'West': west_rows},
                 ['3/4', '3/4'], [str(value) for value in pooled.report.auc],
                 packages, [source.package_id for source in received.sources],
                 ['analysis/selection.py', 'analysis/pool.py', 'analysis/auc.py', 'analysis/comparison.py'],
                 'The four comparisons are 2>1, 2<3, 4>1 and 4>3. The 2<3 cross-station pair loses.')

    def test_score_multiplicities_are_retained_in_pool(self):
        rows = ALIGNED_ROWS + (('P', 'p-repeat', 'positive', '2', '2'),)
        revision = self.seed_station('East', rows)
        package = freeze_station(self.source, self.archive, 'East', revision)
        delivered = issue_comparison(self.archive, [package.package_id])
        self.assertEqual(delivered.report.auc, (Fraction(2, 3), Fraction(2, 3)))
        self.assertEqual(delivered.report.covariance, Fraction(1, 4))

    def test_illegal_package_selection_cannot_publish(self):
        aligned = self.accept_partner('aligned')
        reverse = self.accept_partner('reverse')
        other_models = ModelPair('Line-B', 'Line-A')
        revision = self.seed_station('East', ALIGNED_ROWS, other_models)
        east = freeze_station(self.source, self.archive, 'East', revision)
        for ids in ([], ['missing'], aligned.package_id, [[aligned.package_id]],
                    [aligned.package_id, reverse.package_id], [east.package_id, reverse.package_id]):
            with self.subTest(ids=ids), self.assertRaises(InvalidSelection):
                issue_comparison(self.archive, ids)
        self.assertEqual(self.record_counts(), (0, 0, 0))
