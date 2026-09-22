"""Application services for persistent nodes and bounded method contributions."""
from .persistence.migrations import install_nodes, install_contributions, install_learning, install_all
from .intelligence.nodes import Nodes, verify_nodes

class Application:
    def __init__(self, engine, *, migrate=False, migrate_methods=False, migrate_learning=False, migrate_all=False):
        if migrate_all:install_all(engine)
        elif migrate_learning:install_learning(engine)
        elif migrate_methods:install_contributions(engine)
        elif migrate:install_nodes(engine)
        from .engine import require
        require(engine.db.execute("SELECT 1 FROM engine_versions WHERE component='node_interface' AND version='1'").fetchone(),'node interface not installed; run node-init')
        verify_nodes(engine)
        self.engine=engine
        self.nodes=Nodes(engine)
    @property
    def methods(self):
        from .intelligence.methods import Methods
        return Methods(self.engine)
    @property
    def expression(self):
        from .intelligence.expression import Expression
        return Expression(self.engine)
    @property
    def contributions(self):
        from .persistence.contributions import Contributions
        return Contributions(self.engine)

    @property
    def learning(self):
        from .intelligence.learning import Learning
        return Learning(self.engine)

    @property
    def genesis(self):
        from .intelligence.genesis import Genesis
        return Genesis(self.engine)

    @property
    def encounters(self):
        from .workspaces.world import Encounters
        return Encounters(self.engine)

    @property
    def workspaces(self):
        from .workspaces.registry import Registry
        return Registry(self.engine)

    @property
    def transitions(self):
        from .workspaces.transitions import Transitions
        return Transitions(self.engine)

    @property
    def documents(self):
        from .workspaces.documents import Documents
        return Documents(self.engine)

    @property
    def artifacts(self):
        from .persistence.artifacts import Artifacts
        return Artifacts(self.engine)

    @property
    def transfers(self):
        from .intelligence.transfer import Transfers
        return Transfers(self.engine)

    @property
    def network(self):
        from .intelligence.network import Network
        return Network(self.engine)

    @property
    def repository(self):
        from .workspaces.repository import Repository
        return Repository(self.engine)

    @property
    def pipelines(self):
        from .workspaces.pipeline import Pipelines
        return Pipelines(self.engine)

    @property
    def operations(self):
        from .operations import Operations
        return Operations(self.engine)

    @property
    def composition(self):
        from .composition.registry import CompositionRegistry
        from .engine import require
        require(self.engine.db.execute("SELECT 1 FROM engine_versions WHERE component='composition_interface' AND version='1'").fetchone(), 'composition interface not installed; run engine-init')
        return CompositionRegistry(self.engine)

    @property
    def simulation(self):
        from .composition.service import CompositionService
        return CompositionService(self.engine)

    @property
    def knowledge(self):
        from .composition.knowledge import KnowledgeLedger
        from .engine import require
        require(self.engine.db.execute("SELECT 1 FROM engine_versions WHERE component='composition_interface' AND version='1'").fetchone(), 'composition interface not installed; run engine-init')
        return KnowledgeLedger(self.engine)
