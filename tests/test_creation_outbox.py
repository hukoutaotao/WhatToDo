"""Canonical event identity/provenance, lease fencing values and closed results."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import unittest

from src.application.creation_outbox import (CreationEvent,DeliveryLease,DeliveryOutcome,
    OutboxError,event_id_for,lease_duration)

NOW=datetime(2026,1,1,tzinfo=timezone.utc)


def event(task_id='synthetic-source',revision=1):
    return CreationEvent(event_id_for(task_id),task_id,revision,'a'*64,'synthetic-create','principal','authority',NOW)


class CreationOutboxTests(unittest.TestCase):
    def test_event_hash_handles_unicode_and_long_accepted_reference(self):
        for id in ('课程／任务','x'*1000):
            value=event(id);self.assertEqual(len(value.event_id),73)
            self.assertEqual(value.event_id,event_id_for(id))

    def test_creation_identity_is_exact_and_changes_with_source(self):
        self.assertNotEqual(event_id_for('a'),event_id_for('A'))
        with self.assertRaises(OutboxError):replace(event(),event_id=event_id_for('another'))

    def test_first_snapshot_revision_need_not_be_one(self):
        self.assertEqual(event(revision=7).task_revision,7)

    def test_source_pins_reject_invalid_hash_or_provenance(self):
        for fields in (dict(content_hash='A'*64),dict(content_hash='x'),dict(creation_transaction_ref=''),dict(task_revision=True),dict(task_revision=0)):
            with self.subTest(fields=fields),self.assertRaises(OutboxError):replace(event(),**fields)

    def test_naive_source_and_lease_times_are_rejected(self):
        with self.assertRaises(OutboxError):replace(event(),occurred_at=datetime(2026,1,1))

    def test_source_offset_is_normalized_without_changing_instant(self):
        local=NOW.astimezone(timezone(timedelta(hours=8)))
        self.assertEqual(replace(event(),occurred_at=local).occurred_at,NOW)

    def test_lease_requires_fenced_attempt_revision_and_token(self):
        lease=DeliveryLease(event(),2,1,'worker','f'*32,NOW,NOW+timedelta(seconds=60))
        for fields in (dict(attempt=0),dict(revision=1),dict(token='guess'),dict(worker_id=''),dict(attempt=True)):
            with self.subTest(fields=fields),self.assertRaises(OutboxError):replace(lease,**fields)
        self.assertNotIn(lease.token,repr(lease))

    def test_lease_cannot_precede_event_or_have_unbounded_duration(self):
        good=DeliveryLease(event(),2,1,'worker','f'*32,NOW,NOW+timedelta(seconds=60))
        for fields in (dict(changed_at=NOW-timedelta(seconds=1)),dict(expires_at=NOW),dict(expires_at=NOW+timedelta(seconds=3601))):
            with self.subTest(fields=fields),self.assertRaises(OutboxError):replace(good,**fields)

    def test_ttl_boundary_rejects_boolean_zero_negative_and_over_hour(self):
        self.assertEqual(lease_duration(3600),3600)
        for n in (True,0,-1,3601):
            with self.subTest(n=n),self.assertRaises(OutboxError):lease_duration(n)

    def test_done_and_waiting_preserve_opaque_result_without_task_completion(self):
        for kind in ('DONE','WAITING_FACTS'):
            value=DeliveryOutcome(kind,'synthetic-result');self.assertEqual(DeliveryOutcome.from_payload(value.payload),value)
            with self.assertRaises(OutboxError):DeliveryOutcome(kind)

    def test_retry_preserves_explicit_aware_time_and_closed_reason(self):
        value=DeliveryOutcome('RETRY',code='TEMPORARY_UNAVAILABLE',retry_at=NOW+timedelta(seconds=1))
        self.assertEqual(DeliveryOutcome.from_payload(value.payload),value)
        with self.assertRaises(OutboxError):DeliveryOutcome('RETRY',code='TEMPORARY_UNAVAILABLE')

    def test_failure_cannot_store_raw_exception_or_private_text(self):
        self.assertEqual(DeliveryOutcome('FAILED',code='MAPPING_CONFLICT').code,'MAPPING_CONFLICT')
        for code in ('exception with raw content','lowercase','A'*65):
            with self.subTest(code=code),self.assertRaises(OutboxError):DeliveryOutcome('FAILED',code=code)

    def test_outcome_shape_rejects_extra_fields_and_unknown_state(self):
        value=DeliveryOutcome('DONE','result').payload
        with self.assertRaises(OutboxError):DeliveryOutcome.from_payload(dict(value,extra='field'))
        with self.assertRaises(OutboxError):DeliveryOutcome('COMPLETE_TASK','result')

    def test_done_cannot_smuggle_failure_or_retry_fields(self):
        with self.assertRaises(OutboxError):DeliveryOutcome('DONE','result',code='FAILED')
        with self.assertRaises(OutboxError):DeliveryOutcome('FAILED',code='FAILED',retry_at=NOW)


if __name__=='__main__':unittest.main()
