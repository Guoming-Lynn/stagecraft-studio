"""Python hygiene rules. Structural file checks live in check_hygiene.py."""

from __future__ import annotations

import ast
import tokenize
from dataclasses import dataclass
from io import StringIO


@dataclass(frozen=True)
class Violation:
    path: str
    code: str
    message: str
    line: int = 0

    def render(self) -> str:
        if self.line:
            return f"{self.path}:{self.line}: {self.code}: {self.message}"
        return f"{self.path}: {self.code}: {self.message}"


@dataclass(frozen=True)
class ClassRecord:
    path: str
    line: int
    name: str
    bases: tuple[str, ...]
    is_abc: bool


def forbidden_root_name(name: str) -> bool:
    folded = name.casefold()
    if folded in {"test.py", "debug.py", "scratch.py"}:
        return True
    if folded.startswith(("scratch_", "tmp_", "new_")):
        return True
    if any(marker in folded for marker in ("_old.", "_v2.", "_backup.")):
        return True
    return folded.endswith(("_old", "_v2", "_backup"))


def data_code(name: str) -> str | None:
    folded = name.casefold()
    if folded == ".env" or folded.startswith(".env."):
        return "SECRET"
    suffix = folded.rsplit(".", 1)[-1] if "." in folded else ""
    if suffix == "ipynb":
        return "NOTEBOOK"
    if suffix == "log":
        return "LOG"
    if suffix in {"h5ad", "rds", "mtx", "loom", "safetensors"}:
        return "DATA_FILE"
    if folded.startswith("pytorch_model") and folded.endswith(".bin"):
        return "DATA_FILE"
    return None


def length_violations(relative: str, source: str, limit: int, exemption: str) -> list[Violation]:
    lines = source.splitlines()
    if len(lines) <= limit or (lines and lines[0].startswith(exemption)):
        return []
    return [Violation(relative, "FILE_LENGTH", f"file exceeds {limit} lines")]


def analyze_python(relative: str, source: str) -> tuple[list[Violation], list[ClassRecord]]:
    violations = comment_violations(relative, source)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        violations.append(
            Violation(relative, "SYNTAX", "Python file does not parse", exc.lineno or 1)
        )
        return violations, []
    visitor = _Visitor(relative)
    visitor.visit(tree)
    violations.extend(visitor.violations)
    return violations, visitor.classes


def abc_violations(records: list[ClassRecord]) -> list[Violation]:
    found: list[Violation] = []
    abstract = [item for item in records if item.is_abc]
    for item in abstract:
        same_name = [other for other in abstract if other.name == item.name]
        if len(same_name) != 1:
            continue
        implementations = [
            other for other in records if other is not item and item.name in other.bases
        ]
        if len(implementations) < 2:
            found.append(
                Violation(
                    item.path, "ABC", "abstract base needs at least two implementations", item.line
                )
            )
    return found


def comment_violations(relative: str, source: str) -> list[Violation]:
    found: list[Violation] = []
    try:
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        comments = [tok for tok in tokens if tok.type == tokenize.COMMENT and tok.start[1] == 0]
    except tokenize.TokenError:
        return found
    block_start: int | None = None
    block: list[str] = []
    previous = 0
    for tok in comments:
        text = tok.string[1:].strip()
        found.extend(_todo(relative, tok.start[0], tok.string))
        if block and tok.start[0] != previous + 1:
            found.extend(_comment_block(relative, block_start or tok.start[0], block))
            block = []
            block_start = None
        if not block:
            block_start = tok.start[0]
        block.append(text)
        previous = tok.start[0]
    if block:
        found.extend(_comment_block(relative, block_start or 1, block))
    return found


