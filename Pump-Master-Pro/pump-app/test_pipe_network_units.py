"""
test_pipe_network_units.py
Comprehensive unit tests for the Pipe Network Designer engineering units system,
including:
  1. Unit conversion factors and normalization logic.
  2. Template context injection on /pipe-network.
  3. API calculation numerical consistency across flow and head unit conversions.
  4. Bidirectional state synchronization between Pump Selection and Pipe Network.
"""

import unittest
import json
from app import app
from utils import UNITS_FLOW, UNITS_HEAD, UNITS_POWER, UNITS_DENSITY, UNITS_SIZE

class TestPipeNetworkUnits(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.testing = True
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Admin'

    def test_units_tables_defined(self):
        """Verify standard unit dictionaries exist in utils with valid conversion factors."""
        self.assertIn('m3h', UNITS_FLOW)
        self.assertIn('ls', UNITS_FLOW)
        self.assertIn('gpm', UNITS_FLOW)
        self.assertIn('m', UNITS_HEAD)
        self.assertIn('ft', UNITS_HEAD)
        
        # 1 m3/h base check
        self.assertEqual(UNITS_FLOW['m3h']['factor_to_base'], 1.0)
        # 1 ft = 0.3048 m
        self.assertAlmostEqual(UNITS_HEAD['ft']['factor_to_base'], 0.3048, places=4)

    def test_pipe_network_route_context(self):
        """Verify that GET /pipe-network passes units_tables, unit_system, unit_q, unit_h."""
        with self.client.session_transaction() as sess:
            sess['unit_system'] = 'imperial'
            sess['unit_q'] = 'gpm'
            sess['unit_h'] = 'ft'

        resp = self.client.get('/pipe-network')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Verify HTML contains unit selector and modal elements
        self.assertIn('id="pn-flow-unit"', html)
        self.assertIn('id="pn-unit-preset"', html)
        self.assertIn('id="btn-units-settings"', html)
        self.assertIn('id="pn-units-modal-overlay"', html)

        # Verify template script injected window.__PMP_UNIT_Q, UNIT_H, UNIT_SYSTEM
        self.assertIn('window.__PMP_UNIT_Q = "gpm"', html)
        self.assertIn('window.__PMP_UNIT_H = "ft"', html)
        self.assertIn('window.__PMP_UNIT_SYSTEM = "imperial"', html)

    def test_calculate_api_with_units(self):
        """Verify /api/pipe-network/calculate works accurately with normalized flow values."""
        payload = {
            "flow_m3h": 25.0,
            "nodes": [
                {"id": "N-1", "type": "reservoir", "props": {"elevation_m": 0}},
                {"id": "N-2", "type": "discharge", "props": {"elevation_m": 10}}
            ],
            "pipes": [
                {
                    "id": "P-1",
                    "from_node": "N-1",
                    "to_node": "N-2",
                    "diameter_mm": 100.0,
                    "length_m": 50.0,
                    "material": "commercial_steel",
                    "elev_change_m": 10.0,
                    "fittings": []
                }
            ]
        }

        resp = self.client.post('/api/pipe-network/calculate',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('summary', data)
        self.assertIn('results', data)
        
        # 10m elevation change should produce 10m elevation head
        self.assertAlmostEqual(data['summary']['total_elevation_m'], 10.0, places=2)
        # Total system head > 10m (elevation + friction)
        self.assertGreater(data['summary']['total_system_head_m'], 10.0)

    def test_simple_calculate_npsha(self):
        """Verify /api/pipe-network/simple-calculate computes NPSHa and syncs to session."""
        payload = {
            "flow": 50.0,
            "unit_flow": "m3h",
            "unit_head": "m",
            "unit_system": "metric",
            "fluid_type": "water",
            "temp_c": 20.0,
            "sg": 1.0,
            "viscosity_cst": 1.0,
            "topology": "series",
            "apply_to_selection": True,
            "pipes": [
                {
                    "id": "pipe-suct",
                    "label": "Suction Line",
                    "length_m": 10.0,
                    "diameter_mm": 100.0,
                    "roughness_mm": 0.045,
                    "elevation_m": -1.5, # 1.5m suction lift
                    "fittings": []
                },
                {
                    "id": "pipe-disch",
                    "label": "Discharge Line",
                    "length_m": 40.0,
                    "diameter_mm": 80.0,
                    "roughness_mm": 0.045,
                    "elevation_m": 15.0,
                    "fittings": []
                }
            ]
        }

        resp = self.client.post('/api/pipe-network/simple-calculate',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        # Check NPSHa exists in response
        self.assertIn('npsha_m', data)
        self.assertIn('npsha_ft', data)
        self.assertIsNotNone(data['npsha_m'])
        self.assertGreater(data['npsha_m'], 0.0)
        self.assertIn('summary', data)
        self.assertIn('npsha_m', data['summary'])
        self.assertEqual(data['npsha_m'], data['summary']['npsha_m'])

        # For 20°C water at sea level (~10.33m atm, ~0.24m vp) with -1.5m lift and small friction,
        # NPSHa should be around 8.0 - 8.6 m
        self.assertTrue(7.0 <= data['npsha_m'] <= 9.0, f"Expected NPSHa between 7 and 9 m, got {data['npsha_m']}")

        # Verify applied_to_selection is true and session has npsh_avail
        self.assertTrue(data.get('applied_to_selection'))
        with self.client.session_transaction() as sess:
            active_sel = sess.get('active_selection', {})
            self.assertEqual(active_sel.get('npsh_avail'), data['npsha_m'])
            sel_form = sess.get('selection_form_data', {})
            self.assertEqual(sel_form.get('npsh_avail'), data['npsha_m'])

if __name__ == '__main__':
    unittest.main()
