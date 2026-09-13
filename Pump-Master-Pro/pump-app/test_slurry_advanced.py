import unittest
from app import app

class TestSlurryAndAdvancedFeatures(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Admin'

    def test_slurry_and_custom_pipe_mechanics(self):
        payload = {
            "flow_m3h": 60.0,
            "solver_method": "ggm",
            "friction_method": "darcy_weisbach",
            "altitude_m": 1200.0,
            "barometric_pressure_kpa": 87.5,
            "temperature_c": 35.0,
            "vapor_pressure_kpa": 5.62,
            "specific_gravity": 1.15,
            "is_slurry": True,
            "slurry_d50_mm": 0.25,
            "slurry_solids_sg": 2.70,
            "slurry_c_weight": 30.0,
            "nodes": [
                {"id": "N-1", "type": "reservoir", "x": 100, "y": 200, "props": {"label": "Slurry Sump", "elevation_m": 0}},
                {"id": "N-2", "type": "discharge", "x": 500, "y": 200, "props": {"label": "Cyclone Feed", "elevation_m": 15}}
            ],
            "pipes": [
                {
                    "id": "P-1",
                    "from_node": "N-1",
                    "to_node": "N-2",
                    "label": "Slurry Feed Line",
                    "diameter_mm": 100.0,
                    "length_m": 80.0,
                    "material": "commercial_steel",
                    "elev_change_m": 15.0,
                    "fittings": [],
                    "custom_roughness_mm": 0.065,
                    "custom_hazen_c": 110,
                    "wall_thickness_mm": 6.02
                }
            ]
        }

        resp = self.client.post('/api/pipe-network/calculate', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('summary', data)
        self.assertIn('results', data)
        
        summary = data['summary']
        self.assertTrue(summary['is_slurry'])
        self.assertEqual(summary['vapor_pressure_kpa'], 5.62)
        self.assertIsNotNone(summary['slurry_settling_velocity_ms'])
        self.assertGreater(summary['slurry_settling_velocity_ms'], 0.0)
        self.assertIsNotNone(summary['slurry_c_volume'])
        print(f"\n[Test Slurry Summary] Settling Vt={summary['slurry_settling_velocity_ms']} m/s, Cv={summary['slurry_c_volume']}%")

        res = data['results'][0]
        self.assertIn('critical_velocity_ms', res)
        self.assertIn('deposition_status', res)
        self.assertGreater(res['critical_velocity_ms'], 0.0)
        self.assertGreater(res['wave_speed_ms'], 500)
        self.assertGreater(res['surge_pressure_kpa'], 0)
        print(f"[Water Hammer] Wave speed={res['wave_speed_ms']} m/s, Surge={res['surge_pressure_kpa']} kPa")

        self.assertIn('hoop_stress_mpa', res)
        self.assertIn('stress_safety_factor', res)
        print(f"[Barlow Stress] Hoop={res['hoop_stress_mpa']} MPa, SF={res['stress_safety_factor']}")

if __name__ == '__main__':
    unittest.main()
