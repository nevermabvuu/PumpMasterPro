"""
test_pipe_network_connectivity.py
Unit tests verifying that the Pipe Network Designer prevents calculation when any
member (node or pipe) is not connected to a complete, valid network line.

Hydraulic Engineering Rationale:
--------------------------------
1. Continuity & Conservation of Mass:
   Steady-state fluid simulation (Darcy-Weisbach / Hazen-Williams) requires a complete
   hydraulic circuit connecting an inflow boundary (Reservoir/Tank) to an outflow boundary
   (Discharge/Tank). Disconnected members have indeterminate boundary pressures.
2. Solver Stability:
   Network analysis methods (Global Gradient Method / EPANET, Newton-Raphson, Hardy Cross)
   require non-singular conductance matrices. Disconnected members and floating subgraphs
   introduce zero-flow equations and singular rows that cause solver divergence.
"""

import unittest
import json
from app import app
from services.hydraulic_engine import NetworkGraph, Node, PipeEdge

class TestPipeNetworkConnectivity(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.testing = True
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Admin'

    def test_01_complete_network_line_succeeds(self):
        """A complete, continuous network line (Reservoir -> Pump -> Discharge) must calculate successfully (HTTP 200)."""
        payload = {
            "flow_m3h": 20.0,
            "nodes": [
                {"id": "N-1", "type": "reservoir", "props": {"elevation_m": 0, "label": "Sump"}},
                {"id": "N-2", "type": "pump", "props": {"elevation_m": 0, "label": "Main Pump"}},
                {"id": "N-3", "type": "discharge", "props": {"elevation_m": 15, "label": "Storage Discharge"}}
            ],
            "pipes": [
                {
                    "id": "P-1", "from_node": "N-1", "to_node": "N-2",
                    "diameter_mm": 125.0, "length_m": 5.0, "material": "commercial_steel",
                    "elev_change_m": 0, "fittings": []
                },
                {
                    "id": "P-2", "from_node": "N-2", "to_node": "N-3",
                    "diameter_mm": 100.0, "length_m": 25.0, "material": "commercial_steel",
                    "elev_change_m": 15.0, "fittings": []
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
        self.assertGreater(data['summary']['total_system_head_m'], 15.0)

    def test_02_isolated_orphan_node_blocks_calculation(self):
        """If an isolated node (degree 0) exists on canvas, calculation must be blocked (HTTP 400)."""
        payload = {
            "flow_m3h": 20.0,
            "nodes": [
                {"id": "N-1", "type": "reservoir", "props": {"elevation_m": 0, "label": "Sump"}},
                {"id": "N-2", "type": "discharge", "props": {"elevation_m": 10, "label": "Discharge"}},
                {"id": "N-3", "type": "tank", "props": {"elevation_m": 5, "label": "Floating Tank"}}  # Orphan!
            ],
            "pipes": [
                {
                    "id": "P-1", "from_node": "N-1", "to_node": "N-2",
                    "diameter_mm": 100.0, "length_m": 20.0, "material": "commercial_steel",
                    "elev_change_m": 10, "fittings": []
                }
            ]
        }
        resp = self.client.post('/api/pipe-network/calculate',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('Floating Tank', data['error'])
        self.assertIn('not connected to any pipe line', data['error'])
        self.assertIn('N-3', data['disconnected_members']['node_ids'])

    def test_03_disconnected_pipe_endpoint_blocks_calculation(self):
        """If a pipe has an invalid or missing endpoint node, calculation must be blocked (HTTP 400)."""
        payload = {
            "flow_m3h": 20.0,
            "nodes": [
                {"id": "N-1", "type": "reservoir", "props": {"elevation_m": 0, "label": "Sump"}},
                {"id": "N-2", "type": "discharge", "props": {"elevation_m": 10, "label": "Discharge"}}
            ],
            "pipes": [
                {
                    "id": "P-1", "from_node": "N-1", "to_node": "N-NONEXISTENT",
                    "diameter_mm": 100.0, "length_m": 20.0, "material": "commercial_steel",
                    "elev_change_m": 0, "fittings": []
                }
            ]
        }
        resp = self.client.post('/api/pipe-network/calculate',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('disconnected endpoint', data['error'].lower())
        self.assertIn('P-1', data['disconnected_members']['pipe_ids'])

    def test_04_incomplete_pump_connection_blocks_calculation(self):
        """A pump node must have both suction and discharge connections (degree >= 2). A dangling pump must block calculation."""
        payload = {
            "flow_m3h": 20.0,
            "nodes": [
                {"id": "N-1", "type": "reservoir", "props": {"elevation_m": 0, "label": "Sump"}},
                {"id": "N-2", "type": "pump", "props": {"elevation_m": 0, "label": "Booster Pump"}}  # Dangling pump, no discharge pipe
            ],
            "pipes": [
                {
                    "id": "P-1", "from_node": "N-1", "to_node": "N-2",
                    "diameter_mm": 100.0, "length_m": 10.0, "material": "commercial_steel",
                    "elev_change_m": 0, "fittings": []
                }
            ]
        }
        resp = self.client.post('/api/pipe-network/calculate',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('Booster Pump', data['error'])
        self.assertIn('requires both suction', data['error'])
        self.assertIn('N-2', data['disconnected_members']['node_ids'])

    def test_05_disconnected_components_blocks_calculation(self):
        """If there are separate disconnected network lines/islands, calculation must be blocked (HTTP 400)."""
        payload = {
            "flow_m3h": 20.0,
            "nodes": [
                # Main continuous line: N-1 -> P-1 -> N-2
                {"id": "N-1", "type": "reservoir", "props": {"elevation_m": 0, "label": "Sump 1"}},
                {"id": "N-2", "type": "discharge", "props": {"elevation_m": 10, "label": "Discharge 1"}},
                # Disconnected floating line: N-3 -> P-2 -> N-4
                {"id": "N-3", "type": "tank", "props": {"elevation_m": 0, "label": "Tank 2"}},
                {"id": "N-4", "type": "discharge", "props": {"elevation_m": 10, "label": "Discharge 2"}}
            ],
            "pipes": [
                {
                    "id": "P-1", "from_node": "N-1", "to_node": "N-2",
                    "diameter_mm": 100.0, "length_m": 20.0, "material": "commercial_steel",
                    "elev_change_m": 10, "fittings": []
                },
                {
                    "id": "P-2", "from_node": "N-3", "to_node": "N-4",
                    "diameter_mm": 100.0, "length_m": 10.0, "material": "commercial_steel",
                    "elev_change_m": 0, "fittings": []
                }
            ]
        }
        resp = self.client.post('/api/pipe-network/calculate',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn('disconnected members', data['error'].lower())
        self.assertIn('P-2', data['disconnected_members']['pipe_ids'])

    def test_06_missing_source_blocks_calculation(self):
        """A network with no fluid source (no Reservoir or Tank) must block calculation (HTTP 400)."""
        payload = {
            "flow_m3h": 20.0,
            "nodes": [
                {"id": "N-1", "type": "junction", "props": {"elevation_m": 0, "label": "Junction 1"}},
                {"id": "N-2", "type": "discharge", "props": {"elevation_m": 10, "label": "Discharge"}}
            ],
            "pipes": [
                {"id": "P-1", "from_node": "N-1", "to_node": "N-2", "diameter_mm": 100, "length_m": 10, "material": "commercial_steel", "elev_change_m": 10, "fittings": []}
            ]
        }
        resp = self.client.post('/api/pipe-network/calculate',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        # Either dead-end junction or missing fluid source
        self.assertTrue('source' in data['error'].lower() or 'junction' in data['error'].lower())

    def test_07_missing_destination_blocks_calculation(self):
        """A network with no fluid outlet (no Discharge or Tank) must block calculation (HTTP 400)."""
        payload = {
            "flow_m3h": 20.0,
            "nodes": [
                {"id": "N-1", "type": "reservoir", "props": {"elevation_m": 0, "label": "Sump"}},
                {"id": "N-2", "type": "junction", "props": {"elevation_m": 5, "label": "Junction 1"}}
            ],
            "pipes": [
                {"id": "P-1", "from_node": "N-1", "to_node": "N-2", "diameter_mm": 100, "length_m": 10, "material": "commercial_steel", "elev_change_m": 5, "fittings": []}
            ]
        }
        resp = self.client.post('/api/pipe-network/calculate',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertTrue('outlet' in data['error'].lower() or 'dead-end' in data['error'].lower())

if __name__ == '__main__':
    unittest.main()
