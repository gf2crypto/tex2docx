"""Pipeline stages. Each module exposes run(ctx: Context) -> None.

A stage reads and writes only Context fields and files inside ctx.workdir.
It reports what it could not do through ctx.report and raises StageError
only when continuing makes no sense.
"""


class StageError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
