"""
test_fluid_pipe_network_sync.py
Verify synchronization and hydraulic calculation of fluid details
(Water, Viscous fluid, Slurry) across the pipe network system.
"""
import unittest
import json
from app import app
from services.hydraulic_engine import colebrook_white_exact, solve_network

class TestFluidPipeNetworkSync(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Admin'

    def test_01_colebrook_white_exact(self):
        """Test exact Colebrook-White solver with Newton-Raphson iteration."""
        # Laminar flow (Re < 2000): f = 64 / Re
        f_lam = colebrook_white_exact(1000, 0.045, 0.1)
        self.assertAlmostEqual(f_lam, 64.0 / 1000.0, places=4)

        # Turbulent flow (Re = 10^5, smooth pipe epsilon=0): f ~ 0.018
        f_turb = colebrook_white_exact(1e5, 0.0, 0.1)
        self.assertTrue(0.017 < f_turb < 0.019)

        # Rough pipe (Re = 10^5, epsilon/D = 0.045/100 = 0.00045)
        f_rough = colebrook_white_exact(1e5, 0.045, 0.1)
        self.assertTrue(f_rough > f_turb)

    def test_02_viscous_calculation_api(self):
        """Test /api/pipe-network/calculate with viscous fluid vs clean water."""
        base_payload = {
            "flow_m3h": 50.0,
            "solver_method": "ggm",
            "friction_method": "darcy_weisbach",
            "temperature_c": 20.0,
            "specific_gravity": 1.0,
            "nodes": [
                {"id": "n1", "type": "reservoir", "props": {"elevation_m": 0, "head_m": 0}},
                {"id": "n2", "type": "discharge", "props": {"elevation_m": 0}}
            ],
            "pipes": [
                {
                    "id": "p1", "from_node": "n1", "to_node": "n2",
                    "diameter_mm": 100, "length_m": 100, "material": "commercial_steel",
                    "elev_change_m": 0, "fittings": []
                }
            ]
        }

        # 1. Clean water
        res_water = self.app.post('/api/pipe-network/calculate',
                                 data=json.dumps(base_payload),
                                 content_type='application/json')
        self.assertEqual(res_water.status_code, 200)
        data_water = json.loads(res_water.data)
        hf_water = data_water['summary']['total_hf_major_m']

        # 2. Viscous fluid (150 cSt, density 920 kg/m3, SG=0.92)
        viscous_payload = dict(base_payload)
        viscous_payload.update({
            "liquid": "viscous",
            "fluid_type": "viscous",
            "is_viscous": True,
            "viscosity_cSt": 150.0,
            "specific_gravity": 0.92,
            "fluid_ph": 6.5,
            "fluid_concentration": "100%",
            "is_hazardous": True,
            "is_flammable": False
        })
        res_visc = self.app.post('/api/pipe-network/calculate',
                                data=json.dumps(viscous_payload),
                                content_type='application/json')
        self.assertEqual(res_visc.status_code, 200)
        data_visc = json.loads(res_visc.data)
        hf_visc = data_visc['summary']['total_hf_major_m']

        print(f"hf water: {hf_water:.4f} m, hf viscous (150 cSt): {hf_visc:.4f} m")
        # Viscous head loss should be significantly higher due to higher kinematic viscosity and lower Reynolds number
        self.assertTrue(hf_visc > hf_water)
        self.assertTrue(data_visc['summary']['is_viscous'])
        self.assertEqual(data_visc['summary']['viscosity_cSt'], 150.0)
        self.assertTrue(data_visc['summary']['is_hazardous'])

    def test_03_slurry_calculation_api(self):
        """Test /api/pipe-network/calculate with slurry mixture vs clean water."""
        base_payload = {
            "flow_m3h": 50.0,
            "solver_method": "ggm",
            "friction_method": "darcy_weisbach",
            "temperature_c": 20.0,
            "specific_gravity": 1.0,
            "nodes": [
                {"id": "n1", "type": "reservoir", "props": {"elevation_m": 0, "head_m": 0}},
                {"id": "n2", "type": "discharge", "props": {"elevation_m": 0}}
            ],
            "pipes": [
                {
                    "id": "p1", "from_node": "n1", "to_node": "n2",
                    "diameter_mm": 100, "length_m": 100, "material": "commercial_steel",
                    "elev_change_m": 0, "fittings": []
                }
            ]
        }

        # Clean water
        res_water = self.app.post('/api/pipe-network/calculate',
                                 data=json.dumps(base_payload),
                                 content_type='application/json')
        data_water = json.loads(res_water.data)
        hf_water = data_water['summary']['total_hf_major_m']

        # Slurry mixture (Solids SG=2.65, Liquid SG=1.0, Cw=30%, d50=0.35 mm)
        slurry_payload = dict(base_payload)
        slurry_payload.update({
            "liquid": "slurry",
            "fluid_type": "slurry",
            "is_slurry": True,
            "slurry_liquid_sg": 1.0,
            "slurry_solids_sg": 2.65,
            "slurry_c_weight": 30.0,
            "slurry_d50_mm": 0.35
        })
        res_slurry = self.app.post('/api/pipe-network/calculate',
                                  data=json.dumps(slurry_payload),
                                  content_type='application/json')
        self.assertEqual(res_slurry.status_code, 200)
        data_slurry = json.loads(res_slurry.data)
        hf_slurry = data_slurry['summary']['total_hf_major_m']

        print(f"hf water: {hf_water:.4f} m, hf slurry: {hf_slurry:.4f} m")
        # Durand equation accounts for solids transport energy, increasing total friction head loss
        self.assertTrue(hf_slurry > hf_water)
        self.assertTrue(data_slurry['summary']['is_slurry'])
        self.assertEqual(data_slurry['summary']['slurry_d50_mm'], 0.35)
        self.assertEqual(data_slurry['summary']['slurry_c_weight'], 30.0)

    def test_04_session_fluid_synchronization(self):
        """Test fluid parameters entered on pump selection propagate into pipe network page context."""
        # 1. Post selection with viscous fluid
        visc_form = {
            "flow": "65",
            "unit_flow": "m3h",
            "head": "25",
            "unit_head": "m",
            "liquid": "viscous",
            "rho": "930",
            "viscosity_cSt": "85",
            "fluid_ph": "8.2",
            "fluid_concentration": "40 wt%",
            "is_hazardous": "1",
            "is_flammable": "1"
        }
        resp = self.app.post('/pump-selection', data=visc_form, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # 2. Get /pipe-network and verify fluid metadata in rendered page
        resp_pn = self.app.get('/pipe-network')
        self.assertEqual(resp_pn.status_code, 200)
        html = resp_pn.data.decode('utf-8')
        self.assertIn('viscous', html)
        self.assertIn('85', html)
        self.assertIn('930', html)

if __name__ == '__main__':
    unittest.main()
