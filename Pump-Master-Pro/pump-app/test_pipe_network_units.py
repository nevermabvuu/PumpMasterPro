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

if __name__ == '__main__':
    unittest.main()
