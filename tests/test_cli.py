import unittest

from sportsbro.cli import build_parser


class CliTests(unittest.TestCase):
    def test_public_commands_match_the_static_calendar_scope(self) -> None:
        parser = build_parser()
        fetch = parser.parse_args(["fetch", "f1", "--motorsport-view", "full_weekend"])
        export = parser.parse_args(["export-web", "--season", "2026"])

        self.assertEqual(fetch.motorsport_view, "full_weekend")
        self.assertEqual(export.command, "export-web")
        with self.assertRaises(SystemExit):
            parser.parse_args(["refresh-results"])
