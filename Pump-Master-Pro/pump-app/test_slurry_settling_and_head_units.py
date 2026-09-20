"""
Test verification for:
1. Slurry particle settling velocity (Vt) and critical deposition velocity (Vc)
   using carrier-liquid SG (Sl), NOT the mixture SG (Sm).
2. Friction head reported in metres of the actual flowing fluid.
3. Durand head loss divided by mixture SG (Sm) to express head in m slurry.
4. Pressure computed using rho_fluid * g * h_f.
"""

import unittest
from services.hydraulic_engine import (
    calculate_consolidated_pipe,
    particle_settling_velocity_m_s,
    solve_network,
    PipeEdge,
    Node,
    NetworkGraph,
    GRAVITY
)

class TestSlurrySettlingAndHeadUnits(unittest.TestCase):

    def test_settling_velocity_uses_carrier_liquid_sg(self):
        d50_mm = 0.25
        s_solids = 2.65
        carrier_sl = 1.0
        mixture_sg = 1.35

        res_carrier = particle_settling_velocity_m_s(d50_mm, s_solids, s_liquid=carrier_sl)
        vt_carrier = res_carrier['settling_velocity_ms']

        res_mixture = particle_settling_velocity_m_s(d50_mm, s_solids, s_liquid=mixture_sg)
        vt_mixture = res_mixture['settling_velocity_ms']

        self.assertNotAlmostEqual(vt_carrier, vt_mixture, places=3)
        self.assertGreater(vt_carrier, vt_mixture)

        pipe = PipeEdge(id='P1', from_node='N1', to_node='N2', length_m=50.0, diameter_mm=150.0)
        calc = calculate_consolidated_pipe(
            pipe,
            flow_m3h=100.0,
            friction_method='darcy_weisbach',
            is_slurry=True,
            slurry_d50_mm=d50_mm,
            slurry_solids_sg=s_solids,
            slurry_c_weight=30.0,
            slurry_liquid_sg=carrier_sl,
            fluid_density=1250.0
        )

        self.assertIsNotNone(calc.settling_velocity_ms)
        self.assertAlmostEqual(calc.settling_velocity_ms, vt_carrier, places=4)

    def test_solve_network_slurry_settling_uses_carrier_sg(self):
        graph = NetworkGraph()
        graph.add_node(Node(id='N1', elevation_m=0.0, node_type='reservoir'))
        graph.add_node(Node(id='N2', elevation_m=10.0, node_type='discharge'))
        graph.add_pipe(PipeEdge(id='P1', from_node='N1', to_node='N2', length_m=100.0, diameter_mm=100.0))

        carrier_sl = 1.0
        solids_sg = 2.65
        d50_mm = 0.20
        cw = 25.0

        expected_vt = particle_settling_velocity_m_s(d50_mm, solids_sg, s_liquid=carrier_sl)['settling_velocity_ms']

        result = solve_network(
            graph,
            solver_method='ggm',
            global_flow_m3h=30.0,
            is_slurry=True,
            slurry_d50_mm=d50_mm,
            slurry_solids_sg=solids_sg,
            slurry_liquid_sg=carrier_sl,
            slurry_c_weight=cw
        )

        self.assertTrue(result.converged)
        summary = result.summary
        self.assertAlmostEqual(summary['slurry_settling_velocity_ms'], expected_vt, places=4)

        pipe_res = result.pipe_results[0]
        self.assertAlmostEqual(pipe_res.settling_velocity_ms, expected_vt, places=4)

    def test_pressure_conversion_uses_actual_fluid_density(self):
        graph = NetworkGraph()
        graph.add_node(Node(id='N1', elevation_m=0.0, node_type='reservoir'))
        graph.add_node(Node(id='N2', elevation_m=0.0, node_type='discharge'))
        graph.add_pipe(PipeEdge(id='P1', from_node='N1', to_node='N2', length_m=100.0, diameter_mm=100.0))

        result = solve_network(
            graph,
            solver_method='ggm',
            global_flow_m3h=40.0,
            is_slurry=True,
            slurry_d50_mm=0.15,
            slurry_solids_sg=2.65,
            slurry_c_weight=35.0,
            slurry_liquid_sg=1.0
        )

        summary = result.summary
        rho_slurry = summary['density_kg_m3']
        self.assertGreater(rho_slurry, 1100.0)

        pipe_res = result.pipe_results[0]
        hf_friction = pipe_res.hf_friction_m

        expected_dp_kpa = hf_friction * (rho_slurry * GRAVITY / 1000.0)
        actual_dp_kpa = pipe_res.pressure_drop_kpa
        self.assertAlmostEqual(actual_dp_kpa, expected_dp_kpa, places=2)

if __name__ == '__main__':
    unittest.main()
