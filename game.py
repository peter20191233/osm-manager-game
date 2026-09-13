"""Browser interface in Python. No third-party Python packages or remote assets."""
from browser import document, window, html
from javascript import NULL
from engine import GameSession
from content import CATEGORIES, SCENARIOS, OFFICIAL_SOURCES


ICONS = {
    "card": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 10h18M7 15h4"/>',
    "credit": '<rect x="3" y="5" width="17" height="14" rx="3"/><path d="M3 10h17M7 15h3M18 13v8m-4-4h8"/>',
    "savings": '<path d="M5 11c0-4 3-6 7-6 2 0 4 1 5 3l3-1v6l-2 2-1 4h-3v-3H9v3H6l-1-5-2-1v-3zM10 3h4M10 8h3"/><circle cx="16" cy="10" r=".7"/>',
    "cash": '<rect x="2" y="6" width="20" height="13" rx="2"/><circle cx="12" cy="12.5" r="3"/><path d="M5 9h1m12 7h1M5 3h14"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6"/>',
    "transfer": '<path d="M3 7h17m-5-4 5 4-5 4M21 17H4m5-4-5 4 5 4"/>',
}
SHORT_SUBTITLES = {
    "accounts": "Получение и обслуживание",
    "credit": "Кредитки, кредиты, ипотека",
    "savings": "Сбережения и проценты",
    "cash": "Внести или снять в кассе",
    "insurance": "Полисы и защита",
    "transfers": "Оплата услуг и переводы",
}
GUIDE = {
    "accounts": "Получить готовую карту, оформить дебетовую, перевыпустить её или открыть текущий счёт. Готовая карта → сюда; новая кредитка → кредитные продукты.",
    "credit": "Подать заявку на кредитную карту, кредит наличными, ипотеку или рефинансирование. Кредит наличными — это оформление займа, а не выдача денег в кассе.",
    "savings": "Открыть или продлить вклад, узнать о накопительном счёте, распорядиться сбережениями. Обычный текущий счёт относится к счетам и картам.",
    "cash": "Внести или получить банкноты через кассу. В этих запросах клиенту нужна именно кассовая операция, без оформления нового кредита.",
    "insurance": "Оформить страховой полис: для жилья, автомобиля, путешествия или защиты водителя.",
    "transfers": "Отправить деньги по реквизитам, оплатить услуги, счета или квитанции. В игре это помощь специалиста по платежам.",
}
categories = {item["id"]: item for item in CATEGORIES}
scenario_by_id = {item["id"]: item for item in SCENARIOS}
mode = "shift"
session = None
modal_was_running = False
sound = False
audio_context = None
last_time = window.performance.now()
seed_counter = 0
last_saved_session = None


