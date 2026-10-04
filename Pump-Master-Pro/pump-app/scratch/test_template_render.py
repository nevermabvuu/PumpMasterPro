import jinja2

env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'))
env.globals['url_for'] = lambda *a, **k: '#'

report = type('Report', (), {
    'title': 'Test Report',
    'report_name': 'standard',
    'primary_color': '#1e3a8a',
    'show_head_flow_graph': True,
    'show_additional_graphs': False,
    'show_efficiency_graph': False,
    'show_power_graph': False,
    'show_npsh_graph': False,
    'show_rated_curve': True,
    'show_duty_point': True,
    'show_materials_table': True,
    'show_extended_specs': False,
    'show_notes': False,
    'header_text': 'HEADER',
    'footer_text': 'FOOTER',
    'supplier': None
})()

pump = type('Pump', (), {
    'name': 'Test Fire Pump',
    'manufacturer': 'Lytrose',
    'model_number': 'FP-100',
    'size': '100-250',
    'speed_rpm': 2950,
    'impeller_dia_mm': 250,
    'impeller_material': 'Bronze',
    'casing_material': 'Ductile Iron',
    'suction_size': '150',
    'discharge_size': '100',
    'unit_suction': 'mm',
    'unit_discharge': 'mm'
})()

tmpl = env.get_template('reports/standard_datasheet.html')

# Case 1: Minimal fire_data (rec_driver_kw is intentionally omitted)
ctx1 = {
    'is_fire': True,
    'is_proposal': False,
    'rep_unit_q': 'm3h',
    'rep_unit_h': 'm',
    'rep_unit_pow': 'kW',
    'rep_unit_npsh': 'm',
    'svg_hq': '<svg></svg>',
    'ordered_graphs': [],
    'fire_data': {
        'is_fire': True,
        'q_duty': 100.0,
        'h_duty': 60.0,
        'h_churn': 75.0,
        'max_churn_limit': 84.0,
        'q_150': 150.0,
        'h_150': 45.0,
        'min_overload_limit': 39.0,
        'churn_pct': 125.0,
        'h_150_pct': 75.0
    }
}

out1 = tmpl.render(
    report=report, pump=pump, supplier=None, current_date='October 04, 2026',
    curves=ctx1, is_pdf_export=False
)
assert 'Key NFPA 20 Requirements' in out1
print('Test Case 1 Passed: Rendered without rec_driver_kw without throwing UndefinedError!')

# Case 2: Full enriched fire_data
ctx1['fire_data']['rec_driver_kw'] = 45.0
ctx1['fire_data']['rec_driver_hp'] = 60.0
ctx1['fire_data']['relief_valve_size'] = '3/4" NPT'
ctx1['fire_data']['p_churn_bar'] = 7.35
ctx1['fire_data']['p_churn_psi'] = 106.6
ctx1['fire_data']['jockey_start_bar'] = 6.65
ctx1['fire_data']['jockey_stop_bar'] = 7.35
ctx1['fire_data']['fire_start_bar'] = 6.30
ctx1['fire_data']['fire_start_psi'] = 91.6
ctx1['fire_data']['schedule'] = [
    {'letter': 'A', 'point': 'Shutoff', 'flow_pct': 0, 'q': 0, 'h': 75.0, 'p_bar': 7.35, 'p_psi': 106.6, 'h_pct': 125, 'limit_text': '<= 140%', 'power': 5.0, 'eff': 0, 'npsh': None, 'pass': True, 'status': 'PASS'}
]

out2 = tmpl.render(
    report=report, pump=pump, supplier=None, current_date='October 04, 2026',
    curves=ctx1, is_pdf_export=False
)
assert 'NFPA 20 Performance' in out2
assert 'Non-Overload Driver Sizing' in out2
print('Test Case 2 Passed: Rendered successfully with full enriched fire_data!')

print('ALL TEMPLATE VERIFICATIONS PASSED!')
