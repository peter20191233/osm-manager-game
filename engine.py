"""Portable game rules shared by CPython and the browser's Python runtime.

This module intentionally has no imports or external dependencies. Time only
passes when the application calls ``tick`` with elapsed, visible game time.
"""


CATEGORY_CODES = {
    "accounts": "A",
    "credit": "K",
    "savings": "B",
    "cash": "H",
    "insurance": "C",
    "transfers": "P",
}

CATEGORY_TITLES = {
    "accounts": "Счета и карты",
    "credit": "Кредитные продукты",
    "savings": "Вклады и накопления",
    "cash": "Операции с наличными",
    "insurance": "Страховые продукты",
    "transfers": "Платежи и переводы",
}


class _Random:
    """Small deterministic generator, using exact integers in both runtimes."""

    def __init__(self, seed):
        self.state = int(seed) % 2147483647
        if self.state == 0:
            self.state = 1

    def below(self, maximum):
        self.state = (self.state * 48271) % 2147483647
        return self.state % maximum

    def shuffle(self, values):
        for index in range(len(values) - 1, 0, -1):
            other = self.below(index + 1)
            values[index], values[other] = values[other], values[index]


class GameSession:
    """One shift of clients; answering and advancing are separate actions.

    A scenario must contain a ``category`` ID. Other fields, including ``text``
    and ``explanation``, are passed through. A shift has ``shift_length`` clients
    and may reuse a scenario only after its category's pool has been exhausted.

    ``answer`` and an expired ``tick`` enter the feedback phase. On the last
    client, the result's ``finished`` flag is true; ``advance`` then enters the
    finished phase. This preserves the last client's feedback before results.
    """

    SECONDS_PER_CLIENT = 35.0

    def __init__(self, scenarios, seed=1, mode="shift", shift_length=12):
        if mode not in ("shift", "practice"):
            raise ValueError("mode must be 'shift' or 'practice'")
        if isinstance(shift_length, bool) or not isinstance(shift_length, int):
            raise ValueError("shift_length must be a positive integer")
        if shift_length <= 0:
            raise ValueError("shift_length must be a positive integer")

        self._scenarios = [dict(scenario) for scenario in scenarios]
        if not self._scenarios:
            raise ValueError("At least one scenario is required")
        for scenario in self._scenarios:
            if scenario.get("category") not in CATEGORY_CODES:
                raise ValueError("Every scenario must have a known category")

        self.seed = int(seed)
        self.mode = mode
        self.shift_length = shift_length
        self._deck = []
        self._reset()

    def _reset(self):
        self.phase = "ready"
        self.score = 0
        self.correct_count = 0
        self.answered_count = 0
        self.combo = 0
        self.max_combo = 0
        self.remaining_seconds = self.SECONDS_PER_CLIENT
        self.paused = False
        self._position = 0
        self._history = []
        self._last_result = None
        self._ticket_numbers = {category: 0 for category in CATEGORY_CODES}

    @property
    def current(self):
        if self.phase in ("ready", "finished"):
            return None
        return dict(self._deck[self._position])

    @property
    def finished(self):
        return self.phase == "finished"

    @property
    def history(self):
        return [dict(result) for result in self._history]

    @property
    def last_result(self):
        return dict(self._last_result) if self._last_result is not None else None

    def _make_deck(self):
        random = _Random(self.seed)
        pools = {}
        for scenario in self._scenarios:
            pools.setdefault(scenario["category"], []).append(scenario)
        for pool in pools.values():
            random.shuffle(pool)

        offsets = {category: 0 for category in pools}
        previous_scenarios = {}
        categories = list(pools)
        deck = []
        previous_category = None
        while len(deck) < self.shift_length:
            order = categories[:]
            random.shuffle(order)
            # A cycle includes each available category once. Avoid the same
            # category on both sides of a cycle boundary when possible.
            if len(order) > 1 and order[0] == previous_category:
                order[0], order[1] = order[1], order[0]
            for category in order:
                if len(deck) == self.shift_length:
                    break
                pool = pools[category]
                offset = offsets[category]
                if offset == len(pool):
                    random.shuffle(pool)
                    if len(pool) > 1 and pool[0] is previous_scenarios[category]:
                        pool[0], pool[1] = pool[1], pool[0]
                    offset = 0
                scenario = pool[offset]
                deck.append(scenario)
                offsets[category] = offset + 1
                previous_scenarios[category] = scenario
                previous_category = category
        return deck

    def start(self):
        """Start or restart this seed's shift and return its first client."""
        self._reset()
        self._deck = self._make_deck()
        self.phase = "playing"
        return self.current

    def answer(self, category_id):
        """Issue a ticket; return None if this client cannot be answered now."""
        if self.phase != "playing" or self.paused:
            return None
        if category_id not in CATEGORY_CODES:
            raise ValueError("Unknown ticket category: " + str(category_id))
        return self._record_answer(category_id, timed_out=False)

    def _record_answer(self, category_id, timed_out):
        scenario = self._deck[self._position]
        expected = scenario["category"]
        correct = not timed_out and category_id == expected
        delta = 1 if correct else -1
        self.score += delta
        self.answered_count += 1
        if correct:
            self.correct_count += 1
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
        else:
            self.combo = 0

        ticket = None
        if category_id is not None:
            self._ticket_numbers[category_id] += 1
            number = str(self._ticket_numbers[category_id]).zfill(3)
            ticket = CATEGORY_CODES[category_id] + "-" + number

        result = {
            "scenario_id": scenario.get("id"),
            "correct": correct,
            "chosen": category_id,
            "expected": expected,
            "explanation": scenario.get("explanation")
            or "Подходит раздел «" + CATEGORY_TITLES[expected] + "».",
            "delta": delta,
            "ticket": ticket,
            "score": self.score,
            "finished": self.answered_count >= self.shift_length,
            "timed_out": timed_out,
        }
        self._last_result = result
        self._history.append(result)
        self.phase = "feedback"
        return dict(result)

    def advance(self):
        """Dismiss feedback; return the next client or None when complete."""
        if self.phase != "feedback":
            return self.current
        if self.answered_count >= self.shift_length:
            self.phase = "finished"
            self.paused = False
            return None
        self._position += 1
        self.remaining_seconds = self.SECONDS_PER_CLIENT
        self._last_result = None
        self.phase = "playing"
        return self.current

    def tick(self, seconds):
        """Advance the current timer, returning true only on a new timeout."""
        if self.mode == "practice" or self.paused or self.phase != "playing":
            return False
        elapsed = float(seconds)
        if not elapsed > 0:  # Ignore negative values, zero and NaN.
            return False
        self.remaining_seconds = max(0.0, self.remaining_seconds - elapsed)
        if self.remaining_seconds > 0:
            return False
        self._record_answer(None, timed_out=True)
        return True

    def pause(self):
        """Pause on loss of visibility; call resume when the player returns."""
        if self.phase in ("playing", "feedback"):
            self.paused = True

    def resume(self):
        self.paused = False

    def summary(self):
        """Return live or final statistics; total means clients answered."""
        total = self.answered_count
        accuracy = round(100 * self.correct_count / total) if total else 0
        if total == 0:
            rank = "Стажёр ОСМ"
        elif accuracy == 100:
            rank = "Мастер клиентского потока"
        elif accuracy >= 80:
            rank = "Эксперт сервиса"
        elif accuracy >= 60:
            rank = "Уверенный ОСМ"
        else:
            rank = "Перспективный стажёр"
        return {
            "score": self.score,
            "correct": self.correct_count,
            "total": total,
            "accuracy": accuracy,
            "max_combo": self.max_combo,
            "rank": rank,
        }
