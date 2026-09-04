from app import app
from models import Pump
from pump_selection import select_pumps

with app.app_context():
    pumps = Pump.query.all()
    print("Testing select_pumps with manual speed 1450:")
    res = select_pumps(pumps, 50, 15, operation_mode='fixed', fixed_speed_mode='manual', manual_pump_speed_rpm=1450)
    for r in res:
        print(f"Name: {r['pump_name']}")
        print(f"  optimal_speed_rpm: {r.get('optimal_speed_rpm')}")
        print(f"  speed_rpm: {r.get('speed_rpm')}")
        print(f"  optimal_trim_dia_mm: {r.get('optimal_trim_dia_mm')}")
        print(f"  optimal_trim_ratio: {r.get('optimal_trim_ratio')}")
        print(f"  fixed_speed_mode: {r.get('fixed_speed_mode')}")
        if r.get('motor'):
            print(f"  Motor rated speed: {r['motor'].get('rated_speed_rpm')}")
            print(f"  Motor pump req speed: {r['motor'].get('pump_required_speed_rpm')}")
            print(f"  Motor match: {r['motor'].get('speed_match_status')}")
            print(f"  Motor message: {r['motor'].get('match_message')}")
