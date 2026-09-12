"""Unit tests production guardrails — tanpa network."""

from __future__ import annotations

import os
import sys
import unittest

# Project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import absen_flow
from tests.fixtures_absensi import (
    HTML_NOT_OPEN,
    HTML_NOT_OPEN_WITH_STALE_BTN,
    HTML_OPEN,
    HTML_OPEN_FORM,
    HTML_UNKNOWN,
)
from tool import extract_mahasiswa, state_of


class TestStateOf(unittest.TestCase):
    def test_not_open(self):
        st, detail = state_of(HTML_NOT_OPEN)
        self.assertEqual(st, 'NOT_OPEN')
        self.assertIn('belum', detail.lower())

    def test_open_button(self):
        st, _ = state_of(HTML_OPEN)
        self.assertEqual(st, 'OPEN')

    def test_open_form(self):
        st, _ = state_of(HTML_OPEN_FORM)
        self.assertEqual(st, 'OPEN')

    def test_unknown(self):
        st, _ = state_of(HTML_UNKNOWN)
        self.assertEqual(st, 'UNKNOWN')

    def test_not_open_wins_over_stale_btn(self):
        st, _ = state_of(HTML_NOT_OPEN_WITH_STALE_BTN)
        self.assertEqual(st, 'NOT_OPEN')

    def test_extract_mahasiswa(self):
        self.assertEqual(extract_mahasiswa(HTML_NOT_OPEN), 'Athar Rayyan')


class TestAbsenFlow(unittest.TestCase):
    def test_mode_default(self):
        os.environ.pop('ABSEN_MODE', None)
        self.assertEqual(absen_flow.get_absen_mode(''), 'confirm')
        self.assertEqual(absen_flow.get_absen_mode('AUTO'), 'auto')
        self.assertEqual(absen_flow.get_absen_mode('notify_only'), 'notify_only')
        self.assertEqual(absen_flow.get_absen_mode('weird'), 'confirm')

    def test_fingerprint_stable(self):
        info = {
            'absensi': {'state': 'OPEN'},
            'jadwal_hari_ini': [
                {'kode': 'A', 'warna': 'MERAH', 'jam': '08-10', 'status_absen': 'Belum'},
            ],
        }
        self.assertEqual(
            absen_flow.fingerprint(info),
            'OPEN||A|MERAH|08-10|Belum',
        )

    def test_login_fail_alert_throttle(self):
        self.assertTrue(absen_flow.should_alert_login_fail({}, 1))
        self.assertFalse(absen_flow.should_alert_login_fail({}, 2))
        self.assertTrue(absen_flow.should_alert_login_fail({}, 6))
        self.assertTrue(absen_flow.should_alert_login_fail({}, 12))

    def test_parser_unknown_alert(self):
        self.assertTrue(
            absen_flow.should_alert_parser_unknown({'state': 'OPEN'}, 'UNKNOWN', in_window=False)
        )
        self.assertTrue(
            absen_flow.should_alert_parser_unknown({'state': 'UNKNOWN'}, 'UNKNOWN', in_window=True)
        )
        self.assertFalse(
            absen_flow.should_alert_parser_unknown({'state': 'UNKNOWN'}, 'UNKNOWN', in_window=False)
        )
        self.assertFalse(
            absen_flow.should_alert_parser_unknown({}, 'OPEN', in_window=True)
        )

    def test_merge_metrics_streaks(self):
        prev = {'login_fail_streak': 2, 'parser_unknown_streak': 1}
        m = absen_flow.merge_metrics(
            prev, login_ok=True, login_stats={'attempts': 0, 'result': 'COOKIE_OK'}, state='OPEN',
        )
        self.assertEqual(m['login_fail_streak'], 0)
        self.assertEqual(m['parser_unknown_streak'], 0)
        self.assertTrue(m['last_login_ok'])

        m2 = absen_flow.merge_metrics(
            prev, login_ok=False, login_stats={'attempts': 3, 'wrong_captcha': 3}, state='LOGIN_FAIL',
        )
        self.assertEqual(m2['login_fail_streak'], 3)


if __name__ == '__main__':
    unittest.main()
