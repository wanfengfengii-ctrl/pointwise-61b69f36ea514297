import json

from handoff.package import decode_evidence
from review import Correction, EvidenceSource, StationCatalog, accept_station, encode_evidence, freeze_station, record_pair
from storage import InvalidEvidence, MissingItem
from tests.support import ALIGNED_ROWS, MODELS, ReviewTest, named_scores, sample, scenario


def board_scores(package):
    return {f'{bucket.ticket}:{bucket.label.value}': [
        [[str(score), count] for score, count in column] for column in bucket.columns
    ] for bucket in package.contributions}


class HandoffTests(ReviewTest):
    def test_freeze_original_and_revision(self):
        base_revision = self.seed_station('East', ALIGNED_ROWS)
        original = freeze_station(self.source, self.archive, 'East', base_revision)
        record_pair(self.source, 'East', 'P', 'p-positive', 'positive', MODELS, named_scores(2, 0),
                    correction=Correction('revise-p'))
        updated = record_pair(self.source, 'East', 'Q', 'q-positive', 'positive', MODELS, named_scores(0, 2),
                              correction=Correction('revise-q'))
        corrected = freeze_station(self.source, self.archive, 'East', updated.revision)
        self.assertNotEqual(original.package_id, corrected.package_id)
        self.assertEqual(freeze_station(self.source, self.archive, 'East', base_revision), original)
        self.assertEqual(freeze_station(self.source, self.archive, 'East', updated.revision), corrected)
        self.source.close()
        self.reopen_archive()
        first = StationCatalog(self.archive).read(original.package_id)
        second = StationCatalog(self.archive).read(corrected.package_id)
        self.assertEqual(first.source, EvidenceSource('test-center', 'East', str(base_revision)))
        self.assertEqual(second.source, EvidenceSource('test-center', 'East', str(updated.revision)))
        self.assertEqual(first.models, MODELS)
        self.assertEqual(second.models, MODELS)
        before = {'P:positive': [[['2', 1]], [['2', 1]]], 'Q:positive': [[['0', 1]], [['0', 1]]],
                  'P:negative': [[['1', 1]], [['1', 1]]], 'Q:negative': [[['1', 1]], [['1', 1]]]}
        after = {**before, 'P:positive': [[['2', 1]], [['0', 1]]], 'Q:positive': [[['0', 1]], [['2', 1]]]}
        observed = [board_scores(first), board_scores(second)]
        self.assertEqual(observed, [before, after], 'FROZEN_BOARD_CONTRIBUTIONS')
        for column in (0, 1):
            marginal = lambda groups: sorted((key.split(':')[1], score, count)
                                             for key, columns in groups.items() for score, count in columns[column])
            self.assertEqual(marginal(observed[0]), marginal(observed[1]))
        fixed_sources = [first.source.revision, second.source.revision]
        scenario('v3.board_contributions', {'rows': ALIGNED_ROWS, 'second_model_corrections': {'P': '0', 'Q': '2'}},
                 [before, after], observed, [str(base_revision), str(updated.revision)], fixed_sources,
                 ['scoring/snapshots.py', 'handoff/freeze.py', 'handoff/package.py', 'handoff/catalog.py'],
                 'Only the second model positive scores trade boards. Both negative groups and both score marginals persist.')

    def test_foreign_source_mismatch(self):
        package = sample('foreign-stations.json')['reverse']
        payload = json.dumps(package)
        source = EvidenceSource(**package['source'])
        self.source.close()
        with self.assertRaises(InvalidEvidence) as caught:
            accept_station(self.archive, payload, EvidenceSource('wrong-lab', source.station, source.revision))
        with self.assertRaises(MissingItem):
            StationCatalog(self.archive).read(package['package_id'])
        self.assertEqual(self.archive.execute('SELECT COUNT(*) FROM station_packages').fetchone()[0], 0)
        accepted = accept_station(self.archive, payload, source)
        self.assertEqual(StationCatalog(self.archive).read(package['package_id']), accepted)
        self.assertEqual(decode_evidence(encode_evidence(accepted)), accepted)
        count = self.archive.execute('SELECT COUNT(*) FROM station_packages').fetchone()[0]
        self.assertEqual(count, 1)
        scenario('v4.source_agreement', {'package_source': package['source'], 'first_declared_origin': 'wrong-lab'},
                 'INVALID_STATION_EVIDENCE', caught.exception.code, 1, count,
                 ['handoff/package.py', 'handoff/exchange.py', 'handoff/catalog.py'],
                 'A different declared origin leaves no entry. The matching declaration registers exactly the submitted package.')

    def test_acceptance_canonicalizes_and_checks_fixed_identity(self):
        original = self.accept_partner('aligned')
        repeated = sample('foreign-stations.json')['aligned']
        repeated['package_id'] = 'second-name-for-original'
        repeated['contributions'][0]['scores'][0][0][0] = '4/2'
        repeated['contributions'].reverse()
        self.assertEqual(accept_station(self.archive, json.dumps(repeated), original.source), original)
        with self.assertRaises(MissingItem):
            StationCatalog(self.archive).read(repeated['package_id'])
        repeated['contributions'][0]['scores'][0][0][0] = '7'
        with self.assertRaises(InvalidEvidence):
            accept_station(self.archive, json.dumps(repeated), original.source)
        collision = sample('foreign-stations.json')['reverse']
        collision['package_id'] = original.package_id
        with self.assertRaises(InvalidEvidence):
            accept_station(self.archive, json.dumps(collision), EvidenceSource(**collision['source']))
        self.assertEqual(StationCatalog(self.archive).read(original.package_id), original)
        self.assertEqual(self.archive.execute('SELECT COUNT(*) FROM station_packages').fetchone()[0], 1)

    def test_invalid_contribution_or_version_does_not_register(self):
        invalid = []
        for count in (0, True, 2):
            payload = sample('foreign-stations.json')['reverse']
            payload['contributions'][0]['scores'][1][0][1] = count
            invalid.append(payload)
        payload = sample('foreign-stations.json')['reverse']
        payload['contributions'].append(payload['contributions'][0])
        invalid.append(payload)
        payload = sample('foreign-stations.json')['reverse']
        payload['version'] = True
        invalid.append(payload)
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(InvalidEvidence):
                accept_station(self.archive, json.dumps(payload), EvidenceSource(**payload['source']))
        self.assertEqual(self.archive.execute('SELECT COUNT(*) FROM station_packages').fetchone()[0], 0)

    def test_revision_must_belong_to_requested_station(self):
        revision = self.seed_station('East', ALIGNED_ROWS)
        with self.assertRaises(MissingItem):
            freeze_station(self.source, self.archive, 'West', revision)
        with self.assertRaises(MissingItem):
            freeze_station(self.source, self.archive, 'East', revision + 1)
        self.assertEqual(self.archive.execute('SELECT COUNT(*) FROM station_packages').fetchone()[0], 0)
