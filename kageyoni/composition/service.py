from __future__ import annotations
from copy import deepcopy
from .adapter import EngineAspectAdapter
from .compiler import Compiler
from .effects import EffectResolver, ExpressionContract
from .governor import ResolutionGovernor
from .registry import CompositionRegistry
from ..engine import require

class CompositionService:
    """Stable interface over v10 composition primitives.

    All canonical world mutations still pass through the existing Engine.apply path.
    Registry changes describe the simulation language; they do not mutate a campaign branch.
    """
    def __init__(self, engine):
        self.engine=engine
        require(engine.db.execute("SELECT 1 FROM engine_versions WHERE component='composition_interface' AND version='1'").fetchone(),
                'composition interface not installed; run engine-init')
        self.registry=CompositionRegistry(engine)

    def capabilities(self):
        """Self-describe the compositional surface for human, CLI, API, or MCP adapters."""
        from .gates import list_gates
        return {
            'interface':'composition/1',
            'frames':self.registry.list_frames(),
            'types':self.registry.list_types(),
            'verification_gates':list_gates(),
            'slot_statuses':['FILLED','DERIVED','INFERRED','UNKNOWN','CONFLICTED','STALE','NOT_APPLICABLE','UNPLACED','INVALID'],
            'mutation_boundary':'canonical world mutations only through ResolutionGovernor -> Engine.apply',
        }

    def frames(self): return self.registry.list_frames()
    def graph(self): return self.registry.graph()
    def types(self, family=None): return self.registry.list_types(family)
    def aspects(self, family=None, status='active'): return self.registry.list_aspects(family=family,status=status)
    def register_aspect(self, definition, declared_by='owner'): return self.registry.register_aspect(definition,declared_by=declared_by)

    def compile(self, frame_id, aspects, bindings, version=None, context=None, exploratory=False):
        """Compile declarative inputs. Scoped resolution requires context; exploratory mode is explicit."""
        if context is None and not exploratory:
            # Unscoped compile remains structural-only for compatibility; callers may not use it to authorize effects.
            context={}
        result=Compiler(self.registry.frame(frame_id,version),aspects).compile(bindings,context=context)
        return {'frame_id':frame_id,'bindings':bindings,'result':result}

    def resolve(self, frame_id, aspects, bindings, version=None, context=None, exploratory=False):
        """Resolve only admitted inputs. Scoped effects require explicit context or exploratory=True."""
        require(isinstance(aspects,list),'aspects must be a list')
        require(isinstance(bindings,dict),'bindings must be an object')
        if context is None and not exploratory:
            context={'branch':'main','revision':self.engine.branch('main')['revision']}
        packet=self.compile(frame_id,aspects,bindings,version,context=context,exploratory=exploratory)
        active=set(packet['result'].get('admitted_aspect_ids',[]))
        safe_aspects=[a for a in aspects if isinstance(a,dict)] if isinstance(aspects,(list,tuple)) else []
        resolution=EffectResolver().resolve(safe_aspects,active_aspects=active)
        expression=ExpressionContract().build(packet['result'],resolution)
        return {**packet,'resolution':resolution,'expression_contract':expression}

    def compile_scene(self, scene_id, participant_ids, branch='main'):
        """Compile an existing world scene into a fail-closed v10 snapshot admission result."""
        require(isinstance(participant_ids,list) and participant_ids,'participant_ids required')
        adapter=EngineAspectAdapter(self.engine,branch)
        aspects,bindings=adapter.narrative_scene(scene_id,participant_ids)
        result=Compiler(self.registry.frame('narrative_scene.v1'),aspects).compile(bindings,context={'branch':branch,'revision':self.engine.branch(branch)['revision']})
        return {'branch':branch,'scene_id':scene_id,'aspects':aspects,'bindings':bindings,'basis_manifest':adapter.basis_manifest(aspects),'basis_hash':adapter.binding_hash(aspects),'result':result}

    def resolve_scene(self, scene_id, participant_ids, branch='main'):
        """Compile an existing scene and expose qualitative effects/expression pressures."""
        packet=self.compile_scene(scene_id,participant_ids,branch)
        active=set(packet['result'].get('admitted_aspect_ids',[]))
        resolution=EffectResolver().resolve(packet['aspects'],active_aspects=active)
        expression=ExpressionContract().build(packet['result'],resolution)
        return {**packet,'resolution':resolution,'expression_contract':expression}

    def prepare_event(self, scene_id, participant_ids, command, branch='main'):
        """Preview an existing Engine.apply command against a compiled scene without committing it."""
        packet=self.compile_scene(scene_id,participant_ids,branch)
        require(command.get('branch')==branch,'command branch differs from compiled scene branch')
        prepared=ResolutionGovernor(self.engine).prepare(packet['result'],deepcopy(command),basis_manifest=packet['basis_manifest'])
        return {'compiled':packet,'prepared':prepared}

    def commit_event(self, scene_id, participant_ids, command, prepared, branch='main', authorize=False):
        """Commit exactly the previewed command after rechecking state and explicit authorization."""
        require(authorize is True,'explicit authorize=true required for state mutation')
        packet=self.compile_scene(scene_id,participant_ids,branch)
        require(command.get('branch')==branch,'command branch differs from compiled scene branch')
        from ..v11.integration import begin_domain_operation,complete_domain_operation
        mediation=begin_domain_operation(self.engine,scope='world',objective='Commit governed world event '+str(command.get('request_id')),requirement_version='world-commit/1',basis={'branch':branch,'revision':self.engine.branch(branch)['revision'],'scene_id':scene_id,'command_hash':__import__('hashlib').sha256(__import__('json').dumps(command,sort_keys=True,separators=(',',':')).encode()).hexdigest()})
        committed=ResolutionGovernor(self.engine).commit(prepared,packet['result'],deepcopy(command))
        if committed.get('status')=='committed':
            receipt=committed['engine_receipt'];complete_domain_operation(self.engine,mediation,evidence_type='world-event',evidence_ref=receipt['event_id'],outcome={'event_id':receipt['event_id'],'request_id':receipt['request_id'],'revision':receipt['revision']},verification={'engine_verify':True,'revision':receipt['revision']})
        return {'compiled':packet,'committed':committed,**({'committed_on_failure':True} if committed.get('committed_on_failure') is True else {}),'v11_operation_id':mediation['operation_id']}
