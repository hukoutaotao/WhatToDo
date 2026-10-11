"""Scope-bound evidence ingestion; never mutates canonical Tasks or authority."""
from dataclasses import dataclass, field
from hashlib import sha256

from src.adapters.postgres_migrations import LOCK_KEY, _owner, schema_checked_transaction
from src.application.evidence_storage import (SourceScope, EvidenceError, EvidenceObservation,
    admit_source, admit_candidate, canonical, pending_id, conflict_id, identity, require)
from src.domain.provenance import mark_source_deleted

EVIDENCE_LOCK = LOCK_KEY+2


@dataclass(frozen=True)
class RawContent:
    record_id: str
    content_hash: str
    locator_ref: str
    storage_state: str
    raw_bytes: bytes | None = field(repr=False)
    minimized_at: object = None
    reason_ref: str | None = None


def register_source_scope(connection, plan, roles, scope, *, application_version, clock):
    """Trusted configuration registration, using the migration role only."""
    require(isinstance(scope,SourceScope),'EVIDENCE_SCOPE')
    with schema_checked_transaction(connection,plan,application_version=application_version,read_only=False):
        _owner(connection,roles)
        require(connection.execute('SELECT pg_try_advisory_xact_lock(%s)',(EVIDENCE_LOCK,)).fetchone()[0],
            'EVIDENCE_IMPORT_BUSY')
        previous=connection.execute('SELECT account_ref FROM whattodo.source_scope WHERE provider=%s AND scope_ref=%s',
            (scope.provider,scope.scope_ref)).fetchone()
        if previous is None:
            connection.execute('INSERT INTO whattodo.source_scope VALUES(%s,%s,%s,%s)',
                (scope.provider,scope.scope_ref,scope.account_ref,clock.now()))
        else: require(previous==(scope.account_ref,),'EVIDENCE_SCOPE_IDENTITY_CONFLICT')


