import sqlite3

import pytest

from kageyoni.graph import CausalDAG, CycleDetectedError, NodeNotFoundError
from kageyoni.vantage.graph import EpistemicDependencyGraph, EpistemicNodeStatus
from kageyoni.research_compiler.claims import ClaimGraph, ClaimNode, EpistemicStatus


def chain():
    graph = EpistemicDependencyGraph()
    for name, parents in [('A', []), ('B', ['A']), ('C', ['B'])]:
        graph.add_node(name, 'test', name, dependencies=parents)
    return graph


def test_failed_update_preserves_existing_edge_and_all_metadata():
    graph = chain()
    before = graph.to_dict(), graph._dag.to_dict()
    with pytest.raises(CycleDetectedError):
        graph.add_node('B', 'changed', 'changed', dependencies=['A', 'C'])
    assert (graph.to_dict(), graph._dag.to_dict()) == before


def test_core_update_is_atomic_and_rehashes_changed_payload():
    graph = CausalDAG()
    graph.add_node('A', 'test', {'value': 1})
    graph.add_node('B', 'test', dependencies=['A'])
    before = graph.to_dict()
    with pytest.raises(CycleDetectedError):
        graph.add_node('A', 'changed', {'value': 2}, dependencies=['B'])
    assert graph.to_dict() == before
    original_hash = graph.get_node('A').content_hash
    graph.add_node('A', 'test', {'value': 2})
    assert graph.get_node('A').content_hash != original_hash


def test_status_is_a_projection_and_bound_edges_are_read_only():
    graph = chain()
    graph.invalidate('A', 'changed premise')
    graph.add_node('A', 'test', 'revised')
    assert graph.get_node('A').status == EpistemicNodeStatus.VALID
    assert graph._dag.get_node('A').status == 'VALID'
    assert graph.get_node('B').status == EpistemicNodeStatus.STALE
    assert graph.grant_approval('A', 'reviewer', '')
    assert not graph.grant_approval('B', 'reviewer', '')
    with pytest.raises(AttributeError):
        graph.get_node('B').dependencies.add('C')


def test_claim_view_sequence_and_checked_mutation():
    graph = ClaimGraph()
    for name in ['A', 'B', 'C']:
        graph.add_claim(ClaimNode(name, name, EpistemicStatus.INFERENCE))
    parents = graph.claims['B'].parent_claim_ids
    parents.append('A')
    assert parents[0] == 'A' and parents[:] == ['A'] and list(parents) == ['A']
    assert parents == ['A'] and ['A'] == parents
    before = graph._dag.to_dict()
    with pytest.raises(NodeNotFoundError):
        parents.append('ghost')
    with pytest.raises(CycleDetectedError):
        graph.claims['A'].parent_claim_ids.append('B')
    assert graph._dag.to_dict() == before
    parents[0] = 'C'
    assert graph._dag.get_node('B').dependencies == {'C'}
    assert graph._dag.get_node('A').dependents == set()
    parents.clear()
    assert graph._dag.get_node('C').dependents == set()


def test_claim_failed_update_preserves_existing_edges():
    graph = ClaimGraph()
    for name, parents in [('A', []), ('B', ['A']), ('C', ['B'])]:
        graph.add_claim(ClaimNode(name, name, EpistemicStatus.INFERENCE, parent_claim_ids=parents))
    before = graph._dag.to_dict()
    with pytest.raises(ValueError, match='CYCLE_DETECTED'):
        graph.add_claim(ClaimNode('B', 'bad', EpistemicStatus.INFERENCE, parent_claim_ids=['A', 'C']))
    assert graph._dag.to_dict() == before
    assert graph.claims['B'].statement == 'B'


def test_stale_snapshot_restores_exact_metadata():
    graph = chain()
    graph.invalidate('A', 'retracted')
    saved = graph.to_dict()
    assert EpistemicDependencyGraph.from_dict(saved).to_dict() == saved


def test_restoration_rejects_missing_edges_and_cycles():
    graph = chain()._dag
    saved = graph.to_dict()
    saved['B']['dependencies'].append('ghost')
    with pytest.raises(NodeNotFoundError):
        CausalDAG.from_dict(saved)
    saved = graph.to_dict()
    saved['A']['dependencies'].append('C')
    saved['C']['dependents'].append('A')
    with pytest.raises(CycleDetectedError):
        CausalDAG.from_dict(saved)


def test_sqlite_restore_validates_and_preserves_timestamps():
    graph = chain()._dag
    conn = sqlite3.connect(':memory:')
    graph.to_sqlite(conn)
    assert CausalDAG.from_sqlite(conn).to_dict() == graph.to_dict()
    conn.execute("INSERT INTO causal_dag_edges VALUES ('ghost', 'A')")
    with pytest.raises(NodeNotFoundError):
        CausalDAG.from_sqlite(conn)
    conn.close()
