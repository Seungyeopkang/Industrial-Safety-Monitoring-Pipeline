"""Retry Notion export for a completed job without re-running AI inference."""
import argparse
import json
from pathlib import Path

from notion.report_to_notion import append_report_screenshot, create_safety_report_page


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "outputs" / "results"
SCREENSHOT_DIR = PROJECT_ROOT / "outputs" / "report_screenshots"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id")
    args = parser.parse_args()

    result_path = RESULTS_DIR / f"{args.job_id}.json"
    if not result_path.exists():
        raise SystemExit(f"Result not found: {args.job_id}")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    exported = create_safety_report_page(args.job_id, result)
    result["notion"] = exported

    screenshot_path = SCREENSHOT_DIR / f"{args.job_id}_report.png"
    if exported.get("success") and screenshot_path.exists():
        screenshot_export = append_report_screenshot(exported["page_id"], None, str(screenshot_path))
        result["ui_report_screenshot"] = {
            "local_path": str(screenshot_path),
            "url": None,
            "notion": screenshot_export,
        }

    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"notion": exported, "screenshot_exists": screenshot_path.exists()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