class _Visitor(ast.NodeVisitor):
    def __init__(self, relative: str) -> None:
        self.relative = relative
        self.violations: list[Violation] = []
        self.classes: list[ClassRecord] = []
        self._pickle_modules = {"pickle"}
        self._sys_modules = {"sys"}
        self._importlib_modules = {"importlib"}
        self._builtin_modules = {"builtins"}
        self._pickle_funcs: set[str] = set()
        self._path_names: set[str] = set()
        self._import_module_funcs: set[str] = set()
        self._eval_names = {"eval", "exec"}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            root = alias.name.split(".")[0]
            if root == "pickle":
                self._pickle_modules.add(bound)
            elif root == "sys":
                self._sys_modules.add(bound)
            elif root == "importlib":
                self._importlib_modules.add(bound)
            elif root == "builtins":
                self._builtin_modules.add(bound)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            bound = alias.asname or alias.name
            if module == "pickle" and alias.name in {"load", "loads"}:
                self._pickle_funcs.add(bound)
            elif module == "sys" and alias.name == "path":
                self._path_names.add(bound)
            elif module == "importlib" and alias.name == "import_module":
                self._import_module_funcs.add(bound)
            elif module == "builtins" and alias.name in {"eval", "exec"}:
                self._eval_names.add(bound)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._call(node)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self._add(node, "BARE_EXCEPT", "bare except is forbidden")
        elif _is_bare_exception(node.type) and _body_is_only_pass(node.body):
            self._add(node, "EXCEPT_PASS", "except Exception: pass is forbidden")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = tuple(base for base in (_base_name(item) for item in node.bases) if base)
        self.classes.append(
            ClassRecord(self.relative, node.lineno, node.name, bases, "ABC" in bases)
        )
        self.generic_visit(node)

    def _call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name):
            self._named_call(node, func.id)
        elif isinstance(func, ast.Attribute):
            self._attribute_call(node, func)
        for keyword in node.keywords:
            if keyword.arg == "shell" and not _is_false(keyword.value):
                self._add(node, "SHELL", "shell=True and dynamic shell flags are forbidden")

    def _named_call(self, node: ast.Call, name: str) -> None:
        if name in self._eval_names:
            code = "EXEC" if name == "exec" else "EVAL"
            self._add(node, code, "eval and exec are forbidden")
        if name == "print":
            self._add(node, "PRINT", "print debugging is forbidden; use logging")
        if name in self._pickle_funcs:
            self._add(node, "PICKLE", "pickle.load and pickle.loads are forbidden")
        if name in self._import_module_funcs and not _static_module(node):
            self._add(node, "DYNAMIC_IMPORT", "import_module must receive a literal module name")

    def _attribute_call(self, node: ast.Call, func: ast.Attribute) -> None:
        if func.attr in {"eval", "exec"} and _name_in(func.value, self._builtin_modules):
            code = "EXEC" if func.attr == "exec" else "EVAL"
            self._add(node, code, "eval and exec are forbidden")
        if (
            func.attr == "import_module"
            and _name_in(func.value, self._importlib_modules)
            and not _static_module(node)
        ):
            self._add(node, "DYNAMIC_IMPORT", "import_module must receive a literal module name")
        if func.attr in {"load", "loads"} and _name_in(func.value, self._pickle_modules):
            self._add(node, "PICKLE", "pickle.load and pickle.loads are forbidden")
        if func.attr in {"append", "insert"} and _is_sys_path(
            func.value, self._sys_modules, self._path_names
        ):
            self._add(node, "SYS_PATH", "sys.path mutation is forbidden")

    def _add(self, node: ast.AST, code: str, message: str) -> None:
        line = getattr(node, "lineno", 1)
        self.violations.append(Violation(self.relative, code, message, line))


def _comment_block(relative: str, line: int, lines: list[str]) -> list[Violation]:
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return []
    if any(not _string_expr(node) for node in tree.body):
        return [Violation(relative, "COMMENTED_CODE", "commented-out code is forbidden", line)]
    return []


def _todo(relative: str, line: int, text: str) -> list[Violation]:
    folded = text.casefold()
    for marker in ("todo", "fixme"):
        start = 0
        while True:
            found = folded.find(marker, start)
            if found < 0:
                break
            if not _has_issue_ref(text[found : found + 48]):
                return [Violation(relative, "TODO", "TODO/FIXME requires an issue number", line)]
            start = found + len(marker)
    return []


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_bare_exception(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "Exception"
    if isinstance(node, ast.Tuple):
        names = [elt.id for elt in node.elts if isinstance(elt, ast.Name)]
        return bool(node.elts) and len(names) == len(node.elts) and set(names) == {"Exception"}
    return False


def _body_is_only_pass(body: list[ast.stmt]) -> bool:
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def _static_module(node: ast.Call) -> bool:
    if not node.args:
        return False
    arg = node.args[0]
    return isinstance(arg, ast.Constant) and isinstance(arg.value, str)


def _is_false(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _name_in(node: ast.expr, names: set[str]) -> bool:
    return isinstance(node, ast.Name) and node.id in names


def _is_sys_path(node: ast.expr, sys_modules: set[str], path_names: set[str]) -> bool:
    if isinstance(node, ast.Name) and node.id in path_names:
        return True
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "path"
        and isinstance(node.value, ast.Name)
        and node.value.id in sys_modules
    )


def _string_expr(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _has_issue_ref(window: str) -> bool:
    hashed = window.find("#")
    if hashed >= 0 and _digits_after(window, hashed + 1):
        return True
    folded = window.casefold()
    issue = folded.find("issue")
    return issue >= 0 and _digits_after(window, issue + len("issue"))


def _digits_after(text: str, index: int) -> bool:
    cursor = index
    while cursor < len(text) and text[cursor] in " \t:(-":
        cursor += 1
    return cursor < len(text) and text[cursor].isdigit()
