"""Verify and smoke-test the signed APK on a disposable Android emulator.

Uses SDK command-line tools and Python's standard library, never WebView debugging.
Run after the debug instrumentation tests, before the emulator is stopped:
  python3 android/verify_release.py --apk PATH --certificate-sha256 PUBLIC_DIGEST
The existing app is uninstalled so this exercises the release APK's first launch.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET


PACKAGE = "ru.peterkorytov.osmgame"


def run(*args, timeout=30, check=True):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"{args[0]} failed: " + result.stderr.decode("utf-8", "replace"))
    return result.stdout.decode("utf-8", "replace").strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--certificate-sha256", required=True)
    parser.add_argument("--evidence", type=Path, default=Path("android/evidence/release"))
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL"))
    parser.add_argument("--build-tools", type=Path, default=Path(
        os.environ.get("ANDROID_HOME", os.environ.get("ANDROID_SDK_ROOT", "")))
        / "build-tools" / "35.0.0")
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    expected = args.certificate_sha256.replace(":", "").lower().strip()
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("Expected certificate fingerprint must contain 64 hex digits")

    signature = run(str(args.build_tools / "apksigner"), "verify", "--verbose",
                    "--print-certs", str(args.apk))
    (args.evidence / "signature.txt").write_text(signature + "\n", encoding="utf-8")
    fingerprints = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)", signature)
    if [item.lower() for item in fingerprints] != [expected]:
        raise RuntimeError("The APK's signing certificate does not match the release certificate")
    permissions = run(str(args.build_tools / "aapt"), "dump", "permissions", str(args.apk))
    if "android.permission.INTERNET" in permissions:
        raise RuntimeError("Offline release unexpectedly requests INTERNET permission")

    adb_prefix = ["adb"] + (["-s", args.serial] if args.serial else [])

    def adb(*command, **kwargs):
        return run(*adb_prefix, *command, **kwargs)

    # This script removes app data; never run it on an actual user's phone.
    if adb("shell", "getprop", "ro.kernel.qemu") != "1":
        raise RuntimeError("Release smoke testing requires a disposable emulator")
    api = adb("shell", "getprop", "ro.build.version.sdk")
    adb("shell", "svc", "wifi", "disable")
    adb("shell", "svc", "data", "disable")
    adb("uninstall", PACKAGE, check=False)
    installed = adb("install", "--no-streaming", str(args.apk), timeout=90)
    if "Success" not in installed:
        raise RuntimeError("Release APK installation did not report success: " + installed)
    launch = adb("shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity")
    if "Status: ok" not in launch:
        raise RuntimeError("Release Activity failed to start: " + launch)

    dimensions = re.findall(r"(\d+)x(\d+)", adb("shell", "wm", "size"))
    width, height = map(int, dimensions[-1])

    def screenshot(name):
        data = subprocess.run([*adb_prefix, "exec-out", "screencap", "-p"],
                              capture_output=True, timeout=20, check=True).stdout
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Emulator screenshot is not a PNG")
        (args.evidence / name).write_bytes(data)

    def hierarchy():
        # Android 12's uiautomator can exit successfully without producing a
        # fresh dump while animated accessibility content is not idle. Never
        # mistake a previous screen's XML for the current screen.
        adb("shell", "rm", "-f", "/sdcard/osm-release-ui.xml")
        output = adb("shell", "uiautomator", "dump", "--compressed", "/sdcard/osm-release-ui.xml")
        with (args.evidence / "uiautomator.log").open("a", encoding="utf-8") as log:
            log.write(output + "\n")
        if "dumped to:" not in output.lower():
            return None, ""
        text = adb("shell", "cat", "/sdcard/osm-release-ui.xml")
        (args.evidence / "latest-ui.xml").write_text(text, encoding="utf-8")
        tree = ET.fromstring(text)
        all_text = normalized_text(tree)
        if "Не удалось открыть игру" in all_text or "Открыть ещё раз" in all_text:
            raise RuntimeError("Native release loading error is visible")
        return tree, all_text

    def normalized_text(node):
        return " ".join(" ".join(n.get("text", "") + " " + n.get("content-desc", "")
                                 for n in node.iter("node")).split())

    def visible_button(tree, label):
        for node in tree.iter("node"):
            text = normalized_text(node)
            if (label not in text or node.get("class") not in (
                    "android.widget.Button", "android.widget.ToggleButton")
                    or node.get("enabled") != "true" or node.get("clickable") != "true"):
                continue
            bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
            if bounds:
                left, top, right, bottom = map(int, bounds.groups())
                x, y = (left + right) // 2, (top + bottom) // 2
                if right > left and bottom > top and 0 < x < width and 0 < y < height:
                    return x, y
        return None

    def find_button(label, timeout=60, direction="down"):
        deadline = time.monotonic() + timeout
        swipes = 0
        while time.monotonic() < deadline:
            tree, text = hierarchy()
            if tree is None:
                time.sleep(1)
                continue
            point = visible_button(tree, label)
            if point:
                return point
            if "Открываем отделение" not in text and swipes < 8:
                start, end = height * 4 // 5, height // 3
                if direction == "up":
                    start, end = end, start
                adb("shell", "input", "swipe", str(width // 2), str(start),
                    str(width // 2), str(end), "300")
                swipes += 1
            time.sleep(1)
        raise RuntimeError("Release UI did not expose an enabled button: " + label)

    try:
        find_button("Начать смену")
        # The timed mode already has debug instrumentation coverage. Use the
        # actual player-facing training switch here so Android 12 UIAutomator
        # can inspect the release without a continuously changing timer.
        training = find_button("Тренировка", direction="up")
        adb("shell", "input", "tap", str(training[0]), str(training[1]))
        selected_deadline = time.monotonic() + 45
        while time.monotonic() < selected_deadline:
            tree, _ = hierarchy()
            if tree is not None and any(n.get("resource-id") == "mode-practice"
                                        and n.get("checked") == "true" for n in tree.iter("node")):
                (args.evidence / "training-ui.xml").write_bytes(
                    (args.evidence / "latest-ui.xml").read_bytes())
                break
            time.sleep(1)
        else:
            raise RuntimeError("Release training mode was not selected")
        point = find_button("Начать смену")
        screenshot("release-ready.png")
        (args.evidence / "ready-ui.xml").write_bytes((args.evidence / "latest-ui.xml").read_bytes())
        adb("shell", "input", "tap", str(point[0]), str(point[1]))
        # Enabling a ticket category requires the Python click handler to have
        # started a shift; HTML alone cannot satisfy this check.
        accounts = find_button("Счета и карты", timeout=90)
        screenshot("release-playing.png")
        (args.evidence / "playing-ui.xml").write_bytes((args.evidence / "latest-ui.xml").read_bytes())
        adb("shell", "input", "tap", str(accounts[0]), str(accounts[1]))
        find_button("Следующий клиент", direction="up")
        answered = ET.fromstring((args.evidence / "latest-ui.xml").read_text(encoding="utf-8"))
        feedback_text = normalized_text(answered)
        if not any(value in feedback_text for value in (
                "Верный маршрут! +1 к рейтингу", "Другой маршрут. −1 к рейтингу")):
            raise RuntimeError("Release ticket tap did not produce scored feedback")
        screenshot("release-answered.png")
        (args.evidence / "answered-ui.xml").write_bytes((args.evidence / "latest-ui.xml").read_bytes())
        if not adb("shell", "pidof", PACKAGE):
            raise RuntimeError("Release app terminated after launch")
        report = {"status": "passed", "api": int(api), "package": PACKAGE,
                  "apk_sha256": hashlib.sha256(args.apk.read_bytes()).hexdigest(),
                  "certificate_sha256": expected, "internet_permission": False,
                  "wifi_and_mobile_data_disabled": True, "clean_install": True,
                  "enabled_start_button": True, "start_tap_enabled_ticket_category": True,
                  "mode": "practice", "ticket_tap_produced_scored_feedback": True}
        (args.evidence / "result.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
    finally:
        screenshot("release-final.png")


if __name__ == "__main__":
    main()
