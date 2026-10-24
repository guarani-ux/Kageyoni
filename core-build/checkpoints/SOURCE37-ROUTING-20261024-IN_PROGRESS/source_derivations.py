"""Trusted maintenance verifier only; producer/consumer activation is closed."""
import hashlib
import sqlite3
from .source_derivation_installation import DOMAINS,installation_state
from .source_derivation_history import collect_derivation_metadata
from .source_derivation_facts import require
from ..resources import schema_path
from ..persistence.unit_of_work import UnitOfWork
from ..engine import Rejected

class SourceDerivationUnavailable(Rejected):pass

def guard_artifact(engine,artifact_id):
    """Ordinary Registry/audience authorization belongs before this call.

    Producer and consuming result routes are still explicitly closed. No
    viewer=None exemption, public callback or mutable source_refs inference.
    """
    try:
        with UnitOfWork(engine.db):
            state=installation_state(engine,schema_path('migration_037.sql').read_bytes())
            resolved=collect_derivation_metadata(engine)
            require(state=='installed'or not resolved['facts'],'uninstalled derivation facts')
            require(artifact_id not in resolved['outputs'],'derived result consumer is not activated')
    except (ValueError,RuntimeError,sqlite3.DatabaseError)as error:
        raise SourceDerivationUnavailable('artifact unavailable')from error

def guard_put(engine,request_id):
    if type(request_id)is not str or request_id.casefold().startswith('source-derivation-output:'):
        raise SourceDerivationUnavailable('reserved derivation output producer is not activated')

def verify_source_derivations(engine,*,allow_pristine=True):
    require(type(allow_pristine)is bool,'strict pristine policy required')
    with UnitOfWork(engine.db):
        state=installation_state(engine,schema_path('migration_037.sql').read_bytes())
        require(allow_pristine or state!='pristine','derivation projection is not installed')
        resolved=collect_derivation_metadata(engine)
        require(state=='installed'or not resolved['facts'],'uninstalled derivation history')
        # This is an explicit maintenance body hash path, not consuming access.
        for aid,fact in resolved['outputs'].items():
            row=engine.db.execute('SELECT digest,size,content FROM artifacts WHERE artifact_id=?',(aid,)).fetchone()
            blob=bytes(row['content']);require(len(blob)==row['size']and hashlib.sha256(blob).hexdigest()==fact['creation']['result_digest']==row['digest'],'derived output body corrupt')
        return {'state':state,'installed':state=='installed','facts':len(resolved['facts'])}
