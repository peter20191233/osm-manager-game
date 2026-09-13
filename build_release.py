"""Build a portable source ZIP; optionally bundle an EXE with installed PyInstaller."""

from __future__ import annotations

import argparse
import base64
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from launcher import STATIC_FILES


def inline_game(root: Path) -> str:
    """Build one HTML file with Python, runtime and all graphics embedded."""
    page = (root / "index.html").read_text(encoding="utf-8")
    license_text = (root / "vendor/LICENSE.txt").read_text(encoding="utf-8")
    if "-->" in license_text:
        raise ValueError("Brython license contains an unexpected HTML comment terminator")
    page = page.replace("<!doctype html>", f"<!doctype html>\n<!--\nBrython license:\n{license_text}\n-->", 1)

    def replace_once(old: str, new: str) -> None:
        nonlocal page
        if page.count(old) != 1:
            raise ValueError(f"Expected exactly one HTML reference: {old}")
        page = page.replace(old, new, 1)

    def escaped_script(source: str, *, python: bool = False) -> str:
        # Prevent HTML from treating a closing tag inside a string as markup.
        escaped = "<\\x2fscript" if python else "<\\/script"
        return re.sub(r"</script", lambda _: escaped, source, flags=re.IGNORECASE)

    def data_uri(name: str, mime: str) -> str:
        encoded = base64.b64encode((root / name).read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    styles = (root / "styles.css").read_text(encoding="utf-8")
    if re.search(r"</style", styles, flags=re.IGNORECASE):
        raise ValueError("CSS contains an unexpected closing style tag")
    replace_once('<link rel="stylesheet" href="styles.css">', f"<style>\n{styles}\n</style>")
    replace_once('<link rel="manifest" href="manifest.webmanifest">', "")
    for name in ("vendor/brython.min.js", "bootstrap.js"):
        source = escaped_script((root / name).read_text(encoding="utf-8"))
        setup = ""
        if name == "vendor/brython.min.js":
            setup = "<script>window.osmStandalone=true;window.__BRYTHON__={brython_path:new URL('.',location.href).href};</script>\n"
        replace_once(f'<script defer src="{name}"></script>', f"{setup}<script>\n{source}\n</script>")
    replace_once('src="scene.svg"', f'src="{data_uri("scene.svg", "image/svg+xml")}"')
    replace_once('href="assets/icon.svg"', f'href="{data_uri("assets/icon.svg", "image/svg+xml")}"')
    replace_once('href="assets/icon-192.png"', f'href="{data_uri("assets/icon-192.png", "image/png")}"')
    page = page.replace('class="brand" href="./"', 'class="brand" href="#"')
    game = (root / "game.py").read_text(encoding="utf-8")
    for statement in (
        "from engine import GameSession",
        "from content import CATEGORIES, SCENARIOS, OFFICIAL_SOURCES",
    ):
        if game.splitlines().count(statement) != 1:
            raise ValueError(f"Expected exactly one Python import: {statement}")
        game = "\n".join(line for line in game.splitlines() if line != statement)
    python_source = "\n\n".join((
        (root / "engine.py").read_text(encoding="utf-8"),
        (root / "content.py").read_text(encoding="utf-8"),
        game,
    ))
    # This catches source-combination errors before producing a broken release.
    compile(python_source, "Играть.html", "exec")
    replace_once('<script type="text/python" src="engine.py" id="engine"></script>', "")
    replace_once('<script type="text/python" src="content.py" id="content"></script>', "")
    replace_once('<script type="text/python" src="game.py"></script>',
                 f'<script type="text/python">\n{escaped_script(python_source, python=True)}\n</script>')
    return re.sub(r"(?m)^[ \t]+$", "", page)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Собрать архив игры для Windows и HTTPS-хостинга")
    parser.add_argument("--exe", action="store_true", help="Также собрать Windows EXE установленным PyInstaller")
    options = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    release_files = (
        *STATIC_FILES,
        "launcher.py", "Запустить игру.cmd", "Играть на телефоне.cmd",
        "build_release.py", "README.md", "SOURCES.md", "ANDROID.md",
        "tests/test_engine.py", "tests/test_content.py", "tests/test_launcher.py",
    )
    missing = [name for name in release_files if not (root / name).is_file()]
    if missing:
        print("Сборка не выполнена: отсутствуют файлы:")
        print("\n".join(missing))
        return 1
    output = root / "dist"
    output.mkdir(exist_ok=True)
    standalone_path = output / "Играть.html"
    try:
        standalone = inline_game(root)
    except (OSError, ValueError, SyntaxError) as exc:
        print(f"Не удалось собрать автономную игру: {exc}")
        return 1
    standalone_path.write_text(standalone, encoding="utf-8")
    print(f"Автономная игра: {standalone_path} ({standalone_path.stat().st_size / 1024:.0f} КБ)")
    archive_path = output / "osm-game.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in release_files:
            archive.write(root / name, arcname=name)
        archive.write(standalone_path, arcname="Играть.html")
    print(f"Готово: {archive_path} ({archive_path.stat().st_size / 1024:.0f} КБ)")
    if not options.exe:
        return 0
    if os.name != "nt":
        print("Windows EXE нужно собирать на Windows. ZIP уже готов.")
        return 1
    if importlib.util.find_spec("PyInstaller") is None:
        print("PyInstaller в этом Python не установлен. ZIP готов; EXE не создан.")
        print("При желании установите PyInstaller отдельно и повторите: python build_release.py --exe")
        return 1
    build = output / "build"
    build.mkdir(exist_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
        "--name", "OSMGame", "--distpath", str(output), "--workpath", str(build),
        "--specpath", str(build),
    ]
    for name in STATIC_FILES:
        destination = str(Path(name).parent)
        command.extend(("--add-data", f"{root / name}{os.pathsep}{destination}"))
    command.append(str(root / "launcher.py"))
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