def escape(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def icon(name):
    return '<span class="category-icon"><svg viewBox="0 0 24 24" aria-hidden="true">' + ICONS[name] + '</svg></span>'


def read_storage(key, default):
    try:
        result = window.localStorage.getItem("osm-" + key)
        return default if result is None or result is NULL else str(result)
    except Exception:
        return default


def write_storage(key, value):
    try:
        window.localStorage.setItem("osm-" + key, str(value))
    except Exception:
        pass  # Private browsing can disallow storage; playing still works.


def best_label():
    value = read_storage("best-" + mode, "")
    prefix = "Рекорд смены" if mode == "shift" else "Рекорд тренировки"
    document["best-label"].text = prefix + ": " + value if value else "Ваш рекорд ещё впереди"


def draw_visitor(number):
    coats = ["#bd916e", "#6e9388", "#acb175", "#a18072", "#7c8d9f", "#b69579"]
    hairs = ["#574c3d", "#655147", "#7d6950", "#c4b5a1", "#493f37", "#a78657"]
    skin = ["#e9bd97", "#d4a27a", "#f0cbaa"][number % 3]
    coat, hair = coats[number % 6], hairs[number % 6]
    glasses = '<g fill="none" stroke="#5e6056" stroke-width="2"><rect x="42" y="51" width="14" height="10" rx="4"/><rect x="61" y="51" width="14" height="10" rx="4"/><path d="M56 55h5"/></g>' if number % 3 == 0 else ""
    long_hair = '<path d="M30 40q-6 38 3 57h54q10-22 1-59Z" fill="' + hair + '"/>' if number % 2 == 0 else ""
    bag = '<path d="M86 141h25l-1 39H88Z" fill="#c6a978"/><path d="M91 142v-9q8-12 14 0v9" fill="none" stroke="#917954" stroke-width="3"/>'
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 220"><ellipse cx="62" cy="209" rx="39" ry="8" fill="#68785b" opacity=".13"/>'
    svg += '<path d="M37 139l2 61h18l6-48 5 48h18l1-61" fill="#657065"/><path d="M36 199q-10 10-5 12h28v-12m10 0v12h29q1-8-15-12" fill="#4d554b"/>'
    svg += long_hair + '<path d="M36 85q-16 7-19 58l12 4 10-32-3 33h53l-4-34 9 34 13-5q-4-50-24-58Z" fill="' + coat + '"/>'
    svg += '<path d="M49 85l12 20 13-20" fill="#f7f1df"/><path d="M59 102v46" stroke="#786c54" opacity=".3" stroke-width="2"/>'
    svg += '<rect x="51" y="71" width="20" height="21" rx="7" fill="' + skin + '"/>'
    svg += '<ellipse cx="59" cy="49" rx="29" ry="35" fill="' + hair + '"/><ellipse cx="60" cy="55" rx="24" ry="29" fill="' + skin + '"/>'
    svg += '<path d="M35 48q-4-29 27-31 31 7 21 28-20-1-34-15-2 13-14 18" fill="' + hair + '"/>'
    svg += '<g fill="#564d3f"><circle cx="49" cy="54" r="1.7"/><circle cx="69" cy="54" r="1.7"/></g><path d="M56 66q6 5 12-1" fill="none" stroke="#a46e51" stroke-width="1.7" stroke-linecap="round"/>' + glasses
    svg += bag + '<ellipse cx="23" cy="147" rx="6" ry="9" fill="' + skin + '"/><ellipse cx="101" cy="146" rx="6" ry="9" fill="' + skin + '"/></svg>'
    document["visitor"].html = svg


def play_note(correct=True):
    global audio_context
    if not sound:
        return
    try:
        if audio_context is None:
            audio_context = window.AudioContext.new()
        audio_context.resume()
        now = audio_context.currentTime
        for offset, frequency in [(0, 523 if correct else 247), (.12, 659 if correct else 196)]:
            oscillator = audio_context.createOscillator()
            gain = audio_context.createGain()
            oscillator.type = "sine"
            oscillator.frequency.value = frequency
            gain.gain.setValueAtTime(0, now + offset)
            gain.gain.linearRampToValueAtTime(.06, now + offset + .02)
            gain.gain.exponentialRampToValueAtTime(.001, now + offset + .16)
            oscillator.connect(gain)
            gain.connect(audio_context.destination)
            oscillator.start(now + offset)
            oscillator.stop(now + offset + .18)
    except Exception:
        pass


def toggle_sound(event=None):
    global sound
    sound = not sound
    write_storage("sound", "1" if sound else "0")
    document["sound-button"].attrs["aria-pressed"] = str(sound).lower()
    document["sound-button"].attrs["aria-label"] = "Выключить звук" if sound else "Включить звук"
    document["sound-button"].attrs["title"] = "Выключить звук" if sound else "Включить звук"
    document["sound-button"].html = '♪' if sound else '♪<span class="sound-off">×</span>'
    if sound:
        play_note()


def update_stats():
    document["score"].text = str(session.score) if session else "0"
    document["served"].text = str(session.answered_count) if session else "0"
    document["combo"].text = str(session.combo) if session else "0"


def update_controls():
    active = session is not None and session.phase == "playing" and not session.paused
    for item in CATEGORIES:
        document["category-" + item["id"]].disabled = not active
    document["pause-button"].disabled = session is None or session.phase in ("ready", "finished")
    document["pause-button"].text = "▷ Продолжить" if session and session.paused else "Ⅱ Пауза"
    document["scene"].class_name = "scene paused" if session and session.paused else "scene"
    if session:
        document["next-button"].disabled = session.paused


def show_timer():
    if session is None or session.phase != "playing":
        return
    if session.paused:
        document["patience-label"].text = "На паузе"
    elif mode == "practice":
        document["patience-label"].text = "Без спешки ♧"
    else:
        remaining = session.remaining_seconds
        document["patience-label"].text = "Ожидание: " + str(int(window.Math.ceil(remaining))) + " сек."
        document["patience-fill"].style.width = str(100 * remaining / session.SECONDS_PER_CLIENT) + "%"
        document["patience-track"].class_name = "patience-track urgent" if remaining < 10 else "patience-track"


def render_client():
    global last_time
    last_time = window.performance.now()
    current = session.current
    document.select(".floor-panel")[0].class_name = "floor-panel"
    document["feedback"].hidden = True
    document["flying-ticket"].hidden = True
    document["client-name"].text = current["name"].upper() + " · КЛИЕНТ " + str(session.answered_count + 1).zfill(2)
    document["client-request"].text = "«" + current["text"] + "»"
    document["request-hint"].text = "Выберите раздел на терминале →"
    document["next-button"].hidden = True
    document["patience-track"].hidden = mode == "practice"
    document["queue-caption"].text = "Каждому — правильный маршрут"
    document["queue-count"].text = "Осталось: " + str(session.shift_length - session.answered_count)
    document["scene-status"].text = "Тренировка · без спешки" if mode == "practice" else "Смена идёт · вы справитесь"
    document["scene-bubble"].html = 'Здравствуйте!<br>Поможете мне?<span>♡</span>'
    document["printer-label"].text = "Выберите услугу, чтобы напечатать талон"
    draw_visitor(sum(ord(letter) for letter in current["name"]))
    document["visitor"].class_name = "visitor arriving"
    for item in CATEGORIES:
        document["category-" + item["id"]].class_name = "category-button"
    update_controls()
    update_stats()
    show_timer()
    if window.innerWidth <= 760:
        document["request-card"].scrollIntoView({"behavior": "auto", "block": "nearest"})


def start_game(event=None):
    global session, seed_counter, last_saved_session
    seed_counter += 1
    seed = int(window.Date.now()) % 2147483647 + seed_counter
    session = GameSession(SCENARIOS, seed=seed, mode=mode, shift_length=12)
    last_saved_session = None
    session.start()
    document.body.classList.add("in-game")
    if document["modal"].open:
        document["modal"].close()
    render_client()


def feedback(result):
    if result is None:
        return
    correct = result["correct"]
    document.select(".floor-panel")[0].class_name = "floor-panel feedback-state"
    document["feedback"].hidden = False
    document["feedback"].class_name = "feedback" if correct else "feedback wrong"
    heading = "Верный маршрут! +1 к рейтингу" if correct else "Другой маршрут. −1 к рейтингу"
    if result["timed_out"]:
        heading = "Клиент не дождался талона. −1 к рейтингу"
    document["feedback"].html = '<strong>' + heading + '</strong><small>' + escape(result["explanation"]) + '</small>'
    document["patience-label"].text = "Спасибо за помощь!" if correct else "Учимся на практике"
    document["scene-bubble"].html = 'Вот и мой талон.<br>Большое спасибо!<span>♡</span>' if correct else 'Подскажете<br>другой раздел?<span>?</span>'
    document["visitor"].class_name = "visitor happy" if correct else "visitor sad"
    document["category-" + result["expected"]].class_name = "category-button correct"
    if result["chosen"] and not correct:
        document["category-" + result["chosen"]].class_name = "category-button wrong"
    ticket = result["ticket"]
    if ticket:
        # Keep printed prefixes consistent with the terminal's Russian labels.
        ticket = categories[result["chosen"]]["code"] + ticket[1:]
        document["flying-ticket"].text = ticket
        document["flying-ticket"].hidden = False
        document["printer-label"].text = "Талон " + ticket + " · " + categories[result["chosen"]]["title"]
    else:
        document["printer-label"].text = "Время вышло — талон не выдан"
    document["request-hint"].text = "Верный раздел: " + categories[result["expected"]]["title"]
    document["next-button"].hidden = False
    document["next-button"].disabled = False
    document["next-button"].text = "Итоги смены →" if result["finished"] else "Следующий клиент →"
    document["patience-track"].hidden = True
    update_controls()
    update_stats()
    play_note(correct)
    document["next-button"].focus({"preventScroll": True})
    if window.innerWidth <= 760:
        document["request-card"].scrollIntoView({"behavior": "auto", "block": "start"})


def choose(category):
    if session and not document["modal"].open:
        feedback(session.answer(category))


def next_client(event=None):
    if session is None or session.finished:
        start_game()
    elif session.phase == "feedback" and not session.paused:
        session.advance()
        if session.finished:
            finish_game()
        else:
            render_client()


def open_modal(content):
    global modal_was_running
    modal_was_running = bool(session and session.phase in ("playing", "feedback") and not session.paused)
    if session:
        session.pause()
    document["modal-content"].html = content
    if not document["modal"].open:
        document["modal"].showModal()
    update_controls()
    show_timer()


def after_close(event=None):
    global last_time, modal_was_running
    if session and modal_was_running and not document.hidden:
        session.resume()
    modal_was_running = False
    last_time = window.performance.now()
    update_controls()
    show_timer()


def close_modal(event=None):
    document["modal"].close()


def show_guide(event=None):
    content = '<h2>Один запрос — один маршрут.</h2><p>Небольшая шпаргалка для рабочего дня. Пока вы читаете, время остановлено.</p>'
    for item in CATEGORIES:
        content += '<div class="guide-row">' + icon(item["icon"]) + '<div><h3>' + escape(item["title"]) + '</h3><p>' + escape(GUIDE[item["id"]]) + '</p></div></div>'
    content += '<p>Это обобщённые разделы для игры. Названия и маршрутизация в реальном отделении могут отличаться.</p>'
    open_modal(content)


def show_about(event=None):
    content = '<h2>Маленькая игра о большой заботе.</h2><p>Вы — операционно-сервисный менеджер. Помогите 12 клиентам получить правильные талоны. Верный выбор даёт +1 к рейтингу, ошибка — −1. В рабочей смене на ответ 35 секунд; если не успеть, рейтинг тоже снижается на 1. В тренировке таймера нет.</p><div class="rule-chips"><span>1–6: выбрать талон</span><span>Enter: следующий клиент</span><span>P: пауза</span></div>'
    content += '<h3>Реальные услуги, игровые разделы</h3><p>36 авторских ситуаций основаны на открытых страницах Сбера, Альфа-Банка, ВТБ и СберСтрахования. Меню терминала унифицировано для игры: это не официальный тренажёр какого-либо банка. Проверка источников: 13 сентября 2026 года.</p><ul class="source-list">'
    for source in OFFICIAL_SOURCES:
        content += '<li><a href="' + escape(source["url"]) + '" target="_blank" rel="noopener noreferrer">' + escape(source["bank"] + " — " + source["title"]) + '</a></li>'
    content += '</ul><h3>На компьютере и телефоне</h3><p>Код игры написан на Python и выполняется в браузере с помощью <a href="https://www.brython.info/" target="_blank" rel="noopener noreferrer">Brython 3.13.2</a>. Графика векторная. На Windows можно открыть автономный файл «Играть.html». На телефоне откройте игру по ссылке сервера в одной Wi-Fi сети или с HTTPS-хостинга. На HTTPS её можно добавить на главный экран и играть офлайн после первой загрузки.</p><p>Рекорды хранятся только в этом браузере, отдельно для каждого режима. Если браузер запрещает сохранение, игра продолжит работать. Локальные файлы и HTTP/HTTPS-версии могут иметь разные рекорды.</p>'
    open_modal(content)


def finish_game():
    global last_saved_session
    result = session.summary()
    if last_saved_session is not session:
        try:
            old_best = int(read_storage("best-" + mode, "-999"))
        except (ValueError, TypeError):
            old_best = -999
        if session.score > old_best:
            write_storage("best-" + mode, session.score)
        last_saved_session = session
    best_label()
    document["scene-status"].text = "Хорошая работа. Смена завершена!"
    document["queue-caption"].text = "Все клиенты получили внимание"
    document["queue-count"].text = "Смена завершена"
    document["next-button"].text = "Новая смена →"
    document["request-hint"].text = "Можно начать заново или сменить режим."
    content = '<div class="result-icon">✴</div><h2 class="result-title">' + escape(result["rank"]) + '</h2><div class="result-score">' + str(result["score"]) + '<span>очков рейтинга</span></div>'
    content += '<div class="result-grid"><div><strong>' + str(result["correct"]) + '/12</strong><small>верных талонов</small></div><div><strong>' + str(result["accuracy"]) + '%</strong><small>точность</small></div><div><strong>' + str(result["max_combo"]) + '</strong><small>лучшая серия</small></div></div>'
    mistakes = [entry for entry in session.history if not entry["correct"]]
    if mistakes:
        content += '<h3>На заметку к следующей смене</h3><ol class="review-list">'
        for entry in mistakes:
            scenario = scenario_by_id[entry["scenario_id"]]
            content += '<li>' + escape(scenario["text"]) + '<br><strong>→ ' + escape(categories[entry["expected"]]["title"]) + '</strong></li>'
        content += '</ol>'
    else:
        content += '<p class="result-title">Ни одной ошибки. Каждый клиент на своём месте!</p>'
    content += '<div class="modal-actions"><button id="restart-button" class="primary-button">Ещё один хороший день →</button></div>'
    open_modal(content)
    document["restart-button"].bind("click", start_game)


def apply_mode(new_mode, restart=False):
    global mode, session
    mode = new_mode
    for value in ("shift", "practice"):
        document["mode-" + value].class_name = "selected" if value == mode else ""
        document["mode-" + value].attrs["aria-pressed"] = str(value == mode).lower()
    document["mode-description"].text = "12 клиентов · 35 секунд на ответ" if mode == "shift" else "12 клиентов · без ограничения времени"
    best_label()
    if restart:
        start_game()


def change_mode(new_mode):
    if new_mode == mode:
        return
    if session and not session.finished:
        title = "Начать тренировку?" if new_mode == "practice" else "Начать рабочую смену?"
        open_modal('<h2>' + title + '</h2><p>Текущая смена завершится без сохранения результата. Начнётся новая очередь из 12 клиентов.</p><button id="confirm-mode" class="primary-button">Начать заново →</button>')
        document["confirm-mode"].bind("click", lambda event: apply_mode(new_mode, restart=True))
    else:
        apply_mode(new_mode, restart=bool(session))


def pause_game(event=None):
    global last_time
    if not session or session.finished or document["modal"].open:
        return
    if session.paused:
        session.resume()
    else:
        session.pause()
    last_time = window.performance.now()
    document["scene-status"].text = "Спокойно, очередь подождёт" if session.paused else "Смена идёт · вы справитесь"
    update_controls()
    show_timer()


def visibility(event=None):
    global last_time, modal_was_running
    last_time = window.performance.now()
    if document.hidden and session and not session.finished:
        session.pause()
        modal_was_running = False
        document["scene-status"].text = "Игра на паузе · нажмите «Продолжить»"
        update_controls()
        show_timer()


def clock_tick():
    global last_time
    now = window.performance.now()
    elapsed = max(0, (now - last_time) / 1000)
    last_time = now
    if session and not document.hidden and session.phase == "playing" and not session.paused:
        if session.tick(elapsed):
            feedback(session.last_result)
        else:
            show_timer()


def keyboard(event):
    if document["modal"].open or event.repeat or event.altKey or event.ctrlKey or event.metaKey:
        return
    key = event.key
    if key in ("1", "2", "3", "4", "5", "6"):
        event.preventDefault()
        choose(CATEGORIES[int(key) - 1]["id"])
    elif key in ("p", "P", "з", "З"):
        event.preventDefault()
        pause_game()
    elif key == "Enter" and document.activeElement.tagName != "BUTTON":
        event.preventDefault()
        next_client()


for index, item in enumerate(CATEGORIES):
    category_id = item["id"]
    button = html.BUTTON(id="category-" + category_id, Class="category-button", disabled=True)
    button.attrs["aria-label"] = item["title"]
    button.html = icon(item["icon"]) + '<span class="key-hint">' + str(index + 1) + '</span><span class="category-title">' + escape(item["title"]) + '</span><span class="category-subtitle">' + escape(SHORT_SUBTITLES[category_id]) + '</span>'
    button.bind("click", lambda event, category_id=category_id: choose(category_id))
    document["category-grid"] <= button

document["next-button"].bind("click", next_client)
document["pause-button"].bind("click", pause_game)
document["mode-shift"].bind("click", lambda event: change_mode("shift"))
document["mode-practice"].bind("click", lambda event: change_mode("practice"))
document["guide-button"].bind("click", show_guide)
document["about-button"].bind("click", show_about)
document["sound-button"].bind("click", toggle_sound)
document["modal-close"].bind("click", close_modal)
document["modal"].bind("close", after_close)
document.bind("visibilitychange", visibility)
document.bind("keydown", keyboard)
if read_storage("sound", "0") == "1":
    sound = True
    document["sound-button"].html = "♪"
    document["sound-button"].attrs["aria-pressed"] = "true"
    document["sound-button"].attrs["aria-label"] = "Выключить звук"
draw_visitor(0)
best_label()
document["next-button"].text = "Начать смену →"
document["next-button"].disabled = False
window.setInterval(clock_tick, 250)
window.osmReady = True
document["load-error"].hidden = True
