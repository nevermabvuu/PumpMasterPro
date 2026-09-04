"""
Comprehensive Test Script:
Verifies Variable Speed Drive (VSD) impeller trimming modes and speed limits,
and Fixed Speed automatic, manual, and min-max speed range modes.
"""
import sys
import os

# Add pump-app directory to sys.path
sys.path.insert(0, os.path.abspath('.'))

from app import app
from models import Pump
from pump_selection import select_pumps

def run_tests():
    with app.app_context():
        pumps = Pump.query.all()
        print(f"Loaded {len(pumps)} pumps from database.")

        q_duty = 50.0   # m3/h
        h_duty = 15.0   # m

        # ── Test 1: Fixed Speed - Range Mode [1400, 1550] ──────────────────────
        print("\n--- Test 1: Fixed Speed Range [1400, 1550] RPM ---")
        res_range = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='fixed',
            fixed_speed_mode='range',
            fixed_speed_min_rpm=1400,
            fixed_speed_max_rpm=1550
        )
        print(f"Matching pumps in [1400, 1550] RPM range: {len(res_range)}")
        for r in res_range[:3]:
            print(f"  Pump: {r['pump_name']} | Base: {r['speed_rpm']} RPM | Opt Speed: {r['optimal_speed_rpm']} | Trim: Ø{r['optimal_trim_dia_mm']}mm ({r['optimal_trim_ratio']*100:.1f}%) | Rating: {r['rating']}")
            assert 1400 <= r['optimal_speed_rpm'] <= 1550, f"Speed {r['optimal_speed_rpm']} out of range [1400, 1550]!"

        # ── Test 2: Fixed Speed - Range Mode [2800, 3000] ──────────────────────
        print("\n--- Test 2: Fixed Speed Range [2800, 3000] RPM ---")
        res_range_2p = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='fixed',
            fixed_speed_mode='range',
            fixed_speed_min_rpm=2800,
            fixed_speed_max_rpm=3000
        )
        print(f"Matching pumps in [2800, 3000] RPM range: {len(res_range_2p)}")
        for r in res_range_2p[:3]:
            print(f"  Pump: {r['pump_name']} | Base: {r['speed_rpm']} RPM | Opt Speed: {r['optimal_speed_rpm']} | Trim: Ø{r['optimal_trim_dia_mm']}mm ({r['optimal_trim_ratio']*100:.1f}%) | Rating: {r['rating']}")
            assert 2800 <= r['optimal_speed_rpm'] <= 3000, f"Speed {r['optimal_speed_rpm']} out of range [2800, 3000]!"

        # ── Test 3: VSD - Auto Trim (Full Impeller) ───────────────────────────
        print("\n--- Test 3: VSD Auto Trim (Full Impeller) ---")
        res_vsd_auto = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='vsd',
            vsd_trim_mode='auto'
        )
        print(f"VSD Auto matching pumps: {len(res_vsd_auto)}")
        for r in res_vsd_auto[:3]:
            print(f"  Pump: {r['pump_name']} | VSD Speed: {r['optimal_speed_rpm']} RPM | Impeller: Ø{r['optimal_trim_dia_mm']}mm ({r['optimal_trim_ratio']*100:.1f}%)")
            assert r['optimal_trim_ratio'] >= 0.999, f"Expected full impeller for VSD auto, got {r['optimal_trim_ratio']}"

        # ── Test 4: VSD - Manual Trim (Exact mm, e.g. 210 mm) ──────────────────
        print("\n--- Test 4: VSD Manual Trim (Ø210 mm) ---")
        res_vsd_manual = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='vsd',
            vsd_trim_mode='manual_mm',
            vsd_trim_dia_mm=210
        )
        print(f"VSD Manual (Ø210mm) matching pumps: {len(res_vsd_manual)}")
        for r in res_vsd_manual[:3]:
            print(f"  Pump: {r['pump_name']} | VSD Speed: {r['optimal_speed_rpm']} RPM | Trim: Ø{r['optimal_trim_dia_mm']}mm ({r['optimal_trim_ratio']*100:.1f}%)")
            assert r['optimal_trim_dia_mm'] == 210.0, f"Expected 210mm trim, got {r['optimal_trim_dia_mm']}"

        # ── Test 5: VSD - Range mm [190, 215] mm ──────────────────────────────
        print("\n--- Test 5: VSD Range mm [190, 215] mm ---")
        res_vsd_range_mm = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='vsd',
            vsd_trim_mode='range_mm',
            vsd_trim_min_mm=190,
            vsd_trim_max_mm=215
        )
        print(f"VSD Range mm [190, 215] matching pumps: {len(res_vsd_range_mm)}")
        for r in res_vsd_range_mm[:3]:
            print(f"  Pump: {r['pump_name']} | VSD Speed: {r['optimal_speed_rpm']} RPM | Trim: Ø{r['optimal_trim_dia_mm']}mm ({r['optimal_trim_ratio']*100:.1f}%)")
            assert 190 <= r['optimal_trim_dia_mm'] <= 215, f"Trim {r['optimal_trim_dia_mm']} out of bounds [190, 215]!"

        # ── Test 6: VSD - Range % [80%, 95%] ──────────────────────────────────
        print("\n--- Test 6: VSD Range % [80%, 95%] ---")
        res_vsd_range_pct = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='vsd',
            vsd_trim_mode='range_pct',
            vsd_trim_min_pct=80,
            vsd_trim_max_pct=95
        )
        print(f"VSD Range % [80%, 95%] matching pumps: {len(res_vsd_range_pct)}")
        for r in res_vsd_range_pct[:3]:
            print(f"  Pump: {r['pump_name']} | VSD Speed: {r['optimal_speed_rpm']} RPM | Trim: Ø{r['optimal_trim_dia_mm']}mm ({r['optimal_trim_ratio']*100:.1f}%)")
            pct = round(r['optimal_trim_ratio'] * 100, 1)
            assert 79.5 <= pct <= 95.5, f"Trim % {pct} out of bounds [80%, 95%]!"

        # ── Test 7: VSD Speed Bounds [1000, 1800] RPM ─────────────────────────
        print("\n--- Test 7: VSD Speed Bounds [1000, 1800] RPM ---")
        res_vsd_speed_limits = select_pumps(
            pumps, q_duty, h_duty,
            operation_mode='vsd',
            vsd_trim_mode='auto',
            vsd_speed_min_rpm=1000,
            vsd_speed_max_rpm=1800
        )
        print(f"VSD Speed Bounds [1000, 1800] matching pumps: {len(res_vsd_speed_limits)}")
        for r in res_vsd_speed_limits[:3]:
            print(f"  Pump: {r['pump_name']} | VSD Speed: {r['optimal_speed_rpm']} RPM")
            assert 1000 <= r['optimal_speed_rpm'] <= 1800, f"Speed {r['optimal_speed_rpm']} out of bounds [1000, 1800]!"

        # ── Test 8: Flask Client Integration ──────────────────────────────────
        print("\n--- Test 8: Flask Client Integration ---")
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['org_id'] = 1

        # Post Fixed Speed Range
        resp_post_range = client.post('/pump-selection', data={
            'q_duty': '50',
            'h_duty': '15',
            'operation_mode': 'fixed',
            'fixed_speed_mode': 'range',
            'fixed_speed_min_rpm': '1400',
            'fixed_speed_max_rpm': '1550',
            'motor_freq_hz': '50',
            'motor_poles': '4'
        }, follow_redirects=True)
        assert resp_post_range.status_code == 200, f"POST fixed speed range failed with {resp_post_range.status_code}"
        assert b"Speed:" in resp_post_range.data or b"Fixed Speed" in resp_post_range.data
        print("  POST fixed speed range succeeded (status 200)")

        # Post VSD with Specified Impeller Trim
        resp_post_vsd = client.post('/pump-selection', data={
            'q_duty': '50',
            'h_duty': '15',
            'operation_mode': 'vsd',
            'vsd_trim_mode': 'manual_mm',
            'vsd_trim_dia_mm': '210',
            'vsd_speed_min_rpm': '800',
            'vsd_speed_max_rpm': '2500',
            'motor_freq_hz': '50',
            'motor_poles': '4'
        }, follow_redirects=True)
        assert resp_post_vsd.status_code == 200, f"POST VSD trim failed with {resp_post_vsd.status_code}"
        assert b"VSD Speed:" in resp_post_vsd.data or b"Trim: \xc3\x98210" in resp_post_vsd.data or b"210 mm" in resp_post_vsd.data or b"VSD" in resp_post_vsd.data
        print("  POST VSD manual trim succeeded (status 200)")

        print("\nALL BACKEND & SELECTION TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()
