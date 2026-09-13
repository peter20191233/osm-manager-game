"""Content contract and regression checks for the bank queue scenarios."""

from collections import Counter
import unittest
from urllib.parse import urlparse

from content import CATEGORIES, OFFICIAL_SOURCES, SCENARIOS


class ContentTests(unittest.TestCase):
    def test_unique_complete_scenarios_and_balanced_coverage(self):
        category_ids = {category["id"] for category in CATEGORIES}
        self.assertEqual(len(category_ids), 6)
        self.assertEqual(len(CATEGORIES), len(category_ids))
        self.assertGreaterEqual(len(SCENARIOS), 36)
        self.assertEqual(len({item["id"] for item in SCENARIOS}), len(SCENARIOS))
        self.assertEqual(len({item["text"] for item in SCENARIOS}), len(SCENARIOS))
        counts = Counter(item["category"] for item in SCENARIOS)
        self.assertEqual(set(counts), category_ids)
        self.assertEqual(len(set(counts.values())), 1, "All categories need equal coverage")
        for item in SCENARIOS:
            with self.subTest(scenario=item["id"]):
                for field in ("id", "name", "text", "category", "explanation"):
                    self.assertIsInstance(item[field], str)
                    self.assertTrue(item[field].strip(), field + " must not be empty")

    def test_every_scenario_has_a_resolvable_official_source(self):
        sources = {source["id"]: source for source in OFFICIAL_SOURCES}
        self.assertEqual(len(sources), len(OFFICIAL_SOURCES))
        allowed_domains = ("sberbank.ru", "alfabank.ru", "vtb.ru", "sberbankins.ru")
        for source in OFFICIAL_SOURCES:
            with self.subTest(source=source["id"]):
                url = urlparse(source["url"])
                self.assertEqual(url.scheme, "https")
                self.assertTrue(any(
                    url.hostname == domain or (url.hostname or "").endswith("." + domain)
                    for domain in allowed_domains
                ), "Source must use an official bank or insurer domain")
                self.assertTrue(source["bank"] and source["title"])
        for item in SCENARIOS:
            with self.subTest(scenario=item["id"]):
                self.assertIsInstance(item["source_ids"], list)
                self.assertTrue(item["source_ids"])
                self.assertTrue(set(item["source_ids"]).issubset(sources))

    def test_users_card_examples_remain_distinct(self):
        scenarios = {item["id"]: item for item in SCENARIOS}
        ready = scenarios["accounts_ready"]
        application = scenarios["credit_new_card"]
        self.assertEqual(ready["category"], "accounts")
        self.assertIn("уже", ready["text"].lower())
        self.assertIn("забрать", ready["text"].lower())
        self.assertEqual(application["category"], "credit")
        self.assertIn("оформить кредитную карту", application["text"].lower())

    def test_cash_requests_explicitly_require_a_cashier(self):
        for item in SCENARIOS:
            if item["category"] == "cash":
                with self.subTest(scenario=item["id"]):
                    self.assertIn("касс", item["text"].lower())
        scenarios = {item["id"]: item for item in SCENARIOS}
        # What the customer needs now determines routing, not a product keyword.
        self.assertEqual(scenarios["cash_after_deposit"]["category"], "cash")
        self.assertEqual(scenarios["cash_card_topup"]["category"], "cash")
        self.assertEqual(scenarios["credit_early"]["category"], "credit")
        self.assertIn("консультация", scenarios["credit_early"]["text"].lower())

    def test_current_and_savings_accounts_are_not_interchangeable(self):
        scenarios = {item["id"]: item for item in SCENARIOS}
        self.assertEqual(scenarios["accounts_current"]["category"], "accounts")
        self.assertEqual(scenarios["savings_account"]["category"], "savings")
        self.assertEqual(scenarios["savings_close"]["category"], "savings")
        self.assertEqual(scenarios["transfers_own"]["category"], "transfers")


if __name__ == "__main__":
    unittest.main()
