"""Sets up clean_project and minimal_project test targets for side-by-side verification."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS_DIR = ROOT / "test_targets"

def setup_clean_project():
    clean_dir = TARGETS_DIR / "clean_project"
    clean_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Clean Python module
    (clean_dir / "calculator.py").write_text("""# Clean mathematical module
def add(a: float, b: float) -> float:
    return a + b

def multiply(a: float, b: float) -> float:
    return a * b

if __name__ == "__main__":
    print(f"2 + 2 = {add(2, 2)}")
""", encoding="utf-8")

    # 2. requirements.txt (empty or standard, no unused heavy deps)
    (clean_dir / "requirements.txt").write_text("# Clean project dependencies\n", encoding="utf-8")
    
    # 3. Clean small readme
    (clean_dir / "README.md").write_text("# Clean Project\nA well-optimized, lean repository with zero bloat.\n", encoding="utf-8")
    print(f"✓ Created clean_project at {clean_dir}")

def setup_minimal_project():
    minimal_dir = TARGETS_DIR / "minimal_project"
    minimal_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. CSS file with unminified whitespace and comments
    css_content = """/* Minimal Project Stylesheet */
.container {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px 40px;
    margin: 0 auto;
    background-color: #ffffff;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.button {
    font-size: 16px;
    line-height: 1.5;
    color: #333333;
    background-color: #f0f0f0;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 10px 20px;
    cursor: pointer;
}
"""
    (minimal_dir / "styles.css").write_text(css_content, encoding="utf-8")
    
    # 2. A small duplicate file to trigger a measured duplicate finding
    duplicate_content = "Unique content that is duplicated byte-for-byte in another file.\n" * 100
    (minimal_dir / "data1.txt").write_text(duplicate_content, encoding="utf-8")
    (minimal_dir / "data2.txt").write_text(duplicate_content, encoding="utf-8")
    
    print(f"✓ Created minimal_project at {minimal_dir}")

if __name__ == "__main__":
    setup_clean_project()
    setup_minimal_project()
