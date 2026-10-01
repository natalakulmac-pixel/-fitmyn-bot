import unittest
from datetime import datetime
from unittest.mock import patch

import main


class NotificationTests(unittest.TestCase):
    def test_tomorrow_menu_window_never_runs_after_1800(self):
        self.assertTrue(main.is_due_by(datetime(2026, 10, 1, 17, 45), "18:00"))
        self.assertTrue(main.is_due_by(datetime(2026, 10, 1, 18, 0), "18:00"))
        self.assertFalse(main.is_due_by(datetime(2026, 10, 1, 17, 44, 59), "18:00"))
        self.assertFalse(main.is_due_by(datetime(2026, 10, 1, 18, 0, 1), "18:00"))

    def test_recipe_buttons_deep_link_to_the_matching_meal(self):
        with patch.object(main, "APP_URL", "https://fitmyn.example/app?v=test"):
            markup = main.recipe_links_keyboard(["beansChicken", "proteinCurdDinner"])
        buttons = [row[0] for row in markup.inline_keyboard]
        self.assertEqual(len(buttons), 2)
        self.assertIn("recipe=beansChicken", buttons[0].web_app.url)
        self.assertIn("recipe=proteinCurdDinner", buttons[1].web_app.url)


if __name__ == "__main__":
    unittest.main()
