# Unified Compression Blueprint: Executable Specifications for Slices 1–5
Version: 1.0 — 2026-10-03
Status: Approved Engineering Blueprint under the Green-Only Execution Mandate

---
## Architectural Purpose
This blueprint provides the exact code specifications, schemas, interfaces, and test matrices to execute the compression of Kageyoni's fragmented subsystems into lean, high-capability core organs.

Following the success of **Slice 0 (`kageyoni/graph.py` — 9/9 tests pass)**, this document defines the remaining four implementation slices so that any agent or engineer can implement and verify each slice step-by-step with zero guesswork.

---
## 🟢 Slice 1: Declarative Gate Engine (`kageyoni/gate.py`)
### 1.1 Problem & Scope
- Current State: Scattered, ad-hoc gate classes (`vantage/gatekeeper.py`, `composition/gates.py`, `production_gates.py`, and inline prerequisite logic in `action_dispatcher.py`).
- Target: Single, declarative rule evaluator (`kageyoni/gate.py`, ~100 lines) supporting nested field paths and direct integration with `CausalDAG`.

### 1.2 Data Structures & Classes
```python
class GateOperator(str, Enum):
    EQ = '=='
    NE = '!='
    GT = '>'
    GTE = '>='
    LT = '<'
    LTE = '<='
    IN = 'in'
    NOT_IN = 'not_in'
    NOT_NULL = 'not_null'
    VALID_IN_DAG = 'valid_in_dag'

@dataclass
class GateRule:
    field: str           # Dot-notated path: e.g. 'status', 'chamber.data.condition'
    op: str             # Operator from GateOperator
    expected: Any       # Expected value, list, or DAG reference
    error_message: str  # Diagnostic explanation if rule is violated

@dataclass
class GateEvaluationResult:
    passed: bool
    violations: List[str]
    evaluated_count: int
```

### 1.3 Core Methods (`GateEngine`)
```python
class GateEngine:
    @staticmethod
    def extract_field(target: Dict[str, Any], path: str) -> Tuple[bool, Any]:
        # Traverses dot-separated keys through nested dictionaries
        parts = path.split('.')
        curr = target
        for p in parts:
            if not isinstance(curr, dict) or p not in curr:
                return False, None
            curr = curr[p]
        return True, curr

    @classmethod
    def evaluate(cls, target: Dict[str, Any], rules: List[GateRule], dag=None) -> GateEvaluationResult:
        # Evaluates all rules against target and optional CausalDAG
        # Fails closed on any violation or unknown operator
```

### 1.4 Test Matrix (`tests/test_gate_engine.py`)
1. `test_equality_and_inequality`: primitive value comparisons (`==`, `!=`).
2. `test_numeric_comparisons`: boundary checks (`>`, `<`, `>=`, `<=`).
3. `test_membership_operators`: checks collection membership (`in`, `not_in`).
4. `test_not_null_check`: asserts field exists and is not `None`.
5. `test_nested_field_traversal`: verifies lookup on `'chamber.data.condition'`.
6. `test_causal_dag_integration`: verifies `valid_in_dag` passes if node is `VALID`, fails if `INVALIDATED` or missing.
7. `test_fail_closed_unknown_operator`: raises `ValueError` on invalid operator.
8. `test_multiple_rule_aggregation`: collects all error messages when multiple rules fail.

---
## 🟢 Slice 2: Universal Cryptographic Evidence Ledger (`kageyoni/ledger.py`)
### 2.1 Problem & Scope
- Current State: 8 separate ledger classes across 8 files (1,349 lines), each with its own SQLite table (`scars`, `outcomes`, `assessments`, `knowledge`, `returns`, `contributions`). No cross-domain chronological querying.
- Target: Single, append-only, tamper-evident cryptographic event ledger (`kageyoni/ledger.py`, ~180 lines) backed by SQLite.

### 2.2 Relational DDL Schema
```sql
CREATE TABLE IF NOT EXISTS evidence_ledger (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL,           -- 'scar', 'learning', 'dispatch', 'dialogue', 'assessment', 'receipt'
    actor_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,      -- Hash of previous sequence record (genesis uses '0'*64)
    event_hash TEXT NOT NULL,     -- SHA-256(sequence + event_id + kind + actor_id + topic + payload_json + prev_hash)
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_actor ON evidence_ledger(actor_id);
CREATE INDEX IF NOT EXISTS idx_evidence_kind ON evidence_ledger(kind);
CREATE INDEX IF NOT EXISTS idx_evidence_topic ON evidence_ledger(topic);
```

### 2.3 Data Structures & Methods
```python
@dataclass
class EvidenceRecord:
    sequence: int
    event_id: str
    kind: str
    actor_id: str
    topic: str
    payload: Dict[str, Any]
    prev_hash: str
    event_hash: str
    created_at: float

class EvidenceLedger:
    def __init__(self, conn: sqlite3.Connection, table_name='evidence_ledger'): ...
    def record(self, kind: str, actor_id: str, topic: str, payload: dict, event_id=None) -> EvidenceRecord: ...
    def query(self, actor_id=None, kind=None, topic=None, limit=100, reverse=False) -> List[EvidenceRecord]: ...
    def verify_integrity(self) -> Tuple[bool, Optional[str]]: ...
```

