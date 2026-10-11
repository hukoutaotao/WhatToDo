"""Storage admission/projection preserves independent Task facts and versions."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.application.definitions import DefinitionKey
from src.application.task_storage import (TaskStorageBindings, TaskStorageError,
    admit_storage, project_task, sql_value)
from tools.check_contract_registry import trusted_schemas


class TaskStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = ContractJSONCodec(trusted_schemas())
        cls.cases = json.loads((Path(__file__).parent/'fixtures/task_aggregate/cases.json').read_text())['cases']

    def example(self, name='aggregate-unknown-facts'):
        return deepcopy(next(c['payload'] for c in self.cases if c['id'] == name))

    def record(self, value):
        return admit_storage(self.codec, json.dumps(value, ensure_ascii=False, indent=2).encode())

    def test_supported_examples_retain_original_bytes_and_independent_dimensions(self):
        for case in self.cases:
            if not case['valid']:
                continue
            value = deepcopy(case['payload'])
            binding = TaskStorageBindings()
            if value['core']['disposition'] == 'EXPIRED':
                value['core']['revision'] = value['effort']['task_revision'] = 2
                binding = TaskStorageBindings(notice_task_revision=1)
            record = self.record(value)
            rows = project_task(record, binding).rows
            self.assertEqual(json.loads(record.raw_bytes), value)
            self.assertEqual(rows['task_revision']['metadata'], value['core']['metadata'])
            self.assertEqual(rows['task_revision']['disposition'], value['core']['disposition'])
            self.assertEqual(rows['task_revision']['completion'], value['core']['completion'])
            self.assertEqual(record.aggregate.as_record(), value)

    def test_admission_is_required_and_negative_shapes_are_not_storage_records(self):
        for case in self.cases:
            if not case['valid']:
                with self.subTest(case=case['id']), self.assertRaises(TaskStorageError):
                    self.record(case['payload'])
        bad = self.example()
        bad['effort']['task_id'] = 'unrelated'
        with self.assertRaisesRegex(TaskStorageError, 'TASK_STORAGE_ADMISSION'):
            self.record(bad)
        with self.assertRaisesRegex(TaskStorageError, 'TASK_STORAGE_SIZE'):
            admit_storage(self.codec, b'x'*1048577)

    def test_raw_hash_and_aggregate_cannot_disagree(self):
        record = self.record(self.example())
        with self.assertRaisesRegex(TaskStorageError, 'TASK_STORAGE_HASH'):
            replace(record, content_hash='f'*64)
        value = self.example()
        value['core']['title'] = 'Another task'
        with self.assertRaisesRegex(TaskStorageError, 'TASK_STORAGE_PAYLOAD_DRIFT'):
            replace(record, aggregate=self.record(value).aggregate)

    def test_course_and_activity_require_explicit_matching_profile_versions(self):
        for context, kind in [('COURSE', 'COURSE_PROFILE'), ('ACTIVITY', 'ACTIVITY_PROFILE')]:
            value = self.example()
            value['core']['context'] = dict(kind=context, id='synthetic-context')
            value['core']['task_type_ref'] = dict(id='synthetic-type', version='old-version')
            record = self.record(value)
            with self.assertRaisesRegex(TaskStorageError, 'TASK_STORAGE_PROFILE_VERSION_REQUIRED'):
                project_task(record, TaskStorageBindings())
            key = DefinitionKey(kind, 'synthetic-context', 'explicit-old-version')
            rows = project_task(record, TaskStorageBindings(key)).rows
            self.assertEqual(rows['task_payload_revision']['profile_ref'], key.configuration_ref)
            self.assertEqual(rows['task_revision']['task_type_ref'],
                DefinitionKey('TASKTYPE', 'synthetic-type', 'old-version').configuration_ref)
            with self.assertRaises(TaskStorageError):
                project_task(record, TaskStorageBindings(DefinitionKey(kind, 'wrong-context', '1')))

    def test_expired_history_requires_a_real_older_notice_revision(self):
        value = self.example('aggregate-expired-retains-positive-u')
        value['core']['revision'] = value['effort']['task_revision'] = 2
        record = self.record(value)
        for revision in [None, 2, 3]:
            with self.assertRaisesRegex(TaskStorageError, 'TASK_STORAGE_NOTICE_REVISION_REQUIRED'):
                project_task(record, TaskStorageBindings(notice_task_revision=revision))
        rows = project_task(record, TaskStorageBindings(notice_task_revision=1)).rows
        self.assertEqual(rows['task_revision']['user_remaining_seconds'], 2400)
        self.assertEqual(rows['task_revision']['completion'], 'INCOMPLETE')
        with self.assertRaisesRegex(TaskStorageError, 'TASK_STORAGE_UNEXPECTED_NOTICE_REVISION'):
            project_task(self.record(self.example()), TaskStorageBindings(notice_task_revision=1))

    def test_stage_order_titles_estimates_and_exact_weights_survive_projection(self):
        value = self.example('aggregate-stages-retain-historical-completed-stage-u')
        value['stage_details'].reverse()
        value['stage_details'][0]['title'] = 'x'*200
        record = self.record(value)
        rows = project_task(record, TaskStorageBindings()).rows
        self.assertEqual([r['stage_id'] for r in rows['task_stage_revision']],
            [s['stage_id'] for s in value['effort']['stages']])
        self.assertEqual({r['stage_id']: r['title'] for r in rows['stage_revision']},
            {s['stage_id']: s['title'] for s in value['stage_details']})
        self.assertTrue(any(r['completion'] == 'COMPLETE' and r['user_remaining_seconds'] == 600
            for r in rows['stage_revision']))
        self.assertEqual(record.aggregate.as_record()['stage_details'], value['stage_details'])

    def test_unknown_zero_total_current_u_and_predictions_remain_separate(self):
        value = self.example('aggregate-explicit-facts-and-original-total-below-current-u')
        record = self.record(value)
        rows = project_task(record, TaskStorageBindings()).rows
        self.assertEqual(rows['task_revision']['user_remaining_seconds'], 2400)
        self.assertEqual(rows['task_details_revision']['total_estimate_seconds'], 1800)
        value['effort']['user_remaining'] = None
        value['work']['total_estimate']['seconds'] = 0
        rows = project_task(self.record(value), TaskStorageBindings()).rows
        self.assertIsNone(rows['task_revision']['user_remaining_seconds'])
        self.assertEqual(rows['task_details_revision']['total_estimate_seconds'], 0)

    def test_detached_projections_and_time_offsets_do_not_rewrite_stored_facts(self):
        record = self.record(self.example('aggregate-explicit-facts-and-original-total-below-current-u'))
        projected = project_task(record, TaskStorageBindings())
        rows = projected.rows
        original = rows['task_details_revision']['release_original']
        rows['task_revision']['metadata']['trust'] = 'UNKNOWN'
        self.assertEqual(projected.rows['task_revision']['metadata']['trust'], 'TRUSTED')
        self.assertEqual(projected.rows['task_details_revision']['release_original'], original)
        self.assertEqual(sql_value('release_at', original), datetime.fromisoformat(original))
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(sql_value('created_at', now), now)
        with self.assertRaisesRegex(TaskStorageError, 'TASK_STORAGE_EXPLICIT_TIME_REQUIRED'):
            sql_value('created_at', now.replace(tzinfo=None))


if __name__ == '__main__':
    unittest.main()