class PostgresEvidenceRepository:
    def __init__(self,connection,codec,plan,*,application_version,clock,scopes=()):
        require(isinstance(scopes,tuple) and len(scopes)<=1000 and
            all(isinstance(s,SourceScope) for s in scopes) and
            len({(s.provider,s.scope_ref) for s in scopes})==len(scopes),
            'EVIDENCE_TRUSTED_SCOPE_REGISTRY')
        self.connection=connection; self.codec=codec; self.plan=plan
        self.application_version=application_version; self.clock=clock; self.scopes=scopes

    def _transaction(self,*,write=False):
        return schema_checked_transaction(self.connection,self.plan,
            application_version=self.application_version,read_only=not write)

    def _lock(self):
        require(self.connection.execute('SELECT pg_try_advisory_xact_lock(%s)',(EVIDENCE_LOCK,)).fetchone()[0],
            'EVIDENCE_IMPORT_BUSY')

    def _scope(self,provider,scope_ref):
        scope=next((s for s in self.scopes if (s.provider,s.scope_ref)==(provider,scope_ref)),None)
        require(scope is not None,'EVIDENCE_SOURCE_SCOPE_NOT_AUTHORIZED')
        require(self.connection.execute('SELECT account_ref FROM whattodo.source_scope WHERE provider=%s AND scope_ref=%s',
            (provider,scope_ref)).fetchone()==(scope.account_ref,),'EVIDENCE_SOURCE_SCOPE_NOT_REGISTERED')

    def _insert(self,table,values):
        from psycopg import sql
        self.connection.execute(sql.SQL('INSERT INTO whattodo.{} ({}) VALUES ({})').format(
            sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,values)),
            sql.SQL(',').join(sql.Placeholder() for _ in values)),tuple(values.values()))

    def _source(self,record_id):
        row=self.connection.execute('''SELECT r.source_id,i.source_type,i.provider,i.scope_ref,i.external_id,
            r.external_revision,r.content_hash,r.source_timestamp,r.captured_at,r.state,r.deleted_at
            FROM whattodo.source_record r JOIN whattodo.source_identity i USING(source_id)
            WHERE r.record_id=%s''',(record_id,)).fetchone()
        if row is None: return None
        self._scope(row[2],row[3])
        wire=self.connection.execute('SELECT raw_wire,wire_hash FROM whattodo.source_payload WHERE record_id=%s',
            (record_id,)).fetchone()
        require(wire is not None,'EVIDENCE_LEGACY_SOURCE_PAYLOAD_UNAVAILABLE')
        evidence=admit_source(self.codec,bytes(wire[0])); s=evidence.source
        require(evidence.wire_hash==wire[1] and s.record_id==record_id and row==(
            s.source_id,s.source_type,s.provider,s.scope_ref,s.external_id,s.external_revision,
            s.content_hash,s.source_timestamp,s.captured_at,s.state,s.deleted_at),
            'EVIDENCE_SOURCE_PROJECTION_DRIFT')
        return evidence

    def get_source(self,record_id):
        identity(record_id)
        with self._transaction(): return self._source(record_id)

    def _raw(self,record_id):
        evidence=self._source(record_id)
        if evidence is None: return None
        row=self.connection.execute('''SELECT c.content_hash,r.raw_content_ref,c.storage_state,
            c.raw_content,c.minimized_at,c.reason_ref FROM whattodo.source_raw_content c
            JOIN whattodo.source_record r USING(record_id) WHERE c.record_id=%s''',(record_id,)).fetchone()
        require(row is not None,'EVIDENCE_RAW_METADATA_MISSING')
        raw=bytes(row[3]) if row[3] is not None else None
        require(row[0]==evidence.source.content_hash and
            (raw is None or sha256(raw).hexdigest()==row[0]),'EVIDENCE_RAW_HASH_DRIFT')
        return RawContent(record_id,row[0],row[1],row[2],raw,row[4],row[5])

    def get_raw(self,record_id):
        identity(record_id)
        with self._transaction(): return self._raw(record_id)

    def _pending(self,kind,target_id):
        key=pending_id(kind,target_id)
        if self.connection.execute('SELECT 1 FROM whattodo.pending_evidence_identity WHERE pending_id=%s',
                (key,)).fetchone() is not None: return
        self._insert('pending_evidence_identity',dict(pending_id=key,kind=kind,
            candidate_id=target_id if kind=='CANDIDATE' else None,
            conflict_id=target_id if kind=='CONFLICT' else None,created_at=self.clock.now()))
        self._insert('pending_evidence_revision',dict(pending_id=key,revision=1,state='OPEN',
            authority_ref=None,resolved_at=None,transaction_ref=None))
        self._insert('pending_evidence_head',dict(pending_id=key,revision=1))

    def _conflict(self,kind,target_id,previous,observed):
        expected=previous.semantic_hash if kind=='SOURCE' else previous.proposal_hash
        new=observed.semantic_hash if kind=='SOURCE' else observed.proposal_hash
        key=conflict_id(kind,target_id,expected,new)
        if self.connection.execute('SELECT 1 FROM whattodo.evidence_conflict WHERE conflict_id=%s',
                (key,)).fetchone() is None:
            self._insert('evidence_conflict',dict(conflict_id=key,kind=kind,
                source_record_ref=target_id if kind=='SOURCE' else None,
                candidate_id=target_id if kind=='CANDIDATE' else None,expected_hash=expected,
                observed_hash=new,wire_hash=observed.wire_hash,observed_wire=observed.raw_wire,
                detected_at=self.clock.now()))
            self._pending('CONFLICT',key)
        return key

    def _create_source(self,evidence,raw_content,locator_ref):
        s=evidence.source
        self._insert('source_record',dict(record_id=s.record_id,source_id=s.source_id,
            external_revision=s.external_revision,content_hash=s.content_hash,
            source_timestamp=s.source_timestamp,captured_at=s.captured_at,state=s.state,
            deleted_at=s.deleted_at,raw_content_ref=locator_ref))
        self._insert('source_payload',dict(record_id=s.record_id,source_id=s.source_id,
            content_hash=s.content_hash,wire_hash=evidence.wire_hash,raw_wire=evidence.raw_wire))
        self._insert('source_raw_content',dict(record_id=s.record_id,content_hash=s.content_hash,
            raw_content=raw_content,storage_state='RETAINED' if raw_content is not None else 'EXTERNAL_REFERENCE',
            minimized_at=None,reason_ref=None))

    def observe_source(self,raw_wire,*,raw_content=None,locator_ref,prior_record_id=None):
        evidence=admit_source(self.codec,raw_wire); s=evidence.source; identity(locator_ref)
        require(raw_content is None or (isinstance(raw_content,bytes) and len(raw_content)<=8388608
            and sha256(raw_content).hexdigest()==s.content_hash),'EVIDENCE_RAW_CONTENT_HASH')
        with self._transaction(write=True):
            self._lock(); self._scope(s.provider,s.scope_ref)
            existing=self.connection.execute('SELECT provider,scope_ref,external_id,source_type FROM whattodo.source_identity WHERE source_id=%s',
                (s.source_id,)).fetchone()
            meaning=(s.provider,s.scope_ref,s.external_id,s.source_type)
            if existing is None:
                require(s.state=='PRESENT','EVIDENCE_TOMBSTONE_PRIOR_REQUIRED')
                require(self.connection.execute('SELECT source_id FROM whattodo.source_identity WHERE provider=%s AND scope_ref=%s AND external_id=%s',
                    (s.provider,s.scope_ref,s.external_id)).fetchone() is None,'EVIDENCE_SOURCE_IDENTITY_CONFLICT')
                self._insert('source_identity',dict(source_id=s.source_id,provider=s.provider,
                    scope_ref=s.scope_ref,external_id=s.external_id,source_type=s.source_type))
            else: require(existing==meaning,'EVIDENCE_SOURCE_IDENTITY_CONFLICT')
            previous=self._source(s.record_id)
            if previous is not None:
                if previous.semantic_hash==evidence.semantic_hash:
                    return EvidenceObservation('REPLAY',previous)
                key=self._conflict('SOURCE',s.record_id,previous,evidence)
                return EvidenceObservation('CONFLICT',previous,conflict_id=key)
            if s.state=='DELETED':
                require(raw_content is None,'EVIDENCE_TOMBSTONE_HAS_NO_NEW_RAW_CONTENT')
                require(prior_record_id is not None,'EVIDENCE_TOMBSTONE_PRIOR_REQUIRED')
                prior=self._source(prior_record_id)
                require(prior is not None and prior.source.state=='PRESENT','EVIDENCE_TOMBSTONE_PRIOR_REQUIRED')
                require(s==mark_source_deleted(prior.source,s.deleted_at),'EVIDENCE_TOMBSTONE_SCOPE_DRIFT')
                linked=self.connection.execute('SELECT record_id FROM whattodo.source_tombstone WHERE prior_record_id=%s',
                    (prior_record_id,)).fetchone()
                if linked is not None:
                    previous=self._source(linked[0]); key=self._conflict('SOURCE',linked[0],previous,evidence)
                    return EvidenceObservation('CONFLICT',previous,conflict_id=key)
                self._create_source(evidence,None,self._raw(prior_record_id).locator_ref)
                self._insert('source_tombstone',dict(record_id=s.record_id,prior_record_id=prior_record_id))
            else:
                require(prior_record_id is None,'EVIDENCE_UNEXPECTED_PRIOR_RECORD')
                duplicate=self.connection.execute('''SELECT record_id FROM whattodo.source_record
                    WHERE source_id=%s AND content_hash=%s AND external_revision IS NOT DISTINCT FROM %s
                    AND state='PRESENT' ''',(s.source_id,s.content_hash,s.external_revision)).fetchone()
                require(duplicate is None,'EVIDENCE_SOURCE_VERSION_ID_CONFLICT')
                self._create_source(evidence,raw_content,locator_ref)
            return EvidenceObservation('INSERTED',evidence)

    def minimize_raw(self,record_id,*,reason_ref):
        identity(record_id); identity(reason_ref)
        with self._transaction(write=True):
            self._lock(); raw=self._raw(record_id); require(raw is not None,'EVIDENCE_UNKNOWN_SOURCE')
            if raw.storage_state=='RETAINED':
                self.connection.execute("UPDATE whattodo.source_raw_content SET raw_content=NULL,storage_state='MINIMIZED',minimized_at=%s,reason_ref=%s WHERE record_id=%s AND storage_state='RETAINED'",
                    (self.clock.now(),reason_ref,record_id))
            return self._raw(record_id)

    def _candidate(self,candidate_id,revision=None):
        if revision is None:
            row=self.connection.execute('SELECT max(revision) FROM whattodo.candidate_revision WHERE candidate_id=%s',
                (candidate_id,)).fetchone()
            if row[0] is None: return None
            revision=row[0]
        row=self.connection.execute('''SELECT source_record_ref,parser_version,action,task_id,task_revision,
            proposed_fields,confidence,review_state,review_authority_ref,reviewed_at,created_at,canonical_task_ref
            FROM whattodo.candidate_revision WHERE candidate_id=%s AND revision=%s''',
            (candidate_id,revision)).fetchone()
        if row is None: return None
        source=self._source(row[0]); require(source is not None,'EVIDENCE_UNKNOWN_SOURCE')
        payload=self.connection.execute('SELECT raw_wire,wire_hash,proposal_hash FROM whattodo.candidate_payload WHERE candidate_id=%s AND revision=%s',
            (candidate_id,revision)).fetchone()
        require(payload is not None,'EVIDENCE_LEGACY_CANDIDATE_PAYLOAD_UNAVAILABLE')
        evidence=admit_candidate(self.codec,bytes(payload[0])); c=evidence.candidate
        require(c.candidate_id==candidate_id and evidence.wire_hash==payload[1] and evidence.proposal_hash==payload[2],
            'EVIDENCE_CANDIDATE_PAYLOAD_DRIFT')
        require((c.source_id,c.source_hash)==(source.source.source_id,source.source.content_hash),
            'EVIDENCE_CANDIDATE_SOURCE_DRIFT')
        require(row==(c.source_record_id,c.parser_version,c.action,c.target_task_id,c.target_revision,
            evidence.fields,c.confidence,c.review_state,c.authority_ref,c.reviewed_at,c.created_at,c.canonical_task_id),
            'EVIDENCE_CANDIDATE_PROJECTION_DRIFT')
        pointers=self.connection.execute('''SELECT field_pointer,source_record_ref,source_id,source_hash
            FROM whattodo.candidate_field_provenance WHERE candidate_id=%s AND revision=%s ORDER BY field_pointer''',
            (candidate_id,revision)).fetchall()
        expected=[('/proposed_fields/'+key.replace('~','~0').replace('/','~1'),c.source_record_id,c.source_id,c.source_hash)
            for key in sorted(evidence.fields)]
        require(pointers==expected,'EVIDENCE_FIELD_PROVENANCE_DRIFT')
        return evidence,revision

    def get_candidate(self,candidate_id,revision=None):
        identity(candidate_id)
        require(revision is None or (type(revision) is int and revision>0),'EVIDENCE_REVISION')
        with self._transaction(): return self._candidate(candidate_id,revision)

    def observe_candidate(self,raw_wire):
        from psycopg.types.json import Jsonb
        evidence=admit_candidate(self.codec,raw_wire,pending_only=True); c=evidence.candidate
        with self._transaction(write=True):
            self._lock(); source=self._source(c.source_record_id)
            require(source is not None,'EVIDENCE_UNKNOWN_SOURCE')
            require((c.source_id,c.source_hash)==(source.source.source_id,source.source.content_hash),
                'EVIDENCE_CANDIDATE_SOURCE_DRIFT')
            natural=(c.source_record_id,c.parser_version,c.action,c.target_task_id,c.target_revision)
            existing=self.connection.execute('''SELECT candidate_id FROM whattodo.candidate_identity
                WHERE source_record_ref=%s AND parser_version=%s AND action=%s
                AND task_id IS NOT DISTINCT FROM %s AND task_revision IS NOT DISTINCT FROM %s''',natural).fetchone()
            by_id=self.connection.execute('SELECT source_record_ref,parser_version,action,task_id,task_revision FROM whattodo.candidate_identity WHERE candidate_id=%s',
                (c.candidate_id,)).fetchone()
            require(by_id is None or by_id==natural,'EVIDENCE_CANDIDATE_IDENTITY_CONFLICT')
            if existing is not None:
                require(existing==(c.candidate_id,),'EVIDENCE_CANDIDATE_VERSION_ID_CONFLICT')
                previous,revision=self._candidate(c.candidate_id)
                if previous.proposal_hash==evidence.proposal_hash:
                    return EvidenceObservation('REPLAY',previous,revision)
                key=self._conflict('CANDIDATE',c.candidate_id,previous,evidence)
                return EvidenceObservation('CONFLICT',previous,revision,key)
            require(source.source.state=='PRESENT' and self.connection.execute('SELECT 1 FROM whattodo.source_tombstone WHERE prior_record_id=%s',
                (c.source_record_id,)).fetchone() is None,'EVIDENCE_DELETED_SOURCE_CANNOT_CREATE_PROPOSAL')
            if c.target_task_id is not None:
                require(self.connection.execute('SELECT 1 FROM whattodo.task_revision WHERE task_id=%s AND revision=%s',
                    (c.target_task_id,c.target_revision)).fetchone() is not None,'EVIDENCE_UNKNOWN_TARGET')
            self._insert('candidate_identity',dict(candidate_id=c.candidate_id,source_record_ref=c.source_record_id,
                parser_version=c.parser_version,action=c.action,task_id=c.target_task_id,task_revision=c.target_revision))
            self._insert('candidate_revision',dict(candidate_id=c.candidate_id,revision=1,source_record_ref=c.source_record_id,
                parser_version=c.parser_version,action=c.action,task_id=c.target_task_id,task_revision=c.target_revision,
                proposed_fields=Jsonb(evidence.fields,dumps=canonical),confidence=c.confidence,review_state='PENDING',
                review_authority_ref=None,reviewed_at=None,created_at=c.created_at,canonical_task_ref=None))
            self._insert('candidate_payload',dict(candidate_id=c.candidate_id,revision=1,source_record_ref=c.source_record_id,
                source_id=c.source_id,source_hash=c.source_hash,proposal_hash=evidence.proposal_hash,
                wire_hash=evidence.wire_hash,raw_wire=evidence.raw_wire))
            for key in sorted(evidence.fields):
                self._insert('candidate_field_provenance',dict(candidate_id=c.candidate_id,revision=1,
                    field_pointer='/proposed_fields/'+key.replace('~','~0').replace('/','~1'),
                    source_record_ref=c.source_record_id,source_id=c.source_id,source_hash=c.source_hash))
            self._pending('CANDIDATE',c.candidate_id)
            return EvidenceObservation('INSERTED',evidence)

    def pending_items(self):
        from psycopg import sql
        if not self.scopes: return ()
        with self._transaction():
            for scope in self.scopes: self._scope(scope.provider,scope.scope_ref)
            predicate=sql.SQL(' OR ').join(sql.SQL('(s.provider=%s AND s.scope_ref=%s)') for _ in self.scopes)
            query=sql.SQL('''SELECT p.pending_id,p.kind,p.candidate_id,p.conflict_id,p.created_at,h.revision,r.state
                FROM whattodo.pending_evidence_identity p JOIN whattodo.pending_evidence_head h USING(pending_id)
                JOIN whattodo.pending_evidence_revision r USING(pending_id,revision)
                LEFT JOIN whattodo.evidence_conflict f ON p.conflict_id=f.conflict_id
                LEFT JOIN whattodo.candidate_identity c ON c.candidate_id=coalesce(p.candidate_id,f.candidate_id)
                JOIN whattodo.source_record sr ON sr.record_id=coalesce(c.source_record_ref,f.source_record_ref)
                JOIN whattodo.source_identity s ON s.source_id=sr.source_id
                WHERE r.state='OPEN' AND (''')+predicate+sql.SQL(') ORDER BY p.pending_id')
            return tuple(self.connection.execute(query,tuple(v for s in self.scopes for v in (s.provider,s.scope_ref))).fetchall())

    def get_conflict(self,key):
        identity(key)
        with self._transaction():
            row=self.connection.execute('SELECT kind,source_record_ref,candidate_id,expected_hash,observed_hash,wire_hash,observed_wire,detected_at FROM whattodo.evidence_conflict WHERE conflict_id=%s',
                (key,)).fetchone()
            if row is None: return None
            if row[0]=='SOURCE': self._source(row[1])
            else: self._candidate(row[2])
            require(sha256(bytes(row[6])).hexdigest()==row[5],'EVIDENCE_CONFLICT_WIRE_DRIFT')
            return row
