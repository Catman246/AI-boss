import tempfile
import unittest
from pathlib import Path


class ConfigureKimiTests(unittest.TestCase):
    def test_extracts_unique_keys_without_exposing_surrounding_text(self):
        from scripts.configure_kimi import extract_keys

        text = "first=sk-alpha\n重复 sk-alpha\nsecond: sk-beta_123\n"
        self.assertEqual(extract_keys(text), ["sk-alpha", "sk-beta_123"])

    def test_prefers_general_kimi_model(self):
        from scripts.configure_kimi import choose_model

        self.assertEqual(
            choose_model(["kimi-k2.7-code", "moonshot-v1-8k", "kimi-k2.6"]),
            "kimi-k2.6",
        )

    def test_writes_private_env_atomically(self):
        from scripts.configure_kimi import write_env

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / ".env"
            write_env(target, "sk-secret", "kimi-k2.6")
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "MOONSHOT_API_KEY=sk-secret\n"
                "KIMI_BASE_URL=https://api.moonshot.cn/v1\n"
                "KIMI_MODEL=kimi-k2.6\n",
            )


if __name__ == "__main__":
    unittest.main()
