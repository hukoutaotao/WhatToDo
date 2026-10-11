from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.application.definitions import canonical
from src.application.task_resolution import (CourseLabel,ResolutionSnapshot,admit_intent,admit_reply,admit_frame,
    begin_resolution,resume_resolution,refresh_resolution,resolution_handoff,current_scope)
from src.application.task_storage import admit_storage
from src.application.transactions import TransactionError
from src.domain.authorization import CallerIdentity

ROOT=Path(__file__).resolve().parents[1];NOW=datetime(2026,1,1,tzinfo=timezone.utc);CALLER=CallerIdentity('principal','USER_COMMAND',True)


class TaskResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=ContractJSONCodec(load_supported_schemas(root=ROOT))
        cls.example=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases'][0]['payload']

    def record(self,task_id,title='作业',revision=1,course=None):
        v=deepcopy(self.example);v['core']['task_id']=v['effort']['task_id']=task_id
        v['core']['revision']=v['effort']['task_revision']=revision;v['core']['title']=title
        v['core']['context']=dict(kind='COURSE',id=course) if course else None
        return admit_storage(self.codec,canonical(v).encode())

    def snapshot(self,records=None,courses=None,epoch=1):
        return ResolutionSnapshot('principal',epoch,tuple(records or (self.record('a',course='course-a'),self.record('b',course='course-b'))),
            tuple(courses if courses is not None else (CourseLabel('course-a','基础物理学',('物理',)),CourseLabel('course-b','离散数学',('离散',)))))

    def intent(self,*,mode='NAME',value='作业',course=None,action='COMPLETE_TASK',fields=None,facts=None):
        v=dict(schema_version='0.1.0-resolution-intent',session_id='session',command_id='command',principal_id='principal',action=action,
            target=dict(mode=mode,value=value,course=course) if action!='CREATE_TASK' else None,creation_task_id='new-task' if action=='CREATE_TASK' else None,
            fields=fields or (dict(title='阅读论文') if action=='CREATE_TASK' else dict(disposition='CANCELLED') if action=='CANCEL_TASK' else dict(completion='COMPLETE')),
            creation_facts=facts or {})
        return admit_intent(self.codec,canonical(v).encode())

    def begin(self,intent=None,snapshot=None):
        return begin_resolution(self.codec,intent or self.intent(),snapshot or self.snapshot(),source_ref='initial-source',source_observed_at=NOW-timedelta(seconds=1),at=NOW,caller=CALLER)

    def reply(self,frame,selection=None,answers=None,**changes):
        v=dict(schema_version='0.1.0-clarification-reply',reply_id='reply',session_id=frame.session_id,expected_revision=frame.revision,
            scope_hash=frame.fingerprint,selection=selection,answers=answers or {});v.update(changes)
        return admit_reply(self.codec,canonical(v).encode())

    def resume(self,frame,reply,snapshot=None,**kw):
        options=dict(source_ref='reply-source',source_observed_at=NOW,at=NOW,caller=CALLER);options.update(kw)
        return resume_resolution(self.codec,frame,reply,snapshot or self.snapshot(),**options)

    def test_duplicate_exact_names_list_all_candidates_without_selecting_first(self):
        f=self.begin();v=f.as_record();self.assertEqual(v['state'],'NEEDS_TASK');self.assertEqual([x['id'] for x in v['choices']],['a','b'])
        self.assertIsNone(v['selected_task_ref']);self.assertEqual(v['choices'][1]['course_id'],'course-b')

    def test_single_exact_name_is_resolved_without_redundant_approval_question(self):
        f=self.begin(self.intent(value='证明题'),self.snapshot(records=(self.record('a','证明题'),)))
        self.assertEqual(f.as_record()['state'],'RESOLVED');self.assertEqual(f.as_record()['question'],'')
        out=resolution_handoff(f,authority_ref='independent-grant',caller=CALLER)
        self.assertEqual(out.command.command_id,'command');self.assertEqual(out.command.changes[0].task_id,'a')

    def test_stable_id_is_exact_and_never_interpreted_as_human_title_or_provider_id(self):
        snapshot=self.snapshot(records=(self.record('a','b'),self.record('b','实际标题')))
        self.assertEqual(self.begin(self.intent(mode='ID',value='b'),snapshot).as_record()['selected_task_ref']['task_id'],'b')
        self.assertEqual(self.begin(self.intent(mode='NAME',value='b'),snapshot).as_record()['selected_task_ref']['task_id'],'a')
        self.assertEqual(self.begin(self.intent(mode='ID',value='external-platform-id'),snapshot).as_record()['state'],'NEEDS_TASK')

    def test_similar_or_substring_names_are_suggestions_even_when_only_one(self):
        f=self.begin(self.intent(value='证明'),self.snapshot(records=(self.record('a','证明题'),)))
        self.assertEqual(f.as_record()['state'],'NEEDS_TASK');self.assertEqual(len(f.as_record()['choices']),1)

    def test_explicit_course_name_alias_and_stable_context_narrow_duplicate_task_names(self):
        for course in (dict(mode='NAME',value='物理'),dict(mode='ID',value='course-a')):
            with self.subTest(course=course):
                f=self.begin(self.intent(course=course));self.assertEqual(f.as_record()['selected_task_ref']['task_id'],'a')

    def test_duplicate_course_aliases_require_course_choice_before_task_resolution(self):
        snapshot=self.snapshot(courses=(CourseLabel('course-a','第一门',('数学',)),CourseLabel('course-b','第二门',('数学',))))
        f=self.begin(self.intent(course=dict(mode='NAME',value='数学')),snapshot)
        self.assertEqual(f.as_record()['state'],'NEEDS_COURSE');self.assertEqual(len(f.as_record()['choices']),2)
        out=self.resume(f,self.reply(f,'第二个'),snapshot)
        self.assertEqual(out.as_record()['state'],'RESOLVED');self.assertEqual(out.as_record()['selected_task_ref']['task_id'],'b')

    def test_confirmation_alone_cannot_select_multiple_candidates(self):
        f=self.begin();out=self.resume(f,self.reply(f,'确认'))
        self.assertEqual(out.as_record()['state'],'NEEDS_TASK');self.assertIsNone(out.as_record()['selected_task_ref']);self.assertEqual(out.revision,2)

    def test_choice_number_chinese_ordinal_and_listed_stable_id_bind_original_option(self):
        for choice in ('2','第二个','第2项','b'):
            with self.subTest(choice=choice):
                f=self.begin();out=self.resume(f,self.reply(f,choice));self.assertEqual(out.as_record()['selected_task_ref'],dict(task_id='b',revision=1))
                self.assertEqual(out.as_record()['command_id'],f.as_record()['command_id']);self.assertEqual(out.as_record()['previous_revision'],1)

    def test_old_hash_or_version_cannot_confirm_another_frame(self):
        f=self.begin()
        for change in (dict(scope_hash='0'*64),dict(expected_revision=2),dict(session_id='another')):
            with self.subTest(change=change),self.assertRaisesRegex(TransactionError,'REPLY_SCOPE_CONFLICT'):self.resume(f,self.reply(f,'2',**change))

    def test_changed_task_version_or_label_prevents_selection_even_same_number(self):
        f=self.begin()
        for changed in (self.record('b',revision=2,course='course-b'),self.record('b','另一个作业',course='course-b')):
            snapshot=self.snapshot(records=(self.record('a',course='course-a'),changed))
            with self.subTest(changed=changed),self.assertRaisesRegex(TransactionError,'TASK_SNAPSHOT_CHANGED'):self.resume(f,self.reply(f,'2'),snapshot)

    def test_registry_change_requires_new_question_version(self):
        f=self.begin();changed=self.snapshot(courses=(CourseLabel('course-a','物理新名称'),CourseLabel('course-b','离散数学')))
        with self.assertRaisesRegex(TransactionError,'COURSE_REGISTRY_CHANGED'):self.resume(f,self.reply(f,'2'),changed)
        newer=refresh_resolution(self.codec,f,changed,at=NOW,caller=CALLER)
        self.assertEqual(newer.revision,2);self.assertNotEqual(newer.fingerprint,f.fingerprint)

    def test_unrelated_new_task_does_not_reorder_original_choices_or_widen_selection(self):
        f=self.begin();snapshot=self.snapshot(records=(self.record('0',course='course-a'),self.record('a',course='course-a'),self.record('b',course='course-b')),epoch=2)
        out=self.resume(f,self.reply(f,'2'),snapshot);self.assertEqual(out.as_record()['selected_task_ref']['task_id'],'b')
        self.assertEqual(out.as_record()['store_revision'],2)

    def test_create_missing_fields_resume_same_command_and_preserve_initial_title(self):
        f=self.begin(self.intent(action='CREATE_TASK'));self.assertEqual(f.as_record()['state'],'NEEDS_DETAILS')
        out=self.resume(f,self.reply(f,answers=dict(importance='4',requiredness='必须完成',difficulty='3/2/3',domain='学习')))
        self.assertEqual(out.as_record()['state'],'RESOLVED');self.assertEqual(out.as_record()['fields']['title'],'阅读论文')
        h=resolution_handoff(out,authority_ref='independent-grant',caller=CALLER)
        self.assertEqual(h.command.command_id,'command');self.assertEqual(h.command.changes[0].task_id,'new-task')
        self.assertEqual(h.manual_intent.facts,dict(domain='study'));self.assertEqual(h.source_refs,('initial-source','reply-source'))

    def test_valid_partial_answers_survive_conflict_so_only_unresolved_field_is_asked_again(self):
        f=self.begin(self.intent(action='CREATE_TASK'))
        out=self.resume(f,self.reply(f,answers=dict(importance='6',requiredness='必须',difficulty='3/2/3',domain='学习')))
        self.assertEqual(out.as_record()['missing_fields'],['/core/importance']);self.assertEqual(out.as_record()['creation_facts']['domain'],'study')
        final=self.resume(out,self.reply(out,answers=dict(importance='4')))
        self.assertEqual(final.as_record()['state'],'RESOLVED');self.assertEqual(final.as_record()['fields']['requiredness'],'REQUIRED')

    def test_reply_cannot_overwrite_original_known_fields_or_smuggle_other_effects(self):
        f=self.begin(self.intent(action='CREATE_TASK'))
        with self.assertRaisesRegex(TransactionError,'ANSWER_FIELD_SCOPE'):self.resume(f,self.reply(f,answers=dict(title='替换原标题')))
        f=self.begin()
        with self.assertRaisesRegex(TransactionError,'ANSWER_FIELD_SCOPE'):self.resume(f,self.reply(f,'2',answers=dict(importance='4')))

    def test_incomplete_unknown_answer_keeps_unknown_without_zero_or_default(self):
        f=self.begin(self.intent(action='CREATE_TASK'));out=self.resume(f,self.reply(f,answers=dict(importance='不知道')))
        self.assertEqual(out.as_record()['state'],'NEEDS_DETAILS');self.assertNotIn('importance',out.as_record()['fields'])
        self.assertNotIn('user_remaining_seconds',out.as_record()['fields'])

    def test_other_principal_external_and_unauthenticated_replies_cannot_take_ownership(self):
        f=self.begin()
        for caller in (CallerIdentity('other','USER_COMMAND',True),CallerIdentity('principal','EXTERNAL',True),CallerIdentity('principal','USER_COMMAND',False)):
            with self.subTest(caller=caller),self.assertRaisesRegex(TransactionError,'AUTHENTICATED_OWNER'):self.resume(f,self.reply(f,'2'),caller=caller)

    def test_reply_capture_before_question_or_future_is_rejected(self):
        f=self.begin()
        for timestamp in (NOW-timedelta(seconds=1),NOW+timedelta(seconds=1)):
            with self.subTest(timestamp=timestamp),self.assertRaisesRegex(TransactionError,'REPLY_TIME_REQUIRED'):self.resume(f,self.reply(f,'2'),source_observed_at=timestamp)

    def test_resolved_frame_cannot_be_answered_again_or_refreshed(self):
        f=self.resume(self.begin(),self.reply(self.begin(),'2'))
        with self.assertRaisesRegex(TransactionError,'ALREADY_RESOLVED'):self.resume(f,self.reply(f,'1'))
        with self.assertRaisesRegex(TransactionError,'ALREADY_RESOLVED'):refresh_resolution(self.codec,f,self.snapshot(),at=NOW,caller=CALLER)

    def test_unknown_raw_fields_extra_actions_and_outcomes_are_rejected(self):
        v=self.intent().as_record();v['approval']=True
        with self.assertRaisesRegex(TransactionError,'SHAPE_UNSUPPORTED'):admit_intent(self.codec,canonical(v).encode())
        with self.assertRaises(TransactionError):self.intent(action='CANCEL_TASK',fields=dict(disposition='CANCELLED',importance=4))
        with self.assertRaises(TransactionError):self.intent(action='CREATE_TASK',fields=dict(title='新任务',completion='COMPLETE'))
        with self.assertRaises(TransactionError):self.intent(action='CREATE_TASK',fields=dict(title='新任务',requiredness='EXPIRING'))

    def test_fingerprint_and_frame_bytes_detect_changed_context(self):
        f=self.begin();v=f.as_record();v['question']='different'
        with self.assertRaisesRegex(TransactionError,'BYTES_DRIFT'):replace(f,payload_json=canonical(v))
        changed=admit_frame(self.codec,canonical(v).encode());self.assertNotEqual(changed.fingerprint,f.fingerprint)
        data=f.as_record();data['choices'].clear();self.assertEqual(len(f.as_record()['choices']),2)

    def test_cancel_handoff_preserves_separate_action_and_does_not_infer_completion(self):
        f=self.begin(self.intent(action='CANCEL_TASK',mode='ID',value='a'))
        h=resolution_handoff(f,authority_ref='root',caller=CALLER)
        self.assertEqual(h.command.changes[0].fields,dict(disposition='CANCELLED'));self.assertIsNone(h.manual_intent)


if __name__=='__main__':unittest.main()
