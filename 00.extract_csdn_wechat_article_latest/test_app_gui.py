import unittest

from app_gui import _should_save_screenshot


class ScreenshotOptionTest(unittest.TestCase):
    def test_fscapture_implies_screenshot(self):
        self.assertTrue(_should_save_screenshot(False, True))

    def test_plain_screenshot_still_works(self):
        self.assertTrue(_should_save_screenshot(True, False))

    def test_disabled_when_both_off(self):
        self.assertFalse(_should_save_screenshot(False, False))


if __name__ == '__main__':
    unittest.main()
