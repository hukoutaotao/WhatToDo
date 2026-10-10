"""Cache/ref/default semantics share exact values across fake and PG adapters."""
from dataclasses import replace
from datetime import datetime,timezone
from hashlib import sha1,sha256
import json
import unittest

from src.adapters.clocks import FrozenClock
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.application.definitions import (DefinitionArtifact,DefinitionError,DefinitionKey,GitDefinitionRequest,canonical,defaults_from,resolve_task_definitions)


def artifact(kind,id,version,body):
    envelope=dict(kind=kind,id=id,version=version,body=body)
    raw=canonical(envelope).encode();oid=sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    return DefinitionArtifact(GitDefinitionRequest('a'*40,id+'.json',sha256(raw).hexdigest()),oid,raw)


class DefinitionTests(unittest.TestCase):
    def setUp(self):self.repo=MemoryDefinitionRepository(FrozenClock(datetime(2026,1,1,tzinfo=timezone.utc)))

    def test_same_envelope_as_runtime_config_and_detached_defaults(self):
        item=artifact('TASKTYPE','synthetic-work','1',dict(defaults=dict(importance=3,total_estimate_seconds=1800)))
        record,=self.repo.register_artifacts([item]);defaults=defaults_from(record)
        defaults.values['importance']=5;record.body['defaults']['importance']=1
        self.assertEqual(defaults.values['importance'],3);self.assertEqual(record.body['defaults']['importance'],3)
        self.assertNotIn('1800',repr(record));self.assertIn('NOT_CANONICAL_REMAINING',defaults.meaning)

    def test_new_version_does_not_change_existing_version_or_initial_snapshot(self):
        old,=self.repo.register_artifacts([artifact('TASKTYPE','synthetic-work','1',dict(defaults=dict(importance=3)))])
        values=defaults_from(old)
        self.repo.register_artifacts([artifact('TASKTYPE','synthetic-work','2',dict(defaults=dict(importance=5)))])
        self.assertEqual(values.values['importance'],3);self.assertEqual(self.repo.get(old.key),old)
        self.assertEqual(defaults_from(self.repo.get(DefinitionKey('TASKTYPE','synthetic-work','2'))).values['importance'],5)

    def test_replay_preserves_original_time_and_same_version_change_conflicts(self):
        item=artifact('PREFERENCE','synthetic-preference','1',dict(value='original'))
        first,=self.repo.register_artifacts([item]);self.assertEqual(self.repo.register_artifacts([item]),(first,))
        with self.assertRaises(DefinitionError):self.repo.register_artifacts([artifact('PREFERENCE','synthetic-preference','1',dict(value='changed'))])
        self.assertEqual(self.repo.get(item.key),first)

    def test_missing_profile_reference_rolls_back_whole_import(self):
        bad=artifact('TASKTYPE','synthetic-work','1',dict(references=[dict(kind='COURSE_PROFILE',id='missing',version='1')]))
        with self.assertRaises(DefinitionError) as caught:self.repo.register_artifacts([bad])
        self.assertEqual(str(caught.exception),'DEFINITION_UNRESOLVED_REFERENCE');self.assertIsNone(self.repo.get(bad.key))

    def test_same_bundle_references_resolve_independent_of_import_order(self):
        profile=artifact('COURSE_PROFILE','synthetic-course','1',dict(record_mode='SYNTHETIC'))
        item=artifact('TASKTYPE','synthetic-work','1',dict(references=[dict(kind='COURSE_PROFILE',id='synthetic-course',version='1')]))
        self.repo.register_artifacts([item,profile])
        records=resolve_task_definitions(self.repo,dict(task_type_ref=dict(id='synthetic-work',version='1'),context=dict(kind='COURSE',id='synthetic-course')),profile_key=profile.key)
        self.assertEqual(set(r.key for r in records),{item.key,profile.key})

    def test_task_profile_needs_exact_version_and_resolved_id(self):
        core=dict(task_type_ref=None,context=dict(kind='COURSE',id='synthetic-course'))
        for key in [None,DefinitionKey('COURSE_PROFILE','other','1'),DefinitionKey('COURSE_PROFILE','synthetic-course','missing')]:
            with self.assertRaises(DefinitionError):resolve_task_definitions(self.repo,core,profile_key=key)

    def test_reference_cycles_are_data_not_a_false_task_order_cycle(self):
        a=artifact('PREFERENCE','a','1',dict(references=[dict(kind='PREFERENCE',id='b',version='1')]))
        b=artifact('PREFERENCE','b','1',dict(references=[dict(kind='PREFERENCE',id='a',version='1')]))
        self.repo.register_artifacts([a,b]);self.assertEqual(self.repo.get(a.key).artifact.references,(b.key,))

    def test_invalid_defaults_never_become_user_remaining_or_guessed_values(self):
        for values in [dict(importance=True),dict(importance=6),dict(user_remaining_seconds=10),dict(minimum_session_seconds=0),dict(total_estimate_seconds=-1),dict(fragmentable='yes'),dict(difficulty=dict(thinking_depth=3))]:
            with self.assertRaises(DefinitionError):artifact('TASKTYPE','synthetic-work','1',dict(defaults=values))
        known=artifact('TASKTYPE','synthetic-work','1',dict(defaults=dict(total_estimate_seconds=0,minimum_session_seconds=None)))
        record,=self.repo.register_artifacts([known]);self.assertEqual(defaults_from(record).values,dict(total_estimate_seconds=0,minimum_session_seconds=None))

    def test_forged_blob_hash_missing_keys_and_duplicate_references_fail(self):
        valid=artifact('TASKTYPE','synthetic-work','1',{})
        with self.assertRaises(DefinitionError):replace(valid,blob_oid='b'*40)
        with self.assertRaises(DefinitionError):replace(valid,request=replace(valid.request,content_hash='b'*64))
        ref=dict(kind='COURSE_PROFILE',id='course',version='1')
        with self.assertRaises(DefinitionError):artifact('TASKTYPE','synthetic-work','1',dict(references=[ref,ref]))

    def test_git_request_is_an_exact_commit_and_safe_relative_path(self):
        for commit,path in [('HEAD','file.json'),('a'*40,'../secret'),('a'*40,'/secret'),('a'*40,'x\\secret'),('a'*40,'x/./file')]:
            with self.assertRaises(DefinitionError):GitDefinitionRequest(commit,path,'b'*64)


if __name__=='__main__':unittest.main()
