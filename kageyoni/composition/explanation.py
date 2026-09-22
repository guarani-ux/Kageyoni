from __future__ import annotations
from collections import defaultdict, deque
from typing import Any, Iterable

CAUSAL_KINDS={'causes','derives','supports','requires'}
NONCAUSAL_KINDS={'context','correlates','interprets','references'}
ALL_KINDS=CAUSAL_KINDS|NONCAUSAL_KINDS
MAX_EDGES=4096
MAX_NODES=4096

def validate_explanation_graph(edges: Iterable[dict[str,Any]]):
    try:
        raw=list(edges)
    except Exception:
        return {'valid':False,'invalid_edges':[{'reason':'explanation edges must be iterable'}],'causal_cycle':[],'edges':[],'bounded':True}
    edges=[]; malformed=[]
    for i,e in enumerate(raw):
        if not isinstance(e,dict): malformed.append({'edge_index':i,'reason':'edge must be an object'}); continue
        edges.append(dict(e))
    if malformed:
        return {'valid':False,'invalid_edges':malformed,'causal_cycle':[],'edges':edges,'bounded':True}
    if len(edges)>MAX_EDGES:
        return {'valid':False,'invalid_edges':[{'reason':'explanation edge budget exceeded'}],'causal_cycle':[],'edges':edges[:MAX_EDGES],'bounded':True}
    invalid=[]; graph=defaultdict(list); indegree=defaultdict(int); nodes=set()
    for i,e in enumerate(edges):
        a,b,k=e.get('source'),e.get('target'),e.get('kind')
        if not a or not b or k not in ALL_KINDS:
            invalid.append({'edge_index':i,'reason':'invalid typed explanation edge'}); continue
        nodes.update((a,b))
        if len(nodes)>MAX_NODES:
            invalid.append({'edge_index':i,'reason':'explanation node budget exceeded'}); break
        if k in CAUSAL_KINDS:
            graph[a].append(b); indegree[b]+=1; indegree.setdefault(a,0)
    if invalid:
        return {'valid':False,'invalid_edges':invalid,'causal_cycle':[],'edges':edges,'bounded':True}
    q=deque(n for n in nodes if indegree[n]==0); seen=0
    while q:
        n=q.popleft(); seen+=1
        for m in graph.get(n,[]):
            indegree[m]-=1
            if indegree[m]==0:q.append(m)
    cycle=[] if seen==len(nodes) else [n for n in nodes if indegree[n]>0][:64]
    return {'valid':not cycle,'invalid_edges':[],'causal_cycle':cycle,'edges':edges,'bounded':True}
