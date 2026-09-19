"""Unit tests production guardrails — tanpa network."""

from __future__ import annotations

import os
import sys
import unittest

# Project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import absen_flow
from tests.fixtures_absensi import (
    HTML_BATAS_ACTIVE,
    HTML_BATAS_DOSEN_BELUM,
    HTML_BATAS_EXPIRED_SUDAH,
    HTML_NOT_OPEN,
    HTML_NOT_OPEN_WITH_STALE_BTN,
    HTML_OPEN,
    HTML_OPEN_FORM,
    HTML_UNKNOWN,
)
from tool import extract_mahasiswa, state_of
import absensi_meta


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


class TestBatasAbsen(unittest.TestCase):
    def test_parse_active_batas(self):
        sesi = absensi_meta.parse_sesi_absensi(HTML_BATAS_ACTIVE)
        self.assertEqual(len(sesi), 1)
        self.assertEqual(sesi[0].batas_text, '09:05')
        self.assertEqual(sesi[0].batas_menit, 9 * 60 + 5)
        self.assertFalse(sesi[0].sudah_absen)
        self.assertFalse(sesi[0].dosen_belum_absen)

    def test_within_batas_allows_button(self):
        sesi = absensi_meta.parse_sesi_absensi(HTML_BATAS_ACTIVE)
        ok, reason, target = absensi_meta.boleh_kirim_tombol_absen(
            state='OPEN', sesi_page=sesi, ada_merah_jadwal=True, now_menit=9 * 60,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, 'within_batas')
        self.assertEqual(target.batas_text, '09:05')

    def test_after_batas_no_button(self):
        sesi = absensi_meta.parse_sesi_absensi(HTML_BATAS_ACTIVE)
        ok, reason, _ = absensi_meta.boleh_kirim_tombol_absen(
            state='OPEN', sesi_page=sesi, ada_merah_jadwal=True, now_menit=9 * 60 + 43,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, 'expired')

    def test_sudah_absen_no_button(self):
        sesi = absensi_meta.parse_sesi_absensi(HTML_BATAS_EXPIRED_SUDAH)
        self.assertTrue(sesi[0].sudah_absen)
        ok, reason, _ = absensi_meta.boleh_kirim_tombol_absen(
            state='OPEN', sesi_page=sesi, ada_merah_jadwal=False, now_menit=9 * 60,
        )
        self.assertFalse(ok)
        self.assertIn(reason, ('sudah_absen', 'sudah_absen_or_belum', 'expired'))

    def test_dosen_belum(self):
        sesi = absensi_meta.parse_sesi_absensi(HTML_BATAS_DOSEN_BELUM)
        self.assertTrue(sesi[0].dosen_belum_absen)
        ok, reason, _ = absensi_meta.boleh_kirim_tombol_absen(
            state='NOT_OPEN', sesi_page=sesi, ada_merah_jadwal=False, now_menit=10 * 60,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, 'dosen_belum')
        st, detail = state_of(HTML_BATAS_DOSEN_BELUM)
        self.assertEqual(st, 'NOT_OPEN')
        self.assertIn('belum', detail.lower())

    def test_state_open_from_batas_jam(self):
        st, detail = state_of(HTML_BATAS_ACTIVE)
        self.assertEqual(st, 'OPEN')
        self.assertIn('09:05', detail)


class TestAbsenFlow(unittest.TestCase):
    def test_mode_default(self):
        os.environ.pop('ABSEN_MODE', None)
        self.assertEqual(absen_flow.get_absen_mode(''), 'confirm')
        self.assertEqual(absen_flow.get_absen_mode('AUTO'), 'auto')
        self.assertEqual(absen_flow.get_absen_mode('notify_only'), 'notify_only')
        self.assertEqual(absen_flow.get_absen_mode('weird'), 'confirm')

    def test_fingerprint_stable(self):
        info = {
            'absensi': {'state': 'OPEN', 'batas_reason': 'within_batas', 'sesi_page': []},
            'jadwal_hari_ini': [
                {'kode': 'A', 'warna': 'MERAH', 'jam': '08-10', 'status_absen': 'Belum'},
            ],
        }
        self.assertEqual(
            absen_flow.fingerprint(info),
            'OPEN||within_batas||A|MERAH|08-10|Belum',
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
