from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "ui.py").read_text(encoding="utf-8")
REQUIRED = (
    "#000000",
    "#050505",
    "#e84b4b",
    "#671515",
    "#ff8a7f",
    "#f5eaea",
    "#c4c4c4",
    "linear-gradient(135deg, #671515, #8c1616, #2a0505)",
)


def main() -> None:
    missing = [token for token in REQUIRED if token.lower() not in SOURCE.lower()]
    if missing:
        raise SystemExit(f"Missing YOR tokens: {', '.join(missing)}")
    print("YOR design contract: PASS")


if __name__ == "__main__":
    main()
