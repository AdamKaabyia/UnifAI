import operator
from ..common.base_condition import BaseCondition
from ..common.models import ConditionOutputSchema, BranchType, SymbolicBranchDef
from mas.graph.state.state_view import StateView


class ThresholdCondition(BaseCondition):
    """
    Returns True or False depending on whether state[input_key]
    compares against threshold with the given operator.
    """
    
    READS = {"nodes_output"}

    OPERATORS = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }

    def __init__(self, input_key: str, threshold: float, operator: str = ">"):
        super().__init__()
        if operator not in self.OPERATORS:
            raise ValueError(f"Unsupported operator: {operator}")
        self.input_key = input_key
        self.threshold = threshold
        self.operator_fn = self.OPERATORS[operator]

    def run(self, state: StateView) -> bool:
        """
        Fetches `value = state[self.input_key]`, then returns
        operator_fn(value, threshold).
        """
        value = state.get(self.input_key)
        return self.operator_fn(float(value), self.threshold)

    def __repr__(self) -> str:
        return (
            f"<ThresholdCondition: {self.input_key} {self._operator_symbol()} {self.threshold}>"
        )

    def _operator_symbol(self) -> str:
        # Reverse lookup from function to symbol
        for symbol, func in self.OPERATORS.items():
            if func == self.operator_fn:
                return symbol
        return "<?>"

    @classmethod
    def get_output_schema(cls) -> ConditionOutputSchema:
        """
        ThresholdCondition returns boolean values (True/False).
        """
        return ConditionOutputSchema(
            branch_type=BranchType.SYMBOLIC,
            symbolic_branches=[
                SymbolicBranchDef(
                    name=True,
                    display_name="True",
                    description="Condition evaluated to true"
                ),
                SymbolicBranchDef(
                    name=False,
                    display_name="False",
                    description="Condition evaluated to false"
                )
            ],
            description="Boolean threshold condition for true/false branching"
        )
