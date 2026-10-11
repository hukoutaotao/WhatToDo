from dataclasses import replace
from datetime import datetime,timedelta,timezone
import unittest

from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.application.direct_creation import DirectCreationNormalizer,UserInputBinding,guided_message
from src.application.evidence_storage import SourceScope,admit_candidate
from src.application.manual_tasks import prepare_manual_task
from src.application.transactions import TransactionError
from src.domain.authorization import CallerIdentity
from src.domain.provenance import capture_source
from tools.check_contract_registry import trusted_schemas

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CALLER=CallerIdentity('principal','USER_COMMAND',True)
SCOPE=SourceScope('synthetic-input','scope','account')


class DirectCreationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.codec=ContractJSONCodec(trusted_schemas())

    def setUp(self):
        self.clock=FrozenClock(NOW)
        self.parser=DirectCreationNormalizer(self.codec,clock=self.clock,bindings=(UserInputBinding(CALLER.principal_id,SCOPE),))

    def source(self,raw,**kwargs):
        options=dict(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id='message',raw_bytes=raw,captured_at=NOW-timedelta(seconds=1),source_type='USER')
        options.update(kwargs);return capture_source(**options)

    def natural(self,text,**kwargs):
        raw=text.encode();return self.parser.natural(raw,self.source(raw),caller=CALLER,**kwargs)

    def guided(self,**answers):
        raw=guided_message(answers);return self.parser.guided(raw,self.source(raw),caller=CALLER)

    def handoff(self,p,**kwargs):
        options=dict(command_id='command',task_id='task',authority_ref='independent-grant',caller=CALLER);options.update(kwargs)
        return self.parser.manual_handoff(p,**options)

    def test_clear_chinese_creation_with_explicit_fields_matches_frozen_proposal(self):
        p=self.natural('帮我新增一个任务：阅读论文，必须完成，重要性4，难度3/2/3，剩余约40分钟，领域学习')
        self.assertTrue(p.ready_for_creation);c=admit_candidate(self.codec,p.candidate_json.encode(),pending_only=True).candidate
        self.assertEqual(c.action,'CREATE_TASK');self.assertIsNone(c.target_task_id);self.assertIsNone(c.authority_ref)
        self.assertEqual(c.proposed_fields['remaining_seconds'],2400);self.assertEqual(c.proposed_fields['difficulty']['new_learning_load'],3)
        self.assertEqual(p.facts,dict(domain='study'))

    def test_supported_creation_prefixes_are_anchored_and_obvious_title_is_retained(self):
        for prefix in ('新增任务：','创建任务 ','添加一个任务：','请帮我新建任务：','加个任务：','记一个任务：'):
            with self.subTest(prefix=prefix):
                p=self.natural(prefix+'读论文');self.assertTrue(p.normalized);self.assertEqual(p.candidate['proposed_fields']['title'],'读论文')

    def test_negated_conditional_quoted_external_and_other_actions_are_unresolved(self):
        for text in ('不要新增任务：读论文','如果有时间就新增任务：读论文','老师说“新增任务：读论文”','能不能新增任务：读论文？','完成任务：读论文','取消读论文'):
            with self.subTest(text=text):
                p=self.natural(text);self.assertFalse(p.normalized);self.assertIsNone(p.candidate)
                with self.assertRaisesRegex(TransactionError,'CLARIFICATION_REQUIRED'):self.handoff(p)

    def test_simple_title_is_normalized_but_missing_essential_facts_are_not_defaults(self):
        p=self.natural('新增任务：读论文');self.assertTrue(p.normalized);self.assertFalse(p.ready_for_creation)
        self.assertEqual(p.candidate['proposed_fields'],dict(title='读论文'));self.assertEqual(p.facts,{})
        self.assertEqual(set(p.missing_fields),{'/core/domain','/core/difficulty','/core/importance','/core/requiredness'})
        h=self.handoff(p);draft=prepare_manual_task(self.codec,h.command,h.intent,MemoryDefinitionRepository(self.clock))
        self.assertFalse(draft.ready);self.assertIsNone(draft.after);self.assertEqual(set(draft.missing_fields),set(p.missing_fields))

    def test_complete_handoff_creates_same_manual_draft_without_second_confirmation(self):
        p=self.natural('新增任务：读论文，可选，重要性3，难度223，剩余0秒，领域学习');h=self.handoff(p)
        draft=prepare_manual_task(self.codec,h.command,h.intent,MemoryDefinitionRepository(self.clock))
        self.assertTrue(draft.ready);self.assertEqual(draft.after.aggregate.as_record()['effort']['user_remaining']['seconds'],0)
        self.assertEqual(draft.after.aggregate.as_record()['core']['completion'],'INCOMPLETE')
        self.assertIsNone(draft.after.aggregate.as_record()['timing']['created_at']);self.assertIsNone(draft.after.aggregate.as_record()['work']['total_estimate'])
        self.assertEqual(h.intent.source_ref,p.source.record_id);self.assertEqual(h.statement_bytes,p.statement_bytes)

    def test_guided_fields_are_text_answers_and_preserve_exact_raw_content(self):
        p=self.guided(title='  阅读论文  ',importance='4',requiredness='必须',difficulty='3／2／3',remaining='约1.5小时',domain='学习')
        self.assertTrue(p.ready_for_creation);self.assertEqual(p.candidate['proposed_fields']['remaining_seconds'],5400)
        self.assertIn('  阅读论文  ',p.statement_bytes.decode());self.assertEqual(p.candidate['proposed_fields']['title'],'阅读论文')
        self.assertNotIn('阅读论文',repr(p))

    def test_partial_or_unknown_guided_answers_do_not_reuse_displayed_or_invented_values(self):
        p=self.guided(title='读论文',importance='',requiredness='不确定',difficulty='跳过',remaining='不知道',domain='')
        self.assertTrue(p.normalized);self.assertEqual(p.candidate['proposed_fields'],dict(title='读论文'))
        self.assertFalse(p.ready_for_creation);h=self.handoff(p)
        self.assertIsNone(h.command.changes[0].fields['user_remaining_seconds']);self.assertNotIn('importance',h.command.changes[0].fields)

    def test_single_integral_duration_is_independent_from_original_total_estimate(self):
        for text,seconds in (('0分钟',0),('约40分钟',2400),('1.5小时',5400),('0.1分钟',6)):
            with self.subTest(text=text):
                p=self.guided(title='读论文',remaining=text);self.assertEqual(p.candidate['proposed_fields']['remaining_seconds'],seconds)
                self.assertNotIn('total_estimate_seconds',p.facts)

    def test_ranges_unitless_composite_negative_fractional_seconds_need_clarification(self):
        for value in ('20~30分钟','20分钟或40分钟','40','-1分钟','0.1秒','1小时30分钟','差不多吧'):
            with self.subTest(value=value):
                p=self.guided(title='读论文',remaining=value);self.assertFalse(p.normalized)
                self.assertNotIn('remaining_seconds',p.candidate['proposed_fields'])

    def test_duplicate_fields_conflicting_or_identical_never_get_last_value_precedence(self):
        for suffix in ('重要性3，重要性4','重要性3，重要性3','领域学习，领域其他'):
            with self.subTest(suffix=suffix):
                p=self.natural('新增任务：读论文，'+suffix);self.assertFalse(p.normalized)
                self.assertIn('DUPLICATE_FIELD',[i.code for i in p.issues])

    def test_invalid_ratings_partial_difficulty_and_expiring_requirement_are_unresolved(self):
        for answers in (dict(importance='6'),dict(importance='3.0'),dict(difficulty='3/2'),dict(difficulty='3/2/6'),dict(requiredness='会失效')):
            with self.subTest(answers=answers):self.assertFalse(self.guided(title='读论文',**answers).normalized)

    def test_unknown_fields_and_explicit_date_requests_are_not_silently_ignored(self):
        for text in ('新增任务：读论文，截止明天','新增任务：读论文，principal_id=other','新增任务：明天读论文','新增任务：读论文然后取消其他任务'):
            with self.subTest(text=text):
                p=self.natural(text);self.assertFalse(p.normalized)
                with self.assertRaisesRegex(TransactionError,'CLARIFICATION_REQUIRED'):self.handoff(p)
        self.assertFalse(self.guided(title='读论文',authority_ref='fake-grant').normalized)

    def test_quoted_title_retains_literal_commas_and_words_that_are_not_instructions(self):
        p=self.natural('新增任务：“读论文，并修改笔记”，重要性4')
        self.assertTrue(p.normalized);self.assertEqual(p.candidate['proposed_fields']['title'],'读论文，并修改笔记')
        self.assertEqual(p.candidate['action'],'CREATE_TASK');self.assertIsNone(p.candidate['target_ref'])

    def test_ambiguous_reference_question_unclosed_quote_and_trailing_text_stay_pending(self):
        for text in ('新增任务：那个作业','新增任务：读论文？','新增任务：“读论文','新增任务：“读论文”然后取消任务'):
            with self.subTest(text=text):self.assertFalse(self.natural(text).normalized)

    def test_controls_long_empty_titles_and_nontext_guided_fields_rejected(self):
        for value in ('','  ','x'*501,'读\x00论文','读\x1b论文'):
            with self.subTest(value=value):self.assertFalse(self.guided(title=value).normalized)
        with self.assertRaisesRegex(TransactionError,'TEXT_FIELDS'):guided_message(dict(title='读论文',importance=True))

    def test_external_unauthenticated_and_unbound_principals_cannot_be_direct_users(self):
        raw='新增任务：读论文'.encode();source=self.source(raw)
        for caller,code in ((CallerIdentity('principal','EXTERNAL',True),'AUTHENTICATED_USER'),(CallerIdentity('principal','USER_COMMAND',False),'AUTHENTICATED_USER'),
                (CallerIdentity('other','USER_COMMAND',True),'ACCOUNT_SCOPE')):
            with self.subTest(caller=caller),self.assertRaisesRegex(TransactionError,code):self.parser.natural(raw,source,caller=caller)

    def test_user_tag_without_trusted_source_binding_or_exact_bytes_is_insufficient(self):
        raw='新增任务：读论文'.encode()
        for source,code in ((self.source(raw,source_type='EMAIL'),'PRESENT_USER_SOURCE'),(self.source(raw,scope_ref='other'),'ACCOUNT_SCOPE'),
                (self.source(b'other message'),'EXACT_STATEMENT'),(self.source(raw,captured_at=NOW+timedelta(seconds=1)),'FUTURE_SOURCE')):
            with self.subTest(code=code),self.assertRaisesRegex(TransactionError,code):self.parser.natural(raw,source,caller=CALLER)

    def test_guided_duplicate_json_keys_and_serialized_caller_fields_fail_closed(self):
        for raw in (b'{"input_kind":"CREATE_TASK_GUIDED","answers":{"title":"one","title":"two"}}',
            b'{"input_kind":"CREATE_TASK_GUIDED","answers":{"title":"one"},"principal_id":"principal"}'):
            with self.subTest(raw=raw),self.assertRaisesRegex(TransactionError,'ENVELOPE_INVALID'):self.parser.guided(raw,self.source(raw),caller=CALLER)

    def test_input_size_and_utf8_fail_before_any_candidate_is_published(self):
        for raw,code in ((b'x'*8193,'SIZE_LIMIT'),(b'\xff','UTF8_REQUIRED')):
            with self.subTest(code=code),self.assertRaisesRegex(TransactionError,code):self.parser.natural(raw,self.source(raw),caller=CALLER)

    def test_handoff_reparses_raw_statement_and_rejects_forged_fields_or_changed_principal(self):
        p=self.natural('新增任务：读论文')
        with self.assertRaisesRegex(TransactionError,'PROPOSAL_DRIFT'):self.handoff(replace(p,facts_json='{"domain":"study"}'))
        with self.assertRaisesRegex(TransactionError,'PROPOSAL_OWNER'):self.handoff(p,caller=CallerIdentity('other','USER_COMMAND',True))
        with self.assertRaisesRegex(TransactionError,'AUTHENTICATED_USER'):self.handoff(p,caller=CallerIdentity('principal','USER_COMMAND',False))

    def test_command_ids_are_separate_from_human_title_and_candidate_is_never_confirmed_by_parser(self):
        p=self.natural('新增任务：读论文');one=self.handoff(p,task_id='task-one');two=self.handoff(p,task_id='task-two')
        self.assertNotEqual(one.command.changes[0].task_id,two.command.changes[0].task_id)
        self.assertEqual(one.command.changes[0].fields,two.command.changes[0].fields)
        self.assertEqual(p.candidate['review']['state'],'PENDING');self.assertIsNone(p.candidate['review']['authority_ref'])


if __name__=='__main__':unittest.main()
