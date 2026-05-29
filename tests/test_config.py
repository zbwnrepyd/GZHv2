import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROJECT_ENV = ROOT / ".env"


class ConfigEnvLoadingTests(unittest.TestCase):
    def setUp(self):
        self.original_project_env = PROJECT_ENV.read_text() if PROJECT_ENV.exists() else None

    def tearDown(self):
        if self.original_project_env is None:
            PROJECT_ENV.unlink(missing_ok=True)
        else:
            PROJECT_ENV.write_text(self.original_project_env)

    def _read_config_value(self, key: str, extra_env=None) -> str:
        env = os.environ.copy()
        for name in ("DEEPSEEK_API_KEY", "TAVILY_API_KEY", "TAVILY_API_KEYS", "YOUTUBE_API_KEY"):
            env.pop(name, None)
        if extra_env:
            env.update(extra_env)
        output = subprocess.check_output(
            [
                sys.executable,
                "-c",
                (
                    "import sys;"
                    "sys.path.insert(0, 'webapp');"
                    "from config import config;"
                    f"print(config.{key})"
                ),
            ],
            cwd=ROOT,
            env=env,
            text=True,
        )
        return output.strip()

    def test_project_env_is_loaded(self):
        PROJECT_ENV.write_text("TAVILY_API_KEY=project-tvly-test\n")

        self.assertEqual(
            self._read_config_value("TAVILY_API_KEY"),
            "project-tvly-test",
        )

    def test_environment_variable_overrides_project_env(self):
        PROJECT_ENV.write_text("TAVILY_API_KEY=project-tvly-test\n")

        self.assertEqual(
            self._read_config_value(
                "TAVILY_API_KEY",
                {"TAVILY_API_KEY": "shell-tvly-test"},
            ),
            "shell-tvly-test",
        )

    def test_tavily_api_keys_supports_comma_separated_list(self):
        PROJECT_ENV.write_text("TAVILY_API_KEYS=first-key, second-key\n")

        self.assertEqual(
            self._read_config_value("TAVILY_API_KEYS"),
            "['first-key', 'second-key']",
        )


if __name__ == "__main__":
    unittest.main()
