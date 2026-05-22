import argparse
import ast
import sys
from pathlib import Path


def list_fixtures(module_path):
    # Ensure we are looking at the tests directory within the module
    test_dir = module_path / "tests"
    if not test_dir.exists():
        print(f"Error: Test directory not found at {test_dir}")
        return

    # Change directory to module_path to ensure relative paths in output are clean
    # But keep track of original dir if needed. For now, we'll just use absolute paths or relative to module_path.

    fixture_files = sorted(list((test_dir / "fixtures").glob("*.py")))
    fixture_files.extend(sorted(list(test_dir.rglob("conftest.py"))))

    print(f"--- Available Fixtures in {module_path.name} ({module_path}) ---\n")

    for file_path in fixture_files:
        if not file_path.exists() or file_path.name == "__init__.py":
            continue

        with open(file_path) as f:
            content = f.read()

        try:
            tree = ast.parse(content)
            fixtures_in_file = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    is_fixture = False
                    actual_name = node.name

                    for decorator in node.decorator_list:
                        dec_name = ""
                        # Handle @fixture, @pytest.fixture, @pytest_asyncio.fixture
                        if isinstance(decorator, ast.Call):
                            if isinstance(decorator.func, ast.Attribute):
                                dec_name = decorator.func.attr
                            elif isinstance(decorator.func, ast.Name):
                                dec_name = decorator.func.id

                            # Check for name= override
                            for kw in decorator.keywords:
                                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                    actual_name = kw.value.value

                        elif isinstance(decorator, ast.Attribute):
                            dec_name = decorator.attr
                        elif isinstance(decorator, ast.Name):
                            dec_name = decorator.id

                        if dec_name in ("fixture", "fixture_async", "fixture_sync"):
                            is_fixture = True

                    if is_fixture:
                        docstring = ast.get_docstring(node) or "No description."
                        first_line_doc = docstring.split("\n")[0]
                        fixtures_in_file.append(f"- {actual_name}: {first_line_doc}")

            if fixtures_in_file:
                # Print path relative to module_path for readability
                rel_path = file_path.relative_to(module_path)
                print(f"[{rel_path}]")
                for fix in sorted(set(fixtures_in_file)):
                    print(fix)
                print()
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List pytest fixtures in a module.")
    parser.add_argument("module", help="Module name (e.g., hub) or relative path to module")

    args = parser.parse_args()

    # Try as module name first
    ROOT_DIR = Path(__file__).resolve().parent.parent
    module_path = ROOT_DIR / "modules" / args.module
    if not module_path.exists():
        # Try as direct path
        module_path = Path(args.module)

    if not module_path.exists():
        print(f"Error: Module or path '{args.module}' not found.")
        sys.exit(1)

    list_fixtures(module_path.absolute())
