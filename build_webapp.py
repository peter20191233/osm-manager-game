"""Build the installable, offline web edition without copying private files."""
import hashlib
import json
import re
from pathlib import Path
from build_release import inline_game

ROOT = Path(__file__).resolve().parent


def build(output: Path | None = None) -> Path:
    output = output or ROOT / 'dist' / 'ios'
    output.mkdir(parents=True, exist_ok=True)
    page = inline_game(ROOT)
    page, icon_count = re.subn(r'(<link rel="apple-touch-icon" href=")[^"]+("\s*>)',
                               r'\g<1>icon-192.png\2', page)
    if icon_count != 1:
        raise ValueError('Expected one Apple touch icon')
    page = page.replace('</head>', '''<meta name="apple-mobile-web-app-title" content="Будни ОСМ">
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="stylesheet" href="install.css">
  <script defer src="install.js"></script>
</head>''', 1)
    panel = '''
  <section class="install-panel" aria-label="Установка и сохранение игры">
    <details id="install-help">
      <summary>Установить на iPhone</summary>
      <ol>
        <li>Откройте эту страницу в Safari.</li>
        <li>Нажмите «Поделиться» → «На экран „Домой“». Если есть переключатель «Открывать как веб-приложение», включите его. Нажмите «Добавить».</li>
        <li>Откройте «Будни ОСМ» с новой иконки, пока интернет включён. Дождитесь надписи «Игра сохранена».</li>
      </ol>
      <p>После этого можно играть без интернета. Python, архивы и компьютер не нужны.</p>
      <small>Если очистить данные Safari или устройство удалит сохранённые файлы, откройте игру с интернетом для повторного сохранения.</small>
    </details>
    <p id="offline-status" role="status" aria-live="polite">Сохраняем игру для запуска без интернета…</p>
  </section>'''
    page = page.replace('</header>', '</header>' + panel, 1)
    page = page.replace('Не удалось загрузить игру. Запустите файл «Запустить игру.cmd» и обновите страницу.',
                        'Не удалось загрузить игру. Откройте её в актуальной версии Safari и обновите страницу с включённым интернетом.')
    manifest = json.loads((ROOT / 'manifest.webmanifest').read_text(encoding='utf-8'))
    for icon in manifest['icons']:
        icon['src'] = Path(icon['src']).name
        icon['purpose'] = 'any'
    payloads = {
        'index.html': page.encode('utf-8'),
        'manifest.webmanifest': (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8'),
        **{name: (ROOT / 'pwa' / name).read_bytes() for name in ('install.js', 'install.css')},
        **{name: (ROOT / 'assets' / name).read_bytes() for name in ('icon-192.png', 'icon-512.png')},
    }
    digest = hashlib.sha256()
    for name, data in sorted(payloads.items()):
        digest.update(name.encode('utf-8') + b'\0' + data)
    worker = (ROOT / 'pwa' / 'sw.js').read_text(encoding='utf-8')
    digest.update(worker.encode('utf-8'))
    payloads['sw.js'] = worker.replace('__VERSION__', digest.hexdigest()[:16]).encode('utf-8')
    for name, data in payloads.items():
        (output / name).write_bytes(data)
    print(f'Web app: {len(payloads)} files, {sum(map(len, payloads.values())):,} bytes')
    return output


if __name__ == '__main__':
    build()
