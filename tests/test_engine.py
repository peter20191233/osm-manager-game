"""Run with: python -m unittest discover -s tests -v."""

import unittest

from engine import CATEGORY_CODES, GameSession


def scenarios(per_category=4):
    return [
        {
            "id": category + str(index),
            "category": category,
            "text": "Запрос клиента",
            "explanation": "Причина: " + category,
        }
        for category in CATEGORY_CODES
        for index in range(per_category)
    ]


class GameSessionTests(unittest.TestCase):
    def test_full_shift_scoring_and_last_feedback(self):
        game = GameSession(scenarios(), seed=81)
        self.assertEqual(game.phase, "ready")
        self.assertIsNone(game.current)
        self.assertIsNone(game.answer("accounts"))
        game.start()
        for index in range(12):
            result = game.answer(game.current["category"])
            self.assertTrue(result["correct"])
            self.assertEqual(result["delta"], 1)
            self.assertEqual(result["score"], index + 1)
            self.assertEqual(result["finished"], index == 11)
            self.assertEqual(game.phase, "feedback")
            self.assertFalse(game.finished)
            self.assertEqual(result["explanation"], "Причина: " + result["expected"])
            game.advance()
        self.assertTrue(game.finished)
        self.assertEqual(game.phase, "finished")
        self.assertIsNone(game.current)
        self.assertEqual(game.summary(), {
            "score": 12, "correct": 12, "total": 12, "accuracy": 100,
            "max_combo": 12, "rank": "Мастер клиентского потока",
        })

    def test_double_answer_and_advance_do_not_skip_clients(self):
        game = GameSession(scenarios())
        first = game.start()
        self.assertEqual(game.advance(), first)
        game.answer(first["category"])
        self.assertIsNone(game.answer(first["category"]))
        self.assertFalse(game.tick(1000))
        self.assertEqual(game.score, 1)
        self.assertEqual(game.answered_count, 1)
        second = game.advance()
        self.assertEqual(game.advance(), second)
        self.assertEqual(game.answered_count, 1)

    def test_wrong_answers_negative_score_and_combo_reset(self):
        game = GameSession(scenarios(), shift_length=4)
        game.start()
        for index in range(4):
            expected = game.current["category"]
            chosen = expected if index == 1 else next(c for c in CATEGORY_CODES if c != expected)
            result = game.answer(chosen)
            self.assertEqual(result["correct"], index == 1)
            self.assertEqual(result["expected"], expected)
            game.advance()
        self.assertEqual(game.score, -2)
        self.assertEqual(game.correct_count, 1)
        self.assertEqual(game.combo, 0)
        self.assertEqual(game.max_combo, 1)
        self.assertEqual(game.summary()["accuracy"], 25)

    def test_timeout_scores_once_and_can_advance(self):
        game = GameSession(scenarios(), shift_length=2)
        game.start()
        expected = game.current["category"]
        self.assertFalse(game.tick(34.75))
        self.assertEqual(game.remaining_seconds, 0.25)
        self.assertTrue(game.tick(0.25))
        self.assertEqual(game.remaining_seconds, 0)
        self.assertEqual(game.phase, "feedback")
        self.assertTrue(game.last_result["timed_out"])
        self.assertFalse(game.last_result["correct"])
        self.assertEqual(game.last_result["delta"], -1)
        self.assertEqual(game.last_result["expected"], expected)
        self.assertIsNone(game.last_result["ticket"])
        self.assertIsNone(game.last_result["chosen"])
        self.assertFalse(game.tick(100))
        self.assertIsNone(game.answer(expected))
        self.assertEqual(game.score, -1)
        game.advance()
        self.assertEqual(game.remaining_seconds, 35)
        self.assertIsNone(game.last_result)
        self.assertTrue(game.tick(10000))
        self.assertTrue(game.last_result["finished"])
        game.advance()
        self.assertTrue(game.finished)
        self.assertEqual(game.score, -2)

    def test_paused_time_and_input_are_ignored(self):
        game = GameSession(scenarios())
        game.start()
        game.tick(3.5)
        game.pause()
        self.assertTrue(game.paused)
        self.assertFalse(game.tick(3600))
        self.assertEqual(game.remaining_seconds, 31.5)
        self.assertIsNone(game.answer(game.current["category"]))
        self.assertEqual(game.score, 0)
        game.resume()
        self.assertFalse(game.paused)
        self.assertTrue(game.tick(31.5))

    def test_practice_has_no_timeouts(self):
        game = GameSession(scenarios(), mode="practice")
        game.start()
        self.assertFalse(game.tick(100000))
        self.assertEqual(game.remaining_seconds, 35)
        self.assertEqual(game.score, 0)
        self.assertEqual(game.phase, "playing")
        game.answer(game.current["category"])
        self.assertEqual(game.score, 1)

    def test_bad_deltas_cannot_add_time(self):
        game = GameSession(scenarios())
        self.assertFalse(game.tick(10))
        game.start()
        game.tick(5)
        for elapsed in (0, -3, float("nan")):
            self.assertFalse(game.tick(elapsed))
        self.assertEqual(game.remaining_seconds, 30)

    def test_tickets_number_separately_and_match_chosen_category(self):
        game = GameSession(scenarios(), mode="practice", shift_length=3)
        game.start()
        self.assertEqual(game.answer("accounts")["ticket"], "A-001")
        game.advance()
        self.assertEqual(game.answer("credit")["ticket"], "K-001")
        game.advance()
        self.assertEqual(game.answer("accounts")["ticket"], "A-002")

    def test_unknown_category_does_not_use_up_client(self):
        game = GameSession(scenarios())
        game.start()
        with self.assertRaises(ValueError):
            game.answer("unknown")
        self.assertEqual(game.phase, "playing")
        self.assertEqual(game.answered_count, 0)
        self.assertEqual(game.score, 0)

    def test_categories_balanced_unique_and_reproducible(self):
        def play(seed):
            game = GameSession(scenarios(), seed=seed)
            game.start()
            clients = []
            while not game.finished:
                clients.append(game.current)
                game.answer(game.current["category"])
                game.advance()
            return clients

        clients = play(27)
        self.assertEqual(clients, play(27))
        self.assertNotEqual(clients, play(28))
        self.assertEqual(len({client["id"] for client in clients}), 12)
        for category in CATEGORY_CODES:
            self.assertEqual(sum(client["category"] == category for client in clients), 2)
        for start in (0, 6):
            self.assertEqual({client["category"] for client in clients[start:start + 6]}, set(CATEGORY_CODES))
        self.assertTrue(all(clients[i]["category"] != clients[i + 1]["category"] for i in range(11)))

    def test_small_content_pool_can_fill_whole_shift(self):
        game = GameSession(scenarios(per_category=1), shift_length=19)
        game.start()
        seen = []
        for _ in range(19):
            seen.append(game.current["category"])
            game.answer(game.current["category"])
            game.advance()
        self.assertTrue(game.finished)
        counts = [seen.count(category) for category in CATEGORY_CODES]
        self.assertEqual(max(counts) - min(counts), 1)

    def test_restart_clears_history_score_tickets_and_pause(self):
        game = GameSession(scenarios())
        first = game.start()
        game.answer("accounts")
        game.advance()
        game.tick(8)
        game.pause()
        self.assertEqual(game.start(), first)
        self.assertEqual(game.score, 0)
        self.assertEqual(game.history, [])
        self.assertEqual(game.combo, 0)
        self.assertEqual(game.max_combo, 0)
        self.assertEqual(game.answered_count, 0)
        self.assertEqual(game.remaining_seconds, 35)
        self.assertFalse(game.paused)
        self.assertEqual(game.answer("accounts")["ticket"], "A-001")

    def test_read_results_cannot_mutate_internal_state(self):
        data = scenarios()
        game = GameSession(data)
        game.start()
        current = game.current
        category = current["category"]
        current["category"] = "not a category"
        result = game.answer(category)
        result["score"] = 500
        game.last_result["delta"] = 100
        history = game.history
        history[0]["correct"] = False
        history.clear()
        self.assertEqual(game.score, 1)
        self.assertEqual(game.last_result["score"], 1)
        self.assertEqual(game.last_result["delta"], 1)
        self.assertTrue(game.history[0]["correct"])
        self.assertEqual(len(game.history), 1)
        self.assertEqual(game.current["category"], category)

    def test_invalid_configuration(self):
        for invalid_mode in ("normal", None):
            with self.assertRaises(ValueError):
                GameSession(scenarios(), mode=invalid_mode)
        for invalid_length in (0, -1, 2.5, True):
            with self.assertRaises(ValueError):
                GameSession(scenarios(), shift_length=invalid_length)
        with self.assertRaises(ValueError):
            GameSession([])
        with self.assertRaises(ValueError):
            GameSession([{"category": "unknown"}])
        with self.assertRaises(ValueError):
            GameSession([{}])


if __name__ == "__main__":
    unittest.main()
