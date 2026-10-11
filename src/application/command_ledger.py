"""Detached receipt and audit consistency checks; receipts confer no authority."""
import json
import re

from src.application.ports import (AggregateKey,CommitReceipt,CommitRequest,
    RecordWrite,RequestContext)
from src.application.transactions import require
from src.domain.authorization import CallerIdentity


def validate_caller(caller, *, principal_id=None):
    require(isinstance(caller,CallerIdentity) and caller.authenticated and
        caller.origin!='EXTERNAL' and
        (principal_id is None or caller.principal_id==principal_id),'UNTRUSTED_CALLER')


def receipt_from_row(body, *, request_id, request_hash, store_revision, audit_id):
    code='COMMAND_RECEIPT_INVALID'
    require(isinstance(body,dict) and set(body)=={'request_id','request_fingerprint',
        'store_revision','audit_id','changed_keys'},code)
    require(type(body['store_revision']) is int and body['store_revision']>1 and
        (body['request_id'],body['request_fingerprint'],body['store_revision'],body['audit_id'])==
        (request_id,request_hash,store_revision,audit_id),code)
    require(isinstance(request_hash,str) and re.fullmatch('[a-f0-9]{64}',request_hash),code)
    require(isinstance(body['changed_keys'],list) and 1<=len(body['changed_keys'])<=100,code)
    keys=[]
    for item in body['changed_keys']:
        require(isinstance(item,dict) and set(item)=={'kind','id'} and
            all(isinstance(v,str) and v.strip() for v in item.values()),code)
        keys.append(AggregateKey(**item))
    require(len(set(keys))==len(keys),code)
    return CommitReceipt(request_id,request_hash,store_revision,audit_id,tuple(keys))


def validate_audit_fingerprint(receipt, *, principal_id, expected_store_revision,
                               source_ref, correlation_ref, changes):
    code='COMMAND_RECEIPT_INVALID'
    require(type(expected_store_revision) is int and expected_store_revision>0 and
        receipt.store_revision==expected_store_revision+1 and
        isinstance(changes,tuple) and len(changes)==len(receipt.changed_keys) and
        all(isinstance(c,tuple) and len(c)==6 for c in changes),code)
    writes=[]
    for kind,item_id,before_revision,after_revision,before_value,after_value in changes:
        require(type(after_revision) is int and after_revision>0 and
            (before_revision is None or (type(before_revision) is int and before_revision>0)) and
            after_revision==(before_revision or 0)+1 and
            (before_value is None)==(before_revision is None) and
            (before_value is None or isinstance(before_value,dict)) and isinstance(after_value,dict),code)
        writes.append(RecordWrite(AggregateKey(kind,item_id),before_revision,
            json.dumps(after_value,allow_nan=False)))
    require(len({w.key for w in writes})==len(writes) and
        {w.key for w in writes}==set(receipt.changed_keys),code)
    rebuilt=CommitRequest(RequestContext(receipt.request_id,correlation_ref),principal_id,
        expected_store_revision,tuple(writes),receipt.audit_id,source_ref)
    require(rebuilt.fingerprint==receipt.request_fingerprint,code)
