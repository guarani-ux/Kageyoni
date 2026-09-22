from __future__ import annotations
from typing import Any

class DeficitPlanner:
    """Turn compiler blockers into typed next-step proposals.

    Unlike the donor 10 Shadows resolver, this layer never labels a provision
    verified merely because it came from a dictionary or host. It only names
    what is missing and the authorities a Frame permits for resolving it.
    """
    def __init__(self, frame: dict[str,Any]):
        self.frame=frame; self.slots={s['slot_id']:s for s in frame['slots']}
    def plan(self, compilation: dict[str,Any]) -> list[dict[str,Any]]:
        out=[]
        for blocker in compilation.get('blockers',[]):
            sid=blocker.get('slot_id','')
            if sid.startswith('verification:'):
                out.append({'kind':'verification_deficit','target':sid.split(':',1)[1],'reason':blocker.get('reason'),
                            'allowed_resolution':['implement_or_repair_verifier'],'auto_resolve':False}); continue
            slot=self.slots.get(sid)
            status=blocker.get('status')
            if slot is None:
                out.append({'kind':'ontology_gap','target':sid,'reason':blocker.get('reason'),
                            'allowed_resolution':['define_slot_or_remove_binding'],'auto_resolve':False}); continue
            if status=='UNKNOWN': kind='missing_state'
            elif status=='STALE': kind='stale_state'
            elif status=='UNPLACED': kind='unplaced_aspect'
            elif status=='INVALID': kind='invalid_binding'
            else: kind='unresolved_state'
            methods=[]
            authorities=set(slot.get('authority_policy',[]))
            if 'mechanical' in authorities: methods.append('derive_or_retrieve_mechanical_state')
            if 'owner' in authorities: methods.append('request_owner_authoritative_input')
            if 'evidence' in authorities: methods.append('acquire_or_validate_evidence')
            if 'derived' in authorities: methods.append('derive_from_supported_state')
            if slot.get('host_inference') and 'host_judgment' in authorities: methods.append('request_attributed_host_judgment')
            out.append({'kind':kind,'target':sid,'reason':blocker.get('reason'),
                        'allowed_resolution':methods or ['revise_frame_or_binding'],'auto_resolve':False})
        return out
