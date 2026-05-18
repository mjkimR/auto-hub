import argparse
import os
import sys
from pathlib import Path


def print_tree(directory, prefix=""):
    """Recursive function to print the directory tree."""
    try:
        files = sorted([f for f in os.listdir(directory) if not f.startswith(".") and f != "__pycache__"])
    except OSError as e:
        print(f"Error accessing {directory}: {e}")
        return

    for i, file in enumerate(files):
        path = os.path.join(directory, file)
        is_last = i == len(files) - 1

        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{file}")

        if os.path.isdir(path):
            new_prefix = prefix + ("    " if is_last else "│   ")
            print_tree(path, new_prefix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Show test directory structure for a module.")
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

    test_dir = module_path / "tests"

    print(f"--- {module_path.name} Test Directory Structure ---")
    print("tests/")
    if test_dir.exists():
        print_tree(test_dir)
    else:
        print(f"Directory {test_dir} not found.")
