"""Verify and test signed release APKs on a disposable Android emulator.

The separately installed instrumentation APK has the same release certificate.
It exercises the actual release app without enabling WebView or app debugging.
Only Python's standard library and Android SDK command-line tools are required.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


PACKAGE = "ru.peterkorytov.osmgame"
TEST_PACKAGE = PACKAGE + ".test"
TEST_CLASS = PACKAGE + ".OfflineGameTest"
SCREENSHOTS = "/sdcard/Pictures/OSMReleaseQA"


def decode(value):
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value or ""


def run(*args, timeout=30, check=True):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    output = decode(result.stdout) + decode(result.stderr)
    if check and result.returncode:
        raise RuntimeError(f"{args[0]} failed: " + output)
    return output.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--test-apk", type=Path, default=Path(
        "android/app/build/outputs/apk/androidTest/release/app-release-androidTest.apk"))
    parser.add_argument("--certificate-sha256", required=True)
    parser.add_argument("--evidence", type=Path, default=Path("android/evidence/release"))
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL"))
    parser.add_argument("--build-tools", type=Path, default=Path(
        os.environ.get("ANDROID_HOME", os.environ.get("ANDROID_SDK_ROOT", "")))
        / "build-tools" / "35.0.0")
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "result.json").unlink(missing_ok=True)
    expected = args.certificate_sha256.replace(":", "").lower().strip()
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("Expected certificate fingerprint must contain 64 hex digits")

    for apk, name in ((args.apk, "signature.txt"), (args.test_apk, "test-signature.txt")):
        signature = run(str(args.build_tools / "apksigner"), "verify", "--verbose",
                        "--print-certs", str(apk))
        (args.evidence / name).write_text(signature + "\n", encoding="utf-8")
        fingerprints = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)", signature)
        if [item.lower() for item in fingerprints] != [expected]:
            raise RuntimeError(f"{apk.name} does not have the expected release certificate")
    permissions = run(str(args.build_tools / "aapt"), "dump", "permissions", str(args.apk))
    if "android.permission.INTERNET" in permissions:
        raise RuntimeError("Offline release unexpectedly requests INTERNET permission")
    apk_sha256 = hashlib.sha256(args.apk.read_bytes()).hexdigest()

    adb_prefix = ["adb"] + (["-s", args.serial] if args.serial else [])

    def adb(*command, **kwargs):
        return run(*adb_prefix, *command, **kwargs)

    # Removing app data is permitted only on the disposable CI emulator.
    if adb("shell", "getprop", "ro.kernel.qemu") != "1":
        raise RuntimeError("Release testing requires a disposable emulator")
    api = int(adb("shell", "getprop", "ro.build.version.sdk"))
    adb("shell", "svc", "wifi", "disable")
    adb("shell", "svc", "data", "disable")
    for package in (TEST_PACKAGE, PACKAGE):
        adb("uninstall", package, check=False)
        if "package:" in adb("shell", "pm", "path", package, check=False):
            raise RuntimeError("Could not remove the previous installation: " + package)
    for apk in (args.apk, args.test_apk):
        installed = adb("install", "--no-streaming", "-t", str(apk), timeout=90)
        if "Success" not in installed:
            raise RuntimeError("APK installation did not report success: " + installed)
    # These exact files belong to this test on the disposable emulator. Clear
    # old evidence so a previous run cannot satisfy screenshot validation.
    for name in ("smoke-game.png", "smoke-result.png"):
        adb("shell", "rm", "-f", SCREENSHOTS + "/" + name)
        (args.evidence / "screenshots" / name).unlink(missing_ok=True)

    command = [*adb_prefix, "shell", "am", "instrument", "-w", "-r",
               "-e", "class", TEST_CLASS,
               "-e", "expectedRelease", "true",
               "-e", "expectedCertificate", expected,
               "-e", "expectedApkSha256", apk_sha256,
               TEST_PACKAGE + "/androidx.test.runner.AndroidJUnitRunner"]
    try:
        try:
            completed = subprocess.run(command, capture_output=True, timeout=180)
            output = decode(completed.stdout) + decode(completed.stderr)
        except subprocess.TimeoutExpired as error:
            output = decode(error.stdout) + decode(error.stderr)
            (args.evidence / "instrumentation.txt").write_text(output, encoding="utf-8")
            raise RuntimeError("Signed release instrumentation exceeded 180 seconds") from error
        (args.evidence / "instrumentation.txt").write_text(output, encoding="utf-8")
        # `am instrument` may return exit code zero even when JUnit failed.
        failed = any(marker in output for marker in (
            "FAILURES", "INSTRUMENTATION_FAILED", "INSTRUMENTATION_ABORTED",
            "INSTRUMENTATION_RESULT: shortMsg=", "Process crashed"))
        if (completed.returncode != 0 or failed
                or not re.search(r"(?m)^\s*OK\s+\(4 tests\)\s*$", output)
                or not re.search(r"(?m)^INSTRUMENTATION_CODE:\s*-1\s*$", output)):
            raise RuntimeError("Signed release instrumentation failed; see instrumentation.txt")
    finally:
        # The test writes these while its Activity is visible, before teardown.
        # Pull each named file to a fixed path, including on failed runs.
        args.evidence.joinpath("screenshots").mkdir(exist_ok=True)
        pulls = []
        for name in ("smoke-game.png", "smoke-result.png"):
            pulls.append(adb("pull", SCREENSHOTS + "/" + name,
                             str(args.evidence / "screenshots" / name), timeout=30, check=False))
        (args.evidence / "screenshots-pull.txt").write_text("\n".join(pulls) + "\n", encoding="utf-8")

    for name in ("smoke-game.png", "smoke-result.png"):
        screenshot = args.evidence / "screenshots" / name
        if not screenshot.is_file() or not screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Passing release tests did not provide PNG evidence: " + name)
    report = {"status": "passed", "api": api, "package": PACKAGE,
              "apk_sha256": apk_sha256, "certificate_sha256": expected,
              "internet_permission": False, "wifi_and_mobile_data_disabled": True,
              "clean_install": True, "enabled_start_button": True,
              "start_tap_enabled_ticket_category": True, "mode": "practice",
              "ticket_tap_produced_scored_feedback": True,
              "instrumentation_tests_passed": 4,
              "bundled_music_playback_mute_pause_verified": True,
              "installed_apk_hash_and_certificate_verified": True}
    (args.evidence / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
