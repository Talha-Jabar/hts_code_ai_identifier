# setup_folders.py
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

STRUCTURE = [
    "agents",
    "chains",
    "data/raw",
    "data/processed",
    "data/embeddings",
    "utils",
]

TEMPLATES = {
    "agents/__init__.py": "# agents package\n",
    "chains/__init__.py": "# chains package\n",
    "utils/__init__.py": "# utils package\n",
    "README.md": "# HTS LangGraph Orchestrator\n\nGenerated project scaffold.\n",
}

def create_structure():
    for p in STRUCTURE:
        (PROJECT_ROOT / p).mkdir(parents=True, exist_ok=True)
    for fname, content in TEMPLATES.items():
        fp = PROJECT_ROOT / fname
        if not fp.exists():
            fp.write_text(content)
    print("Project folders and template files created.")
    print("Folders:", ", ".join(STRUCTURE))

if __name__ == "__main__":
    create_structure()