### 2.4 Test Matrix (`tests/test_evidence_ledger.py`)
1. `test_genesis_and_chaining`: sequence 1 has `prev_hash='0'*64`, sequence 2 binds to sequence 1's `event_hash`.
2. `test_tamper_detection`: modifying a row in SQLite directly causes `verify_integrity()` to return `False`.
3. `test_cross_domain_actor_timeline`: records scar, dialogue, and learning outcome; querying `actor_id='sciel'` returns all 3 in chronological order.
4. `test_kind_and_topic_filtering`: verifies targeted query filtering.
5. `test_connection_recovery`: closes DB, reopens in fresh instance, asserts sequence continuity.

---
## 🟢 Slice 3: Universal Static Carrier & AST Scout (`kageyoni/scout.py`)
### 3.1 Problem & Scope
- Current State: Redundant crawlers in `affordances.py`, `shinobi.py`, `garganta_scout.py`, and `ast_genetic_mutator.py`.
- Target: Universal static AST organ scout (`kageyoni/scout.py`, ~150 lines) that inspects Python files across Windows and WSL without executing untrusted code.

### 3.2 Data Structures & Methods
```python
@dataclass
class FunctionSignature:
    name: str
    args: List[str]
    docstring: str
    line_number: int

@dataclass
class CarrierManifest:
    file_path: str
    relative_path: str
    classes: Dict[str, List[FunctionSignature]]
    functions: List[FunctionSignature]
    module_docstring: str
    sha256: str
    line_count: int

class CarrierScout:
    def scan_file(self, file_path: Path) -> Optional[CarrierManifest]: ...
    def scout_directory(self, root: Path, max_depth=4, exclude_dirs=None) -> List[CarrierManifest]: ...
    def find_capability(self, query: str, top_k=5) -> List[Tuple[CarrierManifest, float]]: ...
```

### 3.3 Test Matrix (`tests/test_carrier_scout.py`)
1. `test_ast_extraction`: verifies class names, methods, parameter signatures, and docstrings match AST.
2. `test_syntax_error_resilience`: corrupted files skipped cleanly without throwing unhandled exceptions.
3. `test_keyword_bm25_scoring`: searches for keywords (e.g. `'invalidation'`, `'ledger'`), verifies top-ranked carrier matches.
4. `test_directory_exclusion`: verifies `.git`, `__pycache__`, and `temp_venv` ignored.

---
## 🟢 Slice 4: Unified Celestial Kernel (`kageyoni/celestial.py`)
### 4.1 Problem & Scope
- Current State: Fractured participant models (`characters.py`, `participant_kernel.py`, `hydration.py`, `shinobi.py`).
- Target: Unified `CelestialKernel` (~200 lines) holding identity, local `CausalDAG`, persistent `EvidenceLedger`, and generating verified action proposals for `EncounterActionDispatcher`.

### 4.2 Class Specification
```python
class CelestialKernel:
    def __init__(self, character_id: str, name: str, db_path: Path, role='operative'):
        self.character_id = character_id
        self.name = name
        self.role = role
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.dag = CausalDAG()
        self.ledger = EvidenceLedger(self.conn)

    def observe(self, world_engine, encounter_id: str) -> Dict[str, Any]:
        # Perspective-scoped observation; strictly viewer=self.character_id
        return world_engine.inspect('main', encounter_id, viewer=self.character_id)

    def evaluate_action_prerequisites(self, rules: List[GateRule], observation: dict) -> GateEvaluationResult:
        # Evaluates state and local DAG via GateEngine
        return GateEngine.evaluate(observation, rules, dag=self.dag)

    def propose_action(self, encounter_id: str, action_id: str, rationale: str, payload=None) -> dict:
        # Generates canonical proposal packet for EncounterActionDispatcher
        return {
            'encounter_id': encounter_id,
            'host': f'CelestialKernel:{self.character_id}',
            'message': f'[{self.name}] Proposes {action_id}: {rationale}',
            'interpretation': rationale,
            'action': {'kind': 'propose_action', 'action_id': action_id, 'payload': payload or {}}
        }
```

### 4.3 Test Matrix (`tests/test_celestial_kernel.py`)
1. `test_celestial_initialization`: creates Celestial with local SQLite DB, verifies DAG and ledger initialized.
2. `test_perspective_observation`: mocks world engine, verifies `viewer=self.character_id` is passed.
3. `test_prerequisite_gate_evaluation`: passes valid rules, verifies `passed=True`; alters DAG node to `INVALIDATED`, verifies `passed=False`.
4. `test_propose_action_contract`: verifies returned dictionary matches `EncounterActionDispatcher` schema.
5. `test_record_experience`: writes scars and lessons to ledger, verifies hash-chain integrity.

---
## 🟢 Slice 5: Shinobi Participant Agent Upgrade
### 5.1 System Instructions Upgrade (`.agents/agents/shinobi_participant/agent.md`)
- Update instructions to equip the Shinobi with direct reach into:
  - `kageyoni.graph` (`CausalDAG`)
  - `kageyoni.gate` (`GateEngine`)
  - `kageyoni.ledger` (`EvidenceLedger`)
  - `kageyoni.scout` (`CarrierScout`)
  - `kageyoni.celestial` (`CelestialKernel`)
- Bind `CONSTELLATION_CAPABILITY_GUIDE.md` as the active operational sensory map.