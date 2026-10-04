"""
services/fire_protection.py — Fire Protection Hydraulic Engine & Pump Sizing Service.

Provides:
  1. Standards & Code Sizing Criteria:
     - NFPA 20 (2022/2025): Standard for the Installation of Stationary Pumps for Fire Protection.
     - NFPA 13 (2022/2025): Standard for the Installation of Sprinkler Systems (Density/Area Method).
     - NFPA 14 (2023): Standard for the Installation of Standpipe and Hose Systems (Class I, II, III).
     - EN 12845:2015+A1:2020: Fixed firefighting systems - Automatic sprinkler systems (LPC Rules).
     - AS 2941-2013: Fixed fire protection installations - Pumpset systems (Australia).
     - AS 2419.1:2021: Fire hydrant installations - System design and commissioning.

  2. System Hydraulic Demand Calculations:
     - Sprinkler demand from design density and operating design area.
     - Interior & exterior hose stream allowances.
     - Total dynamic head (TDH): static elevation head, piping friction loss, and residual nozzle pressure.
     - NFPA 20 150% overload flow and minimum head requirements.
     - NFPA 20 maximum shutoff churn head limits.

  3. Auxiliary System Sizing:
     - Jockey Pump (Pressure Maintenance Pump) capacity, rated head, and start/stop pressure switch settings.
     - Fire Water Storage Tank sizing (effective duration and required reserve capacity in m³ and US gallons).
     - NFPA 20 Table 4.27 Pipe Sizing (minimum suction pipe, discharge pipe, relief valve, flow meter line).

  4. Pump NFPA 20 Characteristic Curve Compliance Evaluation:
     - Evaluates pump H-Q curve at 0% flow (churn <= 140%), 100% flow (head >= 100%), and 150% flow (head >= 65%).
     - Driver power sizing: non-overloading across full operating curve or rated for maximum pump load.
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple, Any

# Standard Conversion Factors
GPM_TO_M3H = 0.22712470704     # 1 US GPM = 0.2271247 m³/h
M3H_TO_GPM = 1.0 / GPM_TO_M3H  # 1 m³/h = 4.4028675 US GPM
PSI_TO_M = 0.703069578         # 1 PSI of water head = 0.70307 m
M_TO_PSI = 1.0 / PSI_TO_M      # 1 m of water head = 1.42233 PSI
BAR_TO_M = 10.197162           # 1 bar = 10.197 m of water head
M_TO_BAR = 1.0 / BAR_TO_M      # 1 m = 0.0980665 bar
M3_TO_US_GAL = 264.172         # 1 m³ = 264.172 US gallons
US_GAL_TO_M3 = 1.0 / M3_TO_US_GAL
LMIN_TO_M3H = 0.06             # 1 L/min = 0.06 m³/h
M3H_TO_LMIN = 1.0 / LMIN_TO_M3H
KW_TO_HP = 1.34102             # 1 kW = 1.34102 HP
HP_TO_KW = 0.745699872         # 1 HP = 0.7457 kW


# ============================================================================
# STANDARDS REFERENCE DATA & HAZARD PROFILES
# ============================================================================

# 1. NFPA 13 Sprinkler Hazard Classifications
NFPA_13_HAZARDS: Dict[str, Dict[str, Any]] = {
    'light_hazard': {
        'code': 'light_hazard',
        'name': 'Light Hazard (LH)',
        'description': 'Offices, schools, hospitals, residential, churches, museum galleries (low combustibility).',
        'density_gpm_ft2': 0.10,
        'density_mm_min': 4.1,
        'area_ft2': 1500,
        'area_m2': 139.35,
        'hose_stream_gpm': 100,
        'hose_stream_m3h': 22.7,
        'duration_min': 30,
        'min_residual_psi': 7.0,   # Standard minimum sprinkler head pressure
        'min_residual_bar': 0.48,
    },
    'ordinary_hazard_1': {
        'code': 'ordinary_hazard_1',
        'name': 'Ordinary Hazard Group 1 (OH1)',
        'description': 'Parking garages, bakeries, electronic plants, laundries, restaurant service areas.',
        'density_gpm_ft2': 0.15,
        'density_mm_min': 6.1,
        'area_ft2': 1500,
        'area_m2': 139.35,
        'hose_stream_gpm': 250,
        'hose_stream_m3h': 56.8,
        'duration_min': 60,
        'min_residual_psi': 10.0,
        'min_residual_bar': 0.69,
    },
    'ordinary_hazard_2': {
        'code': 'ordinary_hazard_2',
        'name': 'Ordinary Hazard Group 2 (OH2)',
        'description': 'Woodworking, machine shops, printing, mercantile, warehouses with storage <= 12 ft.',
        'density_gpm_ft2': 0.20,
        'density_mm_min': 8.2,
        'area_ft2': 1500,
        'area_m2': 139.35,
        'hose_stream_gpm': 250,
        'hose_stream_m3h': 56.8,
        'duration_min': 90,
        'min_residual_psi': 15.0,
        'min_residual_bar': 1.03,
    },
    'extra_hazard_1': {
        'code': 'extra_hazard_1',
        'name': 'Extra Hazard Group 1 (EH1)',
        'description': 'Aircraft hangars, sawmills, die-casting, combustible hydraulic fluid areas.',
        'density_gpm_ft2': 0.30,
        'density_mm_min': 12.2,
        'area_ft2': 2500,
        'area_m2': 232.25,
        'hose_stream_gpm': 500,
        'hose_stream_m3h': 113.6,
        'duration_min': 90,
        'min_residual_psi': 20.0,
        'min_residual_bar': 1.38,
    },
    'extra_hazard_2': {
        'code': 'extra_hazard_2',
        'name': 'Extra Hazard Group 2 (EH2)',
        'description': 'Flammable liquid handling, plastics processing, solvent cleaning, asphalt saturating.',
        'density_gpm_ft2': 0.40,
        'density_mm_min': 16.3,
        'area_ft2': 2500,
        'area_m2': 232.25,
        'hose_stream_gpm': 500,
        'hose_stream_m3h': 113.6,
        'duration_min': 120,
        'min_residual_psi': 25.0,
        'min_residual_bar': 1.72,
    },
    'esfr_storage': {
        'code': 'esfr_storage',
        'name': 'High-Bay Storage / ESFR (K-14 / K-25)',
        'description': 'High-piled rack storage requiring 12 ESFR heads operating at 50-75 psi.',
        'fixed_sprinkler_gpm': 1200,
        'fixed_sprinkler_m3h': 272.5,
        'hose_stream_gpm': 250,
        'hose_stream_m3h': 56.8,
        'duration_min': 60,
        'min_residual_psi': 65.0,
        'min_residual_bar': 4.48,
    }
}

# 2. NFPA 14 Standpipe & Hose System Classifications
NFPA_14_STANDPIPE: Dict[str, Dict[str, Any]] = {
    'class_1': {
        'code': 'class_1',
        'name': 'Class I Standpipe (2.5" / 65mm Firefighter Outlets)',
        'description': '500 gpm for the 1st riser + 250 gpm for each additional riser (max 1000 gpm non-sprinklered / 1250 gpm sprinklered). 100 psi residual at roof/highest outlet.',
        'first_riser_gpm': 500,
        'add_riser_gpm': 250,
        'max_sprinklered_gpm': 1250,
        'max_nonsprinklered_gpm': 1000,
        'min_residual_psi': 100.0,
        'min_residual_bar': 6.89,
        'duration_min': 30,
    },
    'class_2': {
        'code': 'class_2',
        'name': 'Class II Standpipe (1.5" / 38mm First-Aid Hose Stations)',
        'description': '100 gpm for building occupants at 65 psi minimum residual pressure at the hydraulically most remote outlet.',
        'fixed_flow_gpm': 100,
        'fixed_flow_m3h': 22.7,
        'min_residual_psi': 65.0,
        'min_residual_bar': 4.48,
        'duration_min': 30,
    },
    'class_3': {
        'code': 'class_3',
        'name': 'Class III Standpipe (Combined 2.5" and 1.5" Hose Outlets)',
        'description': 'Combined system: 500 gpm for first riser + 250 gpm per additional riser at 100 psi residual pressure.',
        'first_riser_gpm': 500,
        'add_riser_gpm': 250,
        'max_sprinklered_gpm': 1250,
        'max_nonsprinklered_gpm': 1000,
        'min_residual_psi': 100.0,
        'min_residual_bar': 6.89,
        'duration_min': 30,
    }
}

# 3. EN 12845 / LPC Sprinkler Hazard Classifications (Europe / UK)
EN_12845_HAZARDS: Dict[str, Dict[str, Any]] = {
    'en_lh': {
        'code': 'en_lh',
        'name': 'Light Hazard (LH)',
        'description': 'Low fire load, e.g. schools, prisons, offices, hospitals.',
        'design_density_mm_min': 2.25,
        'design_area_m2': 84.0,
        'nominal_flow_lmin': 225.0,
        'nominal_flow_m3h': 13.5,
        'nominal_head_bar': 1.5,
        'duration_min': 30,
    },
    'en_oh1': {
        'code': 'en_oh1',
        'name': 'Ordinary Hazard Group 1 (OH1)',
        'description': 'Hotels, libraries, restaurants, hospitals (low hazard processing).',
        'design_density_mm_min': 5.0,
        'design_area_m2': 72.0,
        'nominal_flow_lmin': 1000.0,
        'nominal_flow_m3h': 60.0,
        'nominal_head_bar': 1.5,
        'duration_min': 60,
    },
    'en_oh2': {
        'code': 'en_oh2',
        'name': 'Ordinary Hazard Group 2 (OH2)',
        'description': 'Car workshops, bakeries, chemical labs, breweries.',
        'design_density_mm_min': 5.0,
        'design_area_m2': 144.0,
        'nominal_flow_lmin': 1400.0,
        'nominal_flow_m3h': 84.0,
        'nominal_head_bar': 2.0,
        'duration_min': 60,
    },
    'en_oh3': {
        'code': 'en_oh3',
        'name': 'Ordinary Hazard Group 3 (OH3)',
        'description': 'Woodworking, printing, paper processing, textile mills.',
        'design_density_mm_min': 5.0,
        'design_area_m2': 216.0,
        'nominal_flow_lmin': 1800.0,
        'nominal_flow_m3h': 108.0,
        'nominal_head_bar': 2.5,
        'duration_min': 60,
    },
    'en_oh4': {
        'code': 'en_oh4',
        'name': 'Ordinary Hazard Group 4 (OH4)',
        'description': 'Cinemas, theatres, exhibition halls with higher combustible content.',
        'design_density_mm_min': 5.0,
        'design_area_m2': 360.0,
        'nominal_flow_lmin': 2200.0,
        'nominal_flow_m3h': 132.0,
        'nominal_head_bar': 2.8,
        'duration_min': 60,
    },
    'en_hhp': {
        'code': 'en_hhp',
        'name': 'High Hazard Process (HHP)',
        'description': 'Chemical works, resin distillation, paint manufacturing, foam storage.',
        'design_density_mm_min': 10.0,
        'design_area_m2': 260.0,
        'nominal_flow_lmin': 3000.0,
        'nominal_flow_m3h': 180.0,
        'nominal_head_bar': 3.5,
        'duration_min': 90,
    }
}

# 4. AS 2941 / AS 2419 (Australian Fire Protection Standards)
AS_2941_CRITERIA: Dict[str, Dict[str, Any]] = {
    'as_sprinkler_light': {
        'code': 'as_sprinkler_light',
        'name': 'AS 2118 Light Hazard Sprinkler',
        'flow_lmin': 500.0,
        'flow_m3h': 30.0,
        'head_kpa': 400.0,
        'duration_min': 30,
        'description': 'Standard Australian light hazard commercial/residential sprinkler.'
    },
    'as_sprinkler_ordinary': {
        'code': 'as_sprinkler_ordinary',
        'name': 'AS 2118 Ordinary Hazard Sprinkler',
        'flow_lmin': 1500.0,
        'flow_m3h': 90.0,
        'head_kpa': 600.0,
        'duration_min': 60,
        'description': 'Commercial warehouses and manufacturing facilities.'
    },
    'as_hydrant_single': {
        'code': 'as_hydrant_single',
        'name': 'AS 2419.1 Single Hydrant Attack (10 L/s)',
        'flow_lmin': 600.0,
        'flow_m3h': 36.0,
        'head_kpa': 700.0,  # 700 kPa minimum residual at most disadvantaged hydrant
        'duration_min': 120,
        'description': 'Single internal or external fire hydrant outlet (10 L/s @ 700 kPa).'
    },
    'as_hydrant_dual': {
        'code': 'as_hydrant_dual',
        'name': 'AS 2419.1 Dual Hydrant Attack (20 L/s)',
        'flow_lmin': 1200.0,
        'flow_m3h': 72.0,
        'head_kpa': 700.0,
        'duration_min': 120,
        'description': 'Two concurrent hydrant outlets (20 L/s @ 700 kPa).'
    },
    'as_hydrant_triple': {
        'code': 'as_hydrant_triple',
        'name': 'AS 2419.1 Triple Hydrant Attack (30 L/s)',
        'flow_lmin': 1800.0,
        'flow_m3h': 108.0,
        'head_kpa': 700.0,
        'duration_min': 240,
        'description': 'Large industrial / chemical complex hydrant system (30 L/s @ 700 kPa).'
    }
}

# 5. NFPA 20 Table 4.27 Summary Pipe and Auxiliary Sizing Reference
# Maps Rated Pump GPM -> (Min Suction Size in, Min Discharge Size in, Relief Valve in, Meter in, Hose Valves 2.5")
NFPA_20_PIPE_SCHEDULE: List[Dict[str, Any]] = [
    {'gpm': 25,   'm3h': 5.7,   'suction_in': 1.0,  'discharge_in': 1.0,  'relief_in': 0.75, 'meter_in': 1.25, 'hose_valves': 0},
    {'gpm': 50,   'm3h': 11.4,  'suction_in': 1.5,  'discharge_in': 1.5,  'relief_in': 1.25, 'meter_in': 1.5,  'hose_valves': 0},
    {'gpm': 100,  'm3h': 22.7,  'suction_in': 2.0,  'discharge_in': 2.0,  'relief_in': 1.5,  'meter_in': 2.0,  'hose_valves': 0},
    {'gpm': 150,  'm3h': 34.1,  'suction_in': 2.5,  'discharge_in': 2.5,  'relief_in': 2.0,  'meter_in': 2.5,  'hose_valves': 1},
    {'gpm': 200,  'm3h': 45.4,  'suction_in': 3.0,  'discharge_in': 2.5,  'relief_in': 2.0,  'meter_in': 2.5,  'hose_valves': 1},
    {'gpm': 250,  'm3h': 56.8,  'suction_in': 3.5,  'discharge_in': 3.0,  'relief_in': 2.0,  'meter_in': 3.5,  'hose_valves': 1},
    {'gpm': 300,  'm3h': 68.1,  'suction_in': 4.0,  'discharge_in': 3.0,  'relief_in': 2.0,  'meter_in': 3.5,  'hose_valves': 1},
    {'gpm': 400,  'm3h': 90.9,  'suction_in': 4.0,  'discharge_in': 4.0,  'relief_in': 2.5,  'meter_in': 4.0,  'hose_valves': 1},
    {'gpm': 450,  'm3h': 102.2, 'suction_in': 5.0,  'discharge_in': 4.0,  'relief_in': 2.5,  'meter_in': 4.0,  'hose_valves': 1},
    {'gpm': 500,  'm3h': 113.6, 'suction_in': 5.0,  'discharge_in': 5.0,  'relief_in': 3.0,  'meter_in': 5.0,  'hose_valves': 2},
    {'gpm': 750,  'm3h': 170.3, 'suction_in': 6.0,  'discharge_in': 6.0,  'relief_in': 3.0,  'meter_in': 5.0,  'hose_valves': 3},
    {'gpm': 1000, 'm3h': 227.1, 'suction_in': 8.0,  'discharge_in': 6.0,  'relief_in': 4.0,  'meter_in': 6.0,  'hose_valves': 4},
    {'gpm': 1250, 'm3h': 283.9, 'suction_in': 8.0,  'discharge_in': 8.0,  'relief_in': 4.0,  'meter_in': 6.0,  'hose_valves': 6},
    {'gpm': 1500, 'm3h': 340.7, 'suction_in': 8.0,  'discharge_in': 8.0,  'relief_in': 6.0,  'meter_in': 8.0,  'hose_valves': 6},
    {'gpm': 2000, 'm3h': 454.2, 'suction_in': 10.0, 'discharge_in': 10.0, 'relief_in': 6.0,  'meter_in': 8.0,  'hose_valves': 6},
    {'gpm': 2500, 'm3h': 567.8, 'suction_in': 10.0, 'discharge_in': 10.0, 'relief_in': 6.0,  'meter_in': 8.0,  'hose_valves': 8},
    {'gpm': 3000, 'm3h': 681.4, 'suction_in': 12.0, 'discharge_in': 12.0, 'relief_in': 8.0,  'meter_in': 8.0,  'hose_valves': 12},
    {'gpm': 4000, 'm3h': 908.5, 'suction_in': 14.0, 'discharge_in': 12.0, 'relief_in': 8.0,  'meter_in': 10.0, 'hose_valves': 16},
    {'gpm': 5000, 'm3h': 1135.6,'suction_in': 16.0, 'discharge_in': 14.0, 'relief_in': 8.0,  'meter_in': 12.0, 'hose_valves': 20},
]


def get_nfpa20_pipe_sizes(flow_gpm: float) -> Dict[str, Any]:
    """
    Looks up the nearest standard NFPA 20 Table 4.27 pipe and valve sizes
    for a given rated fire pump flow rate (GPM).
    """
    for entry in NFPA_20_PIPE_SCHEDULE:
        if flow_gpm <= entry['gpm']:
            return {
                'rated_gpm': entry['gpm'],
                'suction_in': entry['suction_in'],
                'suction_mm': round(entry['suction_in'] * 25.4, 0),
                'discharge_in': entry['discharge_in'],
                'discharge_mm': round(entry['discharge_in'] * 25.4, 0),
                'relief_valve_in': entry['relief_in'],
                'meter_in': entry['meter_in'],
                'hose_valves': entry['hose_valves'],
            }
    # Fallback to largest standard entry
    last = NFPA_20_PIPE_SCHEDULE[-1]
    return {
        'rated_gpm': last['gpm'],
        'suction_in': last['suction_in'],
        'suction_mm': round(last['suction_in'] * 25.4, 0),
        'discharge_in': last['discharge_in'],
        'discharge_mm': round(last['discharge_in'] * 25.4, 0),
        'relief_valve_in': last['relief_in'],
        'meter_in': last['meter_in'],
        'hose_valves': last['hose_valves'],
    }


# ============================================================================
# CALCULATION ENGINES
# ============================================================================

def calculate_fire_system_demand(
    standard: str = 'nfpa13',
    hazard_class: str = 'ordinary_hazard_1',
    area_user: Optional[float] = None,
    density_user: Optional[float] = None,
    hose_stream_user: Optional[float] = None,
    risers_count: int = 1,
    sprinklered: bool = True,
    static_elevation_m: float = 0.0,
    friction_loss_m: float = 0.0,
    residual_pressure_bar: Optional[float] = None,
    custom_flow_m3h: Optional[float] = None,
    custom_head_m: Optional[float] = None,
    unit_system: str = 'metric'
) -> Dict[str, Any]:
    """
    Executes complete engineering fire pump demand and auxiliary sizing.

    Parameters:
      standard: 'nfpa13', 'nfpa14', 'en12845', 'as2941', or 'custom'
      hazard_class: Key of selected hazard profile (e.g. 'ordinary_hazard_1')
      area_user: Custom design area (ft² or m² depending on standard)
      density_user: Custom design density
      hose_stream_user: Custom hose stream allowance
      risers_count: Number of standpipe risers (NFPA 14)
      sprinklered: Boolean flag if building is sprinklered (affects NFPA 14 max flow)
      static_elevation_m: Vertical height from pump discharge to highest outlet (m)
      friction_loss_m: Estimated or calculated piping head loss (m)
      residual_pressure_bar: Required pressure at most remote nozzle/outlet (bar)
      custom_flow_m3h: Override flow if standard == 'custom'
      custom_head_m: Override head if standard == 'custom'
      unit_system: 'metric' or 'imperial'

    Returns:
      Comprehensive dictionary containing:
        - Design duty point (Flow & Head in metric and imperial)
        - NFPA 20 curve compliance envelopes (0% churn, 100% rated, 150% overload)
        - Jockey pump sizing and pressure switch start/stop setpoints
        - Water storage tank volume (m³ and US gallons) & duration
        - NFPA 20 recommended pipe sizes
    """
    sprinkler_flow_m3h = 0.0
    hose_flow_m3h = 0.0
    duration_min = 60
    min_residual_m = 10.0  # ~1 bar fallback

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Evaluate Flow Demands based on chosen Standard
    # ─────────────────────────────────────────────────────────────────────────
    if standard == 'nfpa13':
        hz = NFPA_13_HAZARDS.get(hazard_class, NFPA_13_HAZARDS['ordinary_hazard_1'])
        duration_min = hz.get('duration_min', 60)

        if hazard_class == 'esfr_storage':
            spk_gpm = hz['fixed_sprinkler_gpm']
            hse_gpm = hose_stream_user if hose_stream_user is not None else hz['hose_stream_gpm']
        else:
            density = density_user if density_user is not None else hz['density_gpm_ft2']
            area = area_user if area_user is not None else hz['area_ft2']
            spk_gpm = density * area
            hse_gpm = hose_stream_user if hose_stream_user is not None else hz['hose_stream_gpm']

        sprinkler_flow_m3h = spk_gpm * GPM_TO_M3H
        hose_flow_m3h = hse_gpm * GPM_TO_M3H
        res_psi = residual_pressure_bar * 14.5038 if residual_pressure_bar is not None else hz.get('min_residual_psi', 10.0)
        min_residual_m = res_psi * PSI_TO_M

    elif standard == 'nfpa14':
        st = NFPA_14_STANDPIPE.get(hazard_class, NFPA_14_STANDPIPE['class_1'])
        duration_min = st.get('duration_min', 30)

        if hazard_class == 'class_2':
            tot_gpm = st['fixed_flow_gpm']
        else:
            first = st['first_riser_gpm']
            add_riser = st['add_riser_gpm']
            n_add = max(0, int(risers_count) - 1)
            calc_gpm = first + (n_add * add_riser)
            max_gpm = st['max_sprinklered_gpm'] if sprinklered else st['max_nonsprinklered_gpm']
            tot_gpm = min(calc_gpm, max_gpm)

        sprinkler_flow_m3h = 0.0
        hose_flow_m3h = tot_gpm * GPM_TO_M3H
        res_psi = residual_pressure_bar * 14.5038 if residual_pressure_bar is not None else st.get('min_residual_psi', 100.0)
        min_residual_m = res_psi * PSI_TO_M

    elif standard == 'en12845':
        en = EN_12845_HAZARDS.get(hazard_class, EN_12845_HAZARDS['en_oh1'])
        duration_min = en.get('duration_min', 60)
        nominal_m3h = en['nominal_flow_m3h']
        sprinkler_flow_m3h = nominal_m3h
        hose_flow_m3h = (hose_stream_user * GPM_TO_M3H) if hose_stream_user is not None else 0.0
        res_bar = residual_pressure_bar if residual_pressure_bar is not None else en.get('nominal_head_bar', 1.5)
        min_residual_m = res_bar * BAR_TO_M

    elif standard == 'as2941':
        as_crit = AS_2941_CRITERIA.get(hazard_class, AS_2941_CRITERIA['as_sprinkler_ordinary'])
        duration_min = as_crit.get('duration_min', 60)
        sprinkler_flow_m3h = as_crit['flow_m3h']
        hose_flow_m3h = (hose_stream_user * GPM_TO_M3H) if hose_stream_user is not None else 0.0
        head_kpa = as_crit.get('head_kpa', 600.0)
        min_residual_m = (head_kpa / 100.0) * BAR_TO_M

    elif standard == 'custom':
        total_m3h = custom_flow_m3h if custom_flow_m3h is not None and custom_flow_m3h > 0 else 100.0
        sprinkler_flow_m3h = total_m3h
        hose_flow_m3h = 0.0
        duration_min = 60
        min_residual_m = (residual_pressure_bar * BAR_TO_M) if residual_pressure_bar is not None else 10.0

    # Total System Demand Flow
    total_flow_m3h = round(sprinkler_flow_m3h + hose_flow_m3h, 2)
    total_flow_gpm = round(total_flow_m3h * M3H_TO_GPM, 1)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Evaluate Total Dynamic Head (TDH)
    # ─────────────────────────────────────────────────────────────────────────
    if standard == 'custom' and custom_head_m is not None and custom_head_m > 0:
        total_head_m = round(custom_head_m, 2)
    else:
        # TDH = Static Elevation + Friction Losses + Minimum Residual Nozzle Pressure
        total_head_m = round(static_elevation_m + friction_loss_m + min_residual_m, 2)

    total_head_psi = round(total_head_m * M_TO_PSI, 1)
    total_head_bar = round(total_head_m * M_TO_BAR, 2)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. NFPA 20 Characteristic Curve Limits
    # ─────────────────────────────────────────────────────────────────────────
    # Churn / Shutoff: 0% flow must NOT exceed 140% of rated head (typically 101% to 140%)
    max_churn_head_m = round(total_head_m * 1.40, 2)
    max_churn_head_psi = round(total_head_psi * 1.40, 1)

    # Overload: 150% rated flow must produce at least 65% of rated head
    overload_flow_m3h = round(total_flow_m3h * 1.50, 2)
    overload_flow_gpm = round(total_flow_gpm * 1.50, 1)
    min_overload_head_m = round(total_head_m * 0.65, 2)
    min_overload_head_psi = round(total_head_psi * 0.65, 1)

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Auxiliary System Sizing: Jockey Pump (Pressure Maintenance Pump)
    # ─────────────────────────────────────────────────────────────────────────
    # Flow: 1% of fire pump rated capacity (min 10 gpm / 2.27 m³/h)
    jockey_flow_gpm = max(10.0, round(total_flow_gpm * 0.01, 1))
    jockey_flow_m3h = round(jockey_flow_gpm * GPM_TO_M3H, 2)

    # Head: Typically rated head + 10 psi (0.7 bar), ensuring it maintains pressure
    # above main fire pump start pressure
    jockey_head_psi = round(total_head_psi + 10.0, 1)
    jockey_head_m = round(jockey_head_psi * PSI_TO_M, 2)
    jockey_head_bar = round(jockey_head_m * M_TO_BAR, 2)

    # Pressure Switch Settings (NFPA 20 recommendations):
    # - Jockey Pump Stop: Full churn pressure + static supply head (approx churn + 5 psi)
    # - Jockey Pump Start: Jockey stop pressure - 10 psi (0.7 bar)
    # - Fire Pump Start: Jockey start pressure - 10 psi (0.7 bar)
    ps_jockey_stop_psi = round(max_churn_head_psi + 5.0, 1)
    ps_jockey_start_psi = round(ps_jockey_stop_psi - 10.0, 1)
    ps_fire_pump_start_psi = round(ps_jockey_start_psi - 10.0, 1)

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Auxiliary System Sizing: Water Storage Tank (Duration & Volume)
    # ─────────────────────────────────────────────────────────────────────────
    # Volume = Flow Rate * Duration
    tank_vol_m3 = round((total_flow_m3h / 60.0) * duration_min, 1)
    tank_vol_us_gal = round(tank_vol_m3 * M3_TO_US_GAL, 0)

    # ─────────────────────────────────────────────────────────────────────────
    # 6. NFPA 20 Table 4.27 Pipe Sizes
    # ─────────────────────────────────────────────────────────────────────────
    pipe_sizes = get_nfpa20_pipe_sizes(total_flow_gpm)

    # Estimated Hydraulic Power requirement
    # P_hyd (kW) = (Q_m3h * H_m * 1000 * 9.81) / (3600 * 1000)
    hyd_power_kw = round((total_flow_m3h * total_head_m * 9.80665) / 3600.0, 2)
    # Approximate driver power assuming 70% average pump efficiency + 15% safety factor
    driver_power_kw = round((hyd_power_kw / 0.70) * 1.15, 1)
    driver_power_hp = round(driver_power_kw * KW_TO_HP, 1)

    return {
        'standard': standard,
        'hazard_class': hazard_class,
        'unit_system': unit_system,
        'duration_min': duration_min,

        # Duty Point
        'flow_m3h': total_flow_m3h,
        'flow_gpm': total_flow_gpm,
        'sprinkler_flow_m3h': round(sprinkler_flow_m3h, 2),
        'sprinkler_flow_gpm': round(sprinkler_flow_m3h * M3H_TO_GPM, 1),
        'hose_stream_m3h': round(hose_flow_m3h, 2),
        'hose_stream_gpm': round(hose_flow_m3h * M3H_TO_GPM, 1),

        'head_m': total_head_m,
        'head_psi': total_head_psi,
        'head_bar': total_head_bar,
        'static_elevation_m': round(static_elevation_m, 2),
        'friction_loss_m': round(friction_loss_m, 2),
        'residual_pressure_m': round(min_residual_m, 2),

        # NFPA 20 Curve Criteria
        'max_churn_head_m': max_churn_head_m,
        'max_churn_head_psi': max_churn_head_psi,
        'overload_flow_m3h': overload_flow_m3h,
        'overload_flow_gpm': overload_flow_gpm,
        'min_overload_head_m': min_overload_head_m,
        'min_overload_head_psi': min_overload_head_psi,

        # Jockey Pump
        'jockey_pump': {
            'flow_gpm': jockey_flow_gpm,
            'flow_m3h': jockey_flow_m3h,
            'head_psi': jockey_head_psi,
            'head_m': jockey_head_m,
            'head_bar': jockey_head_bar,
            'stop_psi': ps_jockey_stop_psi,
            'start_psi': ps_jockey_start_psi,
            'main_start_psi': ps_fire_pump_start_psi,
        },

        # Water Storage Tank
        'water_tank': {
            'duration_min': duration_min,
            'volume_m3': tank_vol_m3,
            'volume_us_gal': int(tank_vol_us_gal),
        },

        # Recommended Piping (NFPA 20)
        'pipe_sizing': pipe_sizes,

        # Power
        'hydraulic_power_kw': hyd_power_kw,
        'est_driver_power_kw': driver_power_kw,
        'est_driver_power_hp': driver_power_hp,
    }


def compute_pump_head(pump: Any, q_m3h: float) -> float:
    """
    Computes total dynamic head (m) at flow rate q_m3h using the 5th-order H-Q polynomial:
    H(Q) = a0 + a1*Q + a2*Q^2 + a3*Q^3 + a4*Q^4 + a5*Q^5
    """
    if hasattr(pump, 'get_head') and callable(getattr(pump, 'get_head')):
        try:
            return float(pump.get_head(q_m3h))
        except Exception:
            pass
    a0 = getattr(pump, 'hq_a0', 0.0) or 0.0
    a1 = getattr(pump, 'hq_a1', 0.0) or 0.0
    a2 = getattr(pump, 'hq_a2', 0.0) or 0.0
    a3 = getattr(pump, 'hq_a3', 0.0) or 0.0
    a4 = getattr(pump, 'hq_a4', 0.0) or 0.0
    a5 = getattr(pump, 'hq_a5', 0.0) or 0.0
    h = a0 + a1 * q_m3h + a2 * (q_m3h ** 2) + a3 * (q_m3h ** 3) + a4 * (q_m3h ** 4) + a5 * (q_m3h ** 5)
    return max(0.0, float(h))


def compute_pump_eff(pump: Any, q_m3h: float) -> float:
    """
    Computes pump hydraulic efficiency (%) at flow rate q_m3h using polynomial:
    η(Q) = b0 + b1*Q + b2*Q^2 + b3*Q^3 + b4*Q^4 + b5*Q^5
    """
    if hasattr(pump, 'get_eff') and callable(getattr(pump, 'get_eff')):
        try:
            return float(pump.get_eff(q_m3h))
        except Exception:
            pass
    b0 = getattr(pump, 'eff_b0', 0.0) or 0.0
    b1 = getattr(pump, 'eff_b1', 0.0) or 0.0
    b2 = getattr(pump, 'eff_b2', 0.0) or 0.0
    b3 = getattr(pump, 'eff_b3', 0.0) or 0.0
    b4 = getattr(pump, 'eff_b4', 0.0) or 0.0
    b5 = getattr(pump, 'eff_b5', 0.0) or 0.0
    eff = b0 + b1 * q_m3h + b2 * (q_m3h ** 2) + b3 * (q_m3h ** 3) + b4 * (q_m3h ** 4) + b5 * (q_m3h ** 5)
    if eff <= 0.0:
        eff = 72.0  # realistic fallback for centrifugal fire pumps
    return max(1.0, min(98.0, float(eff)))


def compute_pump_power(pump: Any, q_m3h: float, h_m: float, eff_pct: float) -> float:
    """
    Computes pump shaft power (kW) using power polynomial or standard hydraulic power equation:
    P = (Q * H * ρ * g) / (3600 * η)
    """
    if hasattr(pump, 'get_power') and callable(getattr(pump, 'get_power')):
        try:
            return float(pump.get_power(q_m3h))
        except Exception:
            pass
    p0 = getattr(pump, 'pow_p0', 0.0) or 0.0
    p1 = getattr(pump, 'pow_p1', 0.0) or 0.0
    p2 = getattr(pump, 'pow_p2', 0.0) or 0.0
    p3 = getattr(pump, 'pow_p3', 0.0) or 0.0
    p4 = getattr(pump, 'pow_p4', 0.0) or 0.0
    p5 = getattr(pump, 'pow_p5', 0.0) or 0.0
    p = p0 + p1 * q_m3h + p2 * (q_m3h ** 2) + p3 * (q_m3h ** 3) + p4 * (q_m3h ** 4) + p5 * (q_m3h ** 5)
    if p > 0.1:
        return float(p)
    eff = max(0.1, eff_pct / 100.0)
    return float((q_m3h * h_m * 9.80665) / (3600.0 * eff))


def compute_pump_npsh(pump: Any, q_m3h: float) -> Optional[float]:
    """
    Computes pump required NPSH (m) at flow rate q_m3h using polynomial or get_npsh method:
    NPSHr(Q) = c0 + c1*Q + c2*Q^2 + c3*Q^3 + c4*Q^4 + c5*Q^5
    """
    if hasattr(pump, 'get_npsh') and callable(getattr(pump, 'get_npsh')):
        try:
            val = pump.get_npsh(q_m3h)
            if val is not None and float(val) > 0:
                return round(float(val), 2)
        except Exception:
            pass
    c0 = getattr(pump, 'npsh_c0', None)
    if c0 is not None:
        c1 = getattr(pump, 'npsh_c1', 0.0) or 0.0
        c2 = getattr(pump, 'npsh_c2', 0.0) or 0.0
        c3 = getattr(pump, 'npsh_c3', 0.0) or 0.0
        c4 = getattr(pump, 'npsh_c4', 0.0) or 0.0
        c5 = getattr(pump, 'npsh_c5', 0.0) or 0.0
        npsh_val = float(c0) + c1 * q_m3h + c2 * (q_m3h ** 2) + c3 * (q_m3h ** 3) + c4 * (q_m3h ** 4) + c5 * (q_m3h ** 5)
        if npsh_val > 0.05:
            return round(float(npsh_val), 2)
    return None


def evaluate_pump_nfpa20_compliance(
    pump: Any,
    q_duty_m3h: float,
    h_duty_m: float
) -> Dict[str, Any]:
    """
    Evaluates a specific pump against the NFPA 20 Characteristic Curve requirements:
      1. Rated point: H(Q_duty) >= H_duty
      2. Churn / Shutoff: H(0) <= 1.40 * H_duty
      3. Overload capacity: H(1.5 * Q_duty) >= 0.65 * H_duty
      4. Driver power requirement across the full operating range (up to 150% flow).

    Returns evaluation metrics, percentages, pressures, setpoints, and pass/fail statuses.
    """
    # Evaluate Head at 0% flow (Churn / Shutoff)
    h_churn = compute_pump_head(pump, 0.0)

    # Evaluate Head at 100% flow (Rated Duty)
    h_rated = compute_pump_head(pump, q_duty_m3h)

    # Evaluate Head at 150% flow (Overload)
    q_overload = q_duty_m3h * 1.50
    h_overload = compute_pump_head(pump, q_overload)

    # Evaluate Efficiency at rated duty and overload
    eff_rated = compute_pump_eff(pump, q_duty_m3h)
    eff_overload = compute_pump_eff(pump, q_overload)

    # Evaluate Power requirement at shutoff, rated, and 150% overload
    pow_churn = compute_pump_power(pump, 0.0, h_churn, 5.0)
    pow_rated = compute_pump_power(pump, q_duty_m3h, h_rated, eff_rated)
    pow_overload = compute_pump_power(pump, q_overload, h_overload, eff_overload)

    # Evaluate NPSHr at rated and 150% flow
    npsh_rated = compute_pump_npsh(pump, q_duty_m3h)
    npsh_overload = compute_pump_npsh(pump, q_overload)

    # NFPA 20 Ratios:
    # 1. Rated Head Ratio: pump delivered head at duty flow must be >= 100% of required system head
    rated_ratio = (h_rated / h_duty_m) if h_duty_m > 0 else 0.0
    pass_rated = rated_ratio >= 0.98  # Allowing standard 2% engineering tolerance

    # 2. Churn Ratio: shutoff head must NOT exceed 140% of rated head (NFPA 20 §4.7.2)
    reference_rated_head = max(h_duty_m, h_rated)
    churn_ratio = (h_churn / reference_rated_head) if reference_rated_head > 0 else 0.0
    pass_churn = churn_ratio <= 1.405

    # 3. Overload Ratio: at 150% flow, head must be >= 65% of rated head (NFPA 20 §4.7.2)
    overload_ratio = (h_overload / reference_rated_head) if reference_rated_head > 0 else 0.0
    pass_overload = overload_ratio >= 0.645

    # Overall Compliance
    is_compliant = pass_rated and pass_churn and pass_overload

    # Compliance Rating Score (for smart ranking)
    score = 100.0
    if not pass_rated:
        score -= 50.0
    if not pass_churn:
        score -= 30.0
    if not pass_overload:
        score -= 30.0
    score += (eff_rated * 0.2)

    # Sizing Recommended Motor (HP and kW) with NFPA 20 1.15 service factor non-overload margin
    max_power_kw = max(pow_rated, pow_overload)
    rec_driver_kw = round(max_power_kw * 1.15, 1)
    rec_driver_hp = round(rec_driver_kw * KW_TO_HP, 1)

    # Pressure conversions (1 m head = 0.0980665 bar = 1.42233 psi)
    h_churn_bar = round(h_churn * 0.0980665, 2)
    h_churn_psi = round(h_churn * M_TO_PSI, 1)
    h_rated_bar = round(h_rated * 0.0980665, 2)
    h_rated_psi = round(h_rated * M_TO_PSI, 1)
    h_overload_bar = round(h_overload * 0.0980665, 2)
    h_overload_psi = round(h_overload * M_TO_PSI, 1)

    # Jockey pump pressure maintenance switch setpoints (NFPA 20 guidelines)
    jockey_stop_bar = h_churn_bar
    jockey_stop_psi = h_churn_psi
    jockey_start_bar = round(max(0.0, h_churn_bar - 0.7), 2)
    jockey_start_psi = round(max(0.0, h_churn_psi - 10.0), 1)
    fire_start_bar = round(max(0.0, h_churn_bar - 1.05), 2)
    fire_start_psi = round(max(0.0, h_churn_psi - 15.0), 1)

    # Casing relief valve sizing (NFPA 20 §4.18: 3/4" for <= 2500 gpm, 1" for > 2500 gpm)
    relief_valve_size = '3/4" NPT' if q_duty_m3h <= 568.0 else '1" NPT'

    # Performance Test Schedule
    schedule = [
        {
            'letter': 'A',
            'name': 'Shutoff / Churn',
            'flow_pct': 0,
            'flow_m3h': 0.0,
            'head_m': round(h_churn, 2),
            'head_bar': h_churn_bar,
            'head_psi': h_churn_psi,
            'head_pct': round(churn_ratio * 100.0, 1),
            'limit': f'≤ 140% ({round(reference_rated_head * 1.40, 1)} m)',
            'power_kw': round(pow_churn, 1),
            'eff_pct': 0.0,
            'npsh_m': None,
            'pass': pass_churn
        },
        {
            'letter': 'B',
            'name': 'Rated Duty Point',
            'flow_pct': 100,
            'flow_m3h': round(q_duty_m3h, 1),
            'head_m': round(h_rated, 2),
            'head_bar': h_rated_bar,
            'head_psi': h_rated_psi,
            'head_pct': round(rated_ratio * 100.0, 1),
            'limit': f'≥ 100% ({round(h_duty_m, 1)} m)',
            'power_kw': round(pow_rated, 1),
            'eff_pct': round(eff_rated, 1),
            'npsh_m': npsh_rated,
            'pass': pass_rated
        },
        {
            'letter': 'D',
            'name': '150% Overload Test',
            'flow_pct': 150,
            'flow_m3h': round(q_overload, 1),
            'head_m': round(h_overload, 2),
            'head_bar': h_overload_bar,
            'head_psi': h_overload_psi,
            'head_pct': round(overload_ratio * 100.0, 1),
            'limit': f'≥ 65% ({round(reference_rated_head * 0.65, 1)} m)',
            'power_kw': round(pow_overload, 1),
            'eff_pct': round(eff_overload, 1),
            'npsh_m': npsh_overload,
            'pass': pass_overload
        }
    ]

    return {
        'pump_id': pump.id,
        'pump_name': pump.name,
        'manufacturer': pump.manufacturer,
        'model_number': pump.model_number,
        'speed_rpm': pump.speed_rpm,
        'impeller_dia_mm': pump.impeller_dia_mm,

        # NFPA 20 Test Points - Head & Pressures
        'h_churn_m': round(h_churn, 2),
        'h_churn_bar': h_churn_bar,
        'h_churn_psi': h_churn_psi,
        'churn_ratio': round(churn_ratio, 4),
        'churn_ratio_pct': round(churn_ratio * 100.0, 1),
        'pass_churn': pass_churn,

        'h_rated_m': round(h_rated, 2),
        'h_rated_bar': h_rated_bar,
        'h_rated_psi': h_rated_psi,
        'rated_ratio': round(rated_ratio, 4),
        'rated_ratio_pct': round(rated_ratio * 100.0, 1),
        'pass_rated': pass_rated,

        'h_overload_m': round(h_overload, 2),
        'h_overload_bar': h_overload_bar,
        'h_overload_psi': h_overload_psi,
        'overload_ratio': round(overload_ratio, 4),
        'overload_ratio_pct': round(overload_ratio * 100.0, 1),
        'pass_overload': pass_overload,

        # Power & Efficiency
        'eff_rated_pct': round(eff_rated, 1),
        'eff_overload_pct': round(eff_overload, 1),
        'power_churn_kw': round(pow_churn, 1),
        'power_rated_kw': round(pow_rated, 1),
        'power_overload_kw': round(pow_overload, 1),
        'npsh_rated_m': npsh_rated,
        'npsh_overload_m': npsh_overload,
        'rec_driver_kw': rec_driver_kw,
        'rec_driver_hp': rec_driver_hp,

        # Pressure Maintenance Switch Setpoints
        'jockey_stop_bar': jockey_stop_bar,
        'jockey_stop_psi': jockey_stop_psi,
        'jockey_start_bar': jockey_start_bar,
        'jockey_start_psi': jockey_start_psi,
        'fire_start_bar': fire_start_bar,
        'fire_start_psi': fire_start_psi,
        'relief_valve_size': relief_valve_size,
        'schedule': schedule,

        'is_compliant': is_compliant,
        'score': round(score, 1),
        'compliance_status': (
            'COMPLIANT' if is_compliant else
            ('NON_COMPLIANT_HEAD' if not pass_rated else
             ('NON_COMPLIANT_CHURN' if not pass_churn else 'NON_COMPLIANT_OVERLOAD'))
        )
    }
