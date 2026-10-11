from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.application.command_validation import admit_command,validate_effects
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext
from src.application.task_storage import admit_storage
from src.application.transactions import TransactionError
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from tools.check_contract_registry import trusted_schemas

ROOT=Path(__file__).resolve().parents[1];NOW=datetime(2026,1,1,tzinfo=timezone.utc)
CALLER=CallerIdentity('user','USER_COMMAND',True)


class CommandValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=ContractJSONCodec(trusted_schemas())
        cls.base=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases'][0]['payload']

    def setup_values(self,fields=None,*,action='UPDATE_TASK'):
        before=deepcopy(self.base);before['core']['task_id']=before['effort']['task_id']='task'
        before['core']['acceptance']['authority_ref']='grant';before['effort']['user_remaining']=None
        command=Command('command','user','USER_COMMAND','grant',
            (change('task',None if action=='CREATE_TASK' else 1,action,fields or {'title':'Edited'}),))
        grant=AuthorityGrant('grant','user','USER_COMMAND','command',command.changes,'statement',
            NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1))
        after=deepcopy(before);after['core']['title']='Edited'
        if action!='CREATE_TASK':after['core']['revision']=after['effort']['task_revision']=2
        request=CommitRequest(RequestContext('command','correlation'),'user',1,
            (RecordWrite(AggregateKey('TASK','task'),None if action=='CREATE_TASK' else 1,json.dumps(after)),),
            'audit','statement')
        return command,grant,before,after,request

    def validate(self,command,grant,before,after,request,**kw):
        options=dict(caller=CALLER,grant=grant,records=(admit_storage(self.codec,json.dumps(before).encode()),),now=NOW)
        options.update(kw)
        return validate_effects(self.codec,admit_command(self.codec,json.dumps(command.as_record()).encode()),request,**options)

    def test_explicit_title_change_mints_exact_permit_without_an_approval_step(self):
        v=self.setup_values();out=self.validate(*v)
        self.assertEqual(out.permit.request_fingerprint,v[-1].fingerprint)
        self.assertEqual(out.context['command_fingerprint'],v[0].fingerprint)
        self.assertLessEqual(out.permit.expires_at,NOW+timedelta(minutes=5))
        self.assertNotIn('Edited',repr(out))

    def test_issued_context_and_input_facts_are_detached(self):
        v=self.setup_values();original=deepcopy(v[2]);out=self.validate(*v)
        x=out.context;x['grant_ref']='forged'
        self.assertEqual(out.context['grant_ref'],'grant');self.assertEqual(v[2],original)

    def test_forged_approval_reference_and_extra_declared_fields_are_denied(self):
        c,g,b,a,r=self.setup_values()
        for c in (replace(c,authority_ref='claimed-approval'),replace(c,changes=(change('task',1,'UPDATE_TASK',{'title':'Edited','importance':5}),))):
            with self.assertRaisesRegex(TransactionError,'UNREGISTERED_AUTHORITY|EXACT_CHANGE_SCOPE_MISMATCH'):
                self.validate(c,g,b,a,r)

    def test_unknown_and_stale_targets_cannot_mint_write_permits(self):
        v=self.setup_values()
        with self.assertRaisesRegex(TransactionError,'UNKNOWN_TARGET'):self.validate(*v,records=())
        newer=deepcopy(v[2]);newer['core']['revision']=newer['effort']['task_revision']=2
        with self.assertRaisesRegex(TransactionError,'STALE_STATE_VERSION'):
            self.validate(*v,records=(admit_storage(self.codec,json.dumps(newer).encode()),))

    def test_full_aggregate_cannot_smuggle_unrequested_importance_context_or_work(self):
        c,g,b,a,r=self.setup_values()
        variants=[]
        x=deepcopy(a);x['core']['importance']=5;variants.append(x)
        x=deepcopy(a);x['work']['minimum_session_seconds']=1200;variants.append(x)
        x=deepcopy(a);x['core']['metadata']['trust']='CONFLICTED';variants.append(x)
        for after in variants:
            req=replace(r,writes=(replace(r.writes[0],body_json=json.dumps(after)),))
            with self.assertRaisesRegex(TransactionError,'COMMAND_UNAUTHORIZED_EFFECT'):self.validate(c,g,b,after,req)

    def test_unrequested_provenance_is_not_a_side_channel_for_scope_changes(self):
        c,g,b,a,r=self.setup_values();a['provenance']=[dict(field='/core/importance',source_ref='statement')]
        req=replace(r,writes=(replace(r.writes[0],body_json=json.dumps(a)),))
        with self.assertRaisesRegex(TransactionError,'COMMAND_UNAUTHORIZED_PROVENANCE'):self.validate(c,g,b,a,req)

    def test_declared_field_provenance_must_name_the_actual_statement(self):
        c,g,b,a,r=self.setup_values();a['provenance']=[dict(field='/core/title',source_ref='statement')]
        req=replace(r,writes=(replace(r.writes[0],body_json=json.dumps(a)),))
        self.validate(c,g,b,a,req)
        a['provenance'][0]['source_ref']='unrelated'
        req=replace(r,writes=(replace(r.writes[0],body_json=json.dumps(a)),))
        with self.assertRaisesRegex(TransactionError,'COMMAND_UNAUTHORIZED_PROVENANCE'):self.validate(c,g,b,a,req)

    def test_creation_requires_a_trusted_seed_and_cannot_inherit_completed_outcome(self):
        c,g,b,a,r=self.setup_values(action='CREATE_TASK')
        with self.assertRaisesRegex(TransactionError,'COMMAND_TRUSTED_CREATION_SEED_REQUIRED'):
            self.validate(c,g,b,a,r,records=())
        seed=admit_storage(self.codec,json.dumps(b).encode());self.validate(c,g,b,a,r,records=(),seeds=(seed,))
        completed=deepcopy(b);completed['core']['completion']=completed['effort']['completion']='COMPLETE'
        completed['effort']['user_remaining']=dict(seconds=0,observation_id='zero',observed_at=NOW.isoformat(),verified_at=NOW.isoformat())
        completed=admit_storage(self.codec,json.dumps(completed).encode())
        with self.assertRaisesRegex(TransactionError,'COMMAND_CREATION_SEED_CANNOT_ASSERT_OUTCOME'):
            self.validate(c,g,b,a,r,records=(),seeds=(completed,))

    def test_remain_estimate_requires_an_independent_exact_user_observation(self):
        c,g,b,a,r=self.setup_values({'title':'Edited','user_remaining_seconds':900})
        a['effort']['user_remaining']=dict(seconds=900,observation_id='u',observed_at=NOW.isoformat(),verified_at=NOW.isoformat())
        req=replace(r,writes=(replace(r.writes[0],body_json=json.dumps(a)),))
        with self.assertRaisesRegex(TransactionError,'COMMAND_UNRESOLVED_EFFORT_FACT'):self.validate(c,g,b,a,req)
        obs=('u','task','USER_REMAINING',900,NOW,'statement','grant')
        self.validate(c,g,b,a,req,observations=(obs,))
        with self.assertRaisesRegex(TransactionError,'COMMAND_UNRESOLVED_EFFORT_FACT'):
            self.validate(c,g,b,a,req,observations=(obs[:-1]+('other-grant',),))

    def test_command_schema_rejects_duplicate_fields_versions_and_approval_flags(self):
        c,*_=self.setup_values();raw=json.dumps(c.as_record()).encode()
        variants=[raw.replace(b'"0.1.0-draft"',b'"future"',1),raw.replace(b'"principal_id": "user"',b'"principal_id":"user","principal_id":"other"'),
            json.dumps(dict(c.as_record(),approved=True)).encode(),b'{invalid}']
        for raw in variants:
            with self.assertRaisesRegex(TransactionError,'COMMAND_SHAPE_UNSUPPORTED'):admit_command(self.codec,raw)

    def test_exact_request_id_source_and_target_set_are_bound_to_the_command(self):
        c,g,b,a,r=self.setup_values()
        for req in (replace(r,source_ref='other-source'),replace(r,context=RequestContext('another','correlation')),
                replace(r,writes=(replace(r.writes[0],key=AggregateKey('TASK','other')),))):
            with self.assertRaisesRegex(TransactionError,'COMMAND_REQUEST_BINDING_MISMATCH|COMMAND_EFFECT_TARGET_MISMATCH'):
                self.validate(c,g,b,a,req)


if __name__=='__main__':unittest.main()
