import tempfile
import unittest
from pathlib import Path

from sportsbro.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_packaged_provider_defaults_load_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.load(Path(temp_dir))

        self.assertEqual(settings.providers_config["f1"]["default_event_scope"], "all_published")
        self.assertEqual(settings.provider_options("f1").motorsport_view, "race_only")
        self.assertEqual(settings.providers_config["nba"]["default_event_scope"], "regular_only")
        self.assertEqual(settings.config_dir.name, "config")
