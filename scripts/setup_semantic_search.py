import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app.semantic import MODEL_NAME, SemanticIndex


def main() -> None:
    index = SemanticIndex(
        PROJECT_DIR / "data" / "lancedb",
        PROJECT_DIR / "data" / "models" / "fastembed",
    )
    dimensions = index.warmup()
    print(f"语义模型已就绪: {MODEL_NAME} ({dimensions} 维)")


if __name__ == "__main__":
    main()
