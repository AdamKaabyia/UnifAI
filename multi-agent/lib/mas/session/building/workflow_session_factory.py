from mas.catalog.element_registry import ElementRegistry
from mas.session.building.element_builder import SessionElementBuilder
from mas.session.domain.session_registry import SessionRegistry
from mas.session.domain.session_record import SessionRecord
from mas.engine.factory import GraphBuilderFactory
from mas.session.domain.workflow_session import WorkflowSession
from mas.graph.state.graph_state import GraphState
from mas.graph.plan_builder import PlanBuilder
from mas.graph.rt_graph_plan import RTGraphPlan
from mas.core.context import set_current_context
from mas.blueprints.models.blueprint import BlueprintSpec


class WorkflowSessionFactory:
    """
    Builds heavy runtime artifacts (plan, graph, registry) for a session.

    Exposes:
      - build_session(record, spec) — full WorkflowSession from a SessionRecord
      - build_runtime_plan()        — plan with bound callables (Temporal nodes)
      - build_session_registry()    — element instances only (Temporal conditions)
    """

    def __init__(
            self,
            element_registry: ElementRegistry,
            engine_name: str,
    ):
        self._elements = element_registry
        self._engine_name = engine_name
        self._session_builder = SessionElementBuilder(element_registry)

    @property
    def engine_name(self) -> str:
        return self._engine_name

    def build_runtime_plan(self, blueprint_spec: BlueprintSpec) -> RTGraphPlan:
        """
        Build an RTGraphPlan from a blueprint spec.

        Creates all session components, binds callables, injects StepContext.
        """
        logical_plan = PlanBuilder(self._elements).build(blueprint_spec)
        session_registry = self._session_builder.build(blueprint_spec)
        return RTGraphPlan(logical_plan, session_registry, self._elements)

    def build_session_registry(self, blueprint_spec: BlueprintSpec) -> SessionRegistry:
        """
        Build a SessionRegistry from a blueprint spec.

        Creates element instances without building a plan or binding callables.
        Used by Temporal condition activities (conditions don't need a plan).
        """
        return self._session_builder.build(blueprint_spec)

    def build_session(self, record: SessionRecord, blueprint_spec: BlueprintSpec) -> WorkflowSession:
        """
        Build a full WorkflowSession from a persisted SessionRecord.

        Compiles the graph, creates node instances, and wires them into a
        session that shares the record by reference (mutations propagate).
        """
        set_current_context(record.run_context)

        rt_graph_plan = self.build_runtime_plan(blueprint_spec)
        rt_graph_plan.pretty_print()

        engine_builder = GraphBuilderFactory(GraphState).create(self._engine_name)
        executable_graph = engine_builder.compile_from_plan(rt_graph_plan)

        return WorkflowSession(
            record=record,
            session_registry=rt_graph_plan.session_registry,
            rt_graph_plan=rt_graph_plan,
            executable_graph=executable_graph,
            builder=engine_builder,
        )
