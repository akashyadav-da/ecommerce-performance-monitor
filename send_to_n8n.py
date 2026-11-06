from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import subprocess
import sys
import traceback
import urllib.request
import urllib.error
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PAYLOAD_PATH = BASE_DIR / "reports" / "latest_payload.json"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG = LOG_DIR / "pipeline_errors.log"

# Load environment variables
load_dotenv()

# Webhook configuration
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
DEV_WEBHOOK_URL = os.getenv("DEV_WEBHOOK_URL", "")

def current_timestamp():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%Y-%m-%d %H:%M:%S IST")


def write_error_log(stage, error_type, error, technical_traceback, report_status):
    timestamp = current_timestamp()

    with open(ERROR_LOG, "a", encoding="utf-8") as file:
        file.write("\n" + "=" * 70 + "\n")
        file.write(f"TIMESTAMP: {timestamp}\n")
        file.write(f"FAILED STAGE: {stage}\n")
        file.write(f"ERROR TYPE: {error_type}\n")
        file.write(f"ERROR REASON: {error}\n")
        file.write(f"BUSINESS REPORT STATUS: {report_status}\n")
        file.write("\nTECHNICAL TRACEBACK:\n")
        file.write(technical_traceback)
        file.write("\n" + "=" * 70 + "\n")

    return timestamp


def notify_developer(
    stage,
    error_type,
    error,
    technical_traceback,
    timestamp,
    report_status,
):
    if not DEV_WEBHOOK_URL.strip() or DEV_WEBHOOK_URL.startswith("PASTE_"):
        print("Developer webhook URL is not configured.")
        return

    notification = {
        "stage": stage,
        "error_type": error_type,
        "error": str(error),
        "traceback": technical_traceback,
        "timestamp": timestamp,
        "report_status": report_status,
    }

    data = json.dumps(notification).encode("utf-8")

    request = urllib.request.Request(
        DEV_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print("Developer notification HTTP Status:", response.status)
            print("Developer notification sent.")

    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as notify_error:
        print("Could not send developer notification:", notify_error)


def run_stage(script_name):
    print(f"\n=== Running {script_name} ===")

    result = subprocess.run(
        [sys.executable, str(BASE_DIR / script_name)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr)

    if result.returncode != 0:
        details = (
            f"{script_name} failed with exit code {result.returncode}."
        )

        if result.stderr.strip():
            details += f"\n\nSTDERR:\n{result.stderr.strip()}"

        if result.stdout.strip():
            details += f"\n\nSTDOUT:\n{result.stdout.strip()}"

        raise RuntimeError(details)


def main():
    current_stage = "configuration"
    report_status = "NOT_SENT"

    try:
        if (
            not WEBHOOK_URL.strip()
            or WEBHOOK_URL.startswith("PASTE_")
        ):
            raise RuntimeError("Main business webhook URL is not configured.")

        if (
            not DEV_WEBHOOK_URL.strip()
            or DEV_WEBHOOK_URL.startswith("PASTE_")
        ):
            raise RuntimeError("Developer notification webhook URL is not configured.")

        # Stage 1: Validate raw data
        current_stage = "validate_data.py"
        run_stage(current_stage)

        # Stage 2: Incremental ingestion
        current_stage = "incremental_ingestion.py"
        run_stage(current_stage)

        # Stage 3: Build report payload
        current_stage = "build_payload.py"
        run_stage(current_stage)

        # Stage 4: Read fresh payload
        current_stage = "payload loading"

        if not PAYLOAD_PATH.is_file():
            raise FileNotFoundError(
                f"Fresh report payload was not created: {PAYLOAD_PATH}"
            )

        with open(PAYLOAD_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)

        # Stage 5: Send business report to n8n
        current_stage = "business webhook delivery"

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        report_status = "DELIVERY_ATTEMPTED"

        with urllib.request.urlopen(request, timeout=30) as response:
            print("Business webhook HTTP Status:", response.status)
            print("Response:", response.read().decode("utf-8"))

        report_status = "SENT"
        print("\nPIPELINE COMPLETED SUCCESSFULLY.")

    except Exception as error:
        error_type = type(error).__name__
        technical_traceback = traceback.format_exc()

        timestamp = write_error_log(
            stage=current_stage,
            error_type=error_type,
            error=error,
            technical_traceback=technical_traceback,
            report_status=report_status,
        )

        print(f"\nPIPELINE FAILED at {current_stage}")
        print(f"Error type: {error_type}")
        print(f"Reason: {error}")
        print(f"Business report status: {report_status}")
        print(f"Full error logged at: {ERROR_LOG}")

        notify_developer(
            stage=current_stage,
            error_type=error_type,
            error=error,
            technical_traceback=technical_traceback,
            timestamp=timestamp,
            report_status=report_status,
        )

        sys.exit(1)


if __name__ == "__main__":
    main()