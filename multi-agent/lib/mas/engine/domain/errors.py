class GraphRecursionError(RuntimeError):
    """Raised when graph traversal exceeds the configured recursion limit."""

    def __init__(self, recursion_limit: int) -> None:
        self.recursion_limit = recursion_limit
        super().__init__(
            f"Recursion limit of {recursion_limit} reached without hitting "
            "a stop condition. You can increase the limit by passing a higher "
            "recursion_limit to GraphTraversal."
        )
