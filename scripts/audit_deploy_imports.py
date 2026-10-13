"""
What does the demo API actually need at runtime?

  python scripts/audit_deploy_imports.py

1. Lists module-level imports (they run at startup) of heavy or experimental code.
2. Imports app.main, collects the third-party packages that really got loaded, and writes
   requirements-api.txt pinned to the versions installed here.
"""
import ast
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HEAVY = {
    "mlflow", "celery", "kafka", "langchain", "langchain_core", "langchain_community",
    "langchain_openai", "openai", "faiss", "sentence_transformers", "torch", "tensorflow",
    "airflow", "sse_starlette", "pypdf", "tiktoken", "great_expectations",
}
INTERNAL_HEAVY = (
    "app.worker", "app.data_pipeline", "app.core.connection_manager",
    "app.ml.rag_chain", "app.ml.csrd_report_generator", "app.ml.vector_store_manager",
    "app.ml.document_processor", "app.api.v1.endpoints.rag", "app.api.v1.endpoints.websocket",
)
EXTRAS = ["uvicorn", "alembic", "bcrypt", "psycopg2-binary"]   # needed at runtime, imported lazily
WINDOWS_ONLY = {"pywin32", "pywin32-ctypes"}


def is_heavy(name: str) -> bool:
    return name.split(".")[0] in HEAVY or any(
        name == p or name.startswith(p + ".") for p in INTERNAL_HEAVY
    )


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def module_level_imports(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    found: list[tuple[str, int]] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue   # runs only when called, not at startup
            if isinstance(child, ast.Import):
                found.extend((a.name, child.lineno) for a in child.names)
            elif isinstance(child, ast.ImportFrom) and child.level == 0 and child.module:
                found.append((child.module, child.lineno))
                found.extend((f"{child.module}.{a.name}", child.lineno) for a in child.names)
            visit(child)

    visit(tree)
    return found


def main() -> None:
    print("Module-level imports of heavy or experimental code "
          "(make them lazy, or gate behind ENABLE_EXPERIMENTAL):")
    count = 0
    for path in sorted((ROOT / "app").rglob("*.py")):
        if is_heavy(module_name(path)):
            continue   # the heavy modules themselves
        seen: set[tuple[int, str]] = set()
        for name, line in module_level_imports(path):
            if is_heavy(name) and (line, name) not in seen:
                seen.add((line, name))
                count += 1
                print(f"  {path.relative_to(ROOT)}:{line}  {name}")
    if count == 0:
        print("  none")

    import app.main  # noqa: F401  (executes the real import graph)

    loaded = {m.split(".")[0] for m in sys.modules} - {"app"}
    third_party = sorted(m for m in loaded if m not in sys.stdlib_module_names and not m.startswith("_"))
    owner = metadata.packages_distributions()
    dists: dict[str, str] = {}
    for module in third_party:
        for dist in owner.get(module, []):
            if dist not in WINDOWS_ONLY:
                dists[dist] = metadata.version(dist)
    for extra in EXTRAS:
        try:
            dists[extra] = metadata.version(extra)
        except metadata.PackageNotFoundError:
            print(f"  note: {extra} is not installed here")

    print("\nHeavy packages actually loaded by `import app.main`:")
    loaded_heavy = sorted(HEAVY & loaded)
    print("  " + (", ".join(loaded_heavy) if loaded_heavy else "none"))

    lines = sorted(f"{name}=={version}" for name, version in dists.items())
    Path("requirements-api.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote requirements-api.txt ({len(lines)} packages)")


if __name__ == "__main__":
    main()
