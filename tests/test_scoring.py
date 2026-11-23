from fractions import Fraction

from review import BoardTicket, Correction, ModelPair, admit_board, freeze_station, read_station_snapshot, record_pair
from storage import Conflict, InvalidInput, MissingItem
from tests.support import MODELS, ReviewTest, named_scores, scenario


class ScoringTests(ReviewTest):
    def test_repeat_preserves_occurrence(self):
        for station in ('East', 'West'):
            self.admit('P', station)
        east = record_pair(self.source, 'East', 'P', 'same-1', 'positive', MODELS, named_scores('2/6', 1))
        west = record_pair(self.source, 'West', 'P', 'same-1', 'positive', MODELS, named_scores('1/3', 1))
        repeated = record_pair(self.source, 'East', 'P', 'same-1', 'positive', MODELS, named_scores('1/3', '2/2'))
        self.assertEqual(repeated, east)
        self.assertNotEqual(east.revision, west.revision)
        east_fixed = freeze_station(self.source, self.archive, 'East', east.revision)
        west_fixed = freeze_station(self.source, self.archive, 'West', west.revision)
        actual = [sum(count for bucket in package.contributions for _, count in bucket.columns[0])
                  for package in (east_fixed, west_fixed)]
        self.assertEqual(actual, [1, 1])
        scenario('v1.same_number_two_stations', {'station_order': ['East', 'West', 'East'], 'occurrence': 'same-1'},
                 [1, 1], actual, True, east == repeated,
                 ['boards/stations.py', 'scoring/intake.py', 'scoring/ledger.py', 'handoff/freeze.py'],
                 'One stable occurrence at each station, plus an equivalent replay at East.')

    def test_conflict_requires_revision(self):
        self.admit('P', 'East')
        original = record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores(2, 1))
        with self.assertRaises(Conflict):
            record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores(3, 1))
        unchanged = read_station_snapshot(self.source, 'East', original.revision)
        self.assertEqual(unchanged.occurrences, (original,))
        change = Correction('inspect-m')
        corrected = record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores(3, 1), correction=change)
        retry = record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores('6/2', 1), correction=change)
        self.assertGreater(corrected.revision, original.revision)
        self.assertEqual(retry, corrected)
        with self.assertRaises(Conflict):
            record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores(4, 1), correction=change)
        replay = record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores(2, 1))
        self.assertEqual(replay, original)
        snapshots = [read_station_snapshot(self.source, 'East', version.revision) for version in (original, corrected)]
        actual = [str(snapshot.occurrences[0].pair.scores[0]) for snapshot in snapshots]
        self.assertEqual(actual, ['2', '3'])
        scenario('v2.historical_revision', {'first_score': '2', 'corrected_score': '3'},
                 ['2', '3'], actual, True, retry == corrected,
                 ['scoring/intake.py', 'scoring/revisions.py', 'scoring/ledger.py', 'scoring/snapshots.py'],
                 'The second accepted value is a correction, so each fixed revision has its own score.')

    def test_conflicting_admission_preserves_original_qualification(self):
        original = self.admit('P', 'East')
        west = self.admit('P', 'West')
        self.assertNotEqual(original.revision, west.revision)
        with self.assertRaises(Conflict):
            admit_board(self.source, BoardTicket('P', 'different-board'), 'South')
        with self.assertRaises(Conflict):
            admit_board(self.source, BoardTicket('R', 'film-P'), 'South')
        self.assertEqual(self.admit('P', 'East'), original)
        self.assertEqual(self.admit('P', 'West'), west)
        with self.assertRaises(MissingItem):
            record_pair(self.source, 'South', 'P', 'm', 'positive', MODELS, named_scores(2, 1))
        record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores(2, 1))
        record_pair(self.source, 'West', 'P', 'm', 'positive', MODELS, named_scores(2, 1))

    def test_invalid_intake_does_not_create_measurement(self):
        self.admit('P', 'East')
        for label, scores in (
            ('unknown', named_scores(2, 1)),
            ('positive', named_scores(2.0, 1)),
            ('positive', named_scores(True, 1)),
            ('positive', named_scores('1/0', 1)),
            ('positive', {MODELS.first: 2}),
        ):
            with self.subTest(label=label, scores=scores), self.assertRaises(InvalidInput):
                record_pair(self.source, 'East', 'P', 'm', label, MODELS, scores)
        with self.assertRaises(MissingItem):
            record_pair(self.source, 'East', 'Z', 'm', 'positive', MODELS, named_scores(2, 1))
        with self.assertRaises(MissingItem):
            record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores(2, 1),
                        correction=Correction('before-intake'))
        accepted = record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores('1/3', '2/6'))
        self.assertEqual(accepted.pair.scores, (Fraction(1, 3), Fraction(1, 3)))
        self.assertEqual(read_station_snapshot(self.source, 'East', accepted.revision).occurrences, (accepted,))
        alternate = ModelPair('Line-B', 'Line-A')
        with self.assertRaises(Conflict):
            record_pair(self.source, 'East', 'P', 'other', 'negative', alternate, named_scores(1, 0, alternate))

    def test_correction_cannot_move_a_measurement_to_another_ticket(self):
        for ticket in ('P', 'Q'):
            self.admit(ticket, 'East')
        original = record_pair(self.source, 'East', 'P', 'm', 'negative', MODELS, named_scores(2, 1))
        with self.assertRaises(Conflict):
            record_pair(self.source, 'East', 'Q', 'm', 'positive', MODELS, named_scores(3, 1),
                        correction=Correction('move-m'))
        corrected = record_pair(self.source, 'East', 'P', 'm', 'positive', MODELS, named_scores(3, 1),
                                correction=Correction('inspect-m'))
        self.assertEqual(original.pair.label.value, 'negative')
        self.assertEqual(read_station_snapshot(self.source, 'East', corrected.revision).occurrences[0].pair.label.value,
                         'positive')
