# PumpSelect Pro

Interactive pump selection and Warman-style curve visualisation tool. Engineers enter a duty point to find matching pumps from a catalogue, view H-Q / power / efficiency / NPSH curves, and compare pumps side-by-side.

## Run & Operate

- `cd pump-app && python app.py` — run the Flask app (port 8000, served at `/`)
- `pnpm --filter @workspace/api-server run dev` — run the Node API server (port 8080, served at `/api`)
- Workflow: **Pump App** — starts Flask automatically

## Stack

- **Backend**: Python 3.11 + Flask + SQLAlchemy (SQLite)
- **Frontend**: Jinja2 templates + Bootstrap 5 + Plotly.js
- **Curve math**: NumPy/SciPy — polynomial evaluation for H-Q, η, power, NPSHr
- **Node API**: Express 5 + Drizzle ORM (pre-existing, not used by pump app)

## Where things live

```
pump-app/
├── app.py               # Flask routes (all modules)
├── models.py            # SQLAlchemy Pump model
├── pump_curves.py       # Curve math: HQ, efficiency, power, NPSHr
├── pump_selection.py    # Duty-point matching + suitability scoring
├── seed_data.py         # 7 example Warman/generic pumps
├── pumps.db             # SQLite database (auto-created)
├── templates/
│   ├── base.html        # Navbar, Plotly CDN, Bootstrap
│   ├── index.html       # Dashboard
│   ├── pump_data.html   # Catalogue list
│   ├── pump_form.html   # Add/edit pump (polynomial coefficients)
│   ├── pump_curve.html  # Warman-style curve viewer
│   ├── pump_selection.html  # Duty-point selection module
│   └── pump_comparison.html # Multi-pump comparison
└── static/
    ├── css/style.css    # Dark theme (CSS variables)
    └── js/
        ├── pump_curves.js      # Plotly chart builders (HQ, eff, power, NPSH, overlay)
        ├── pump_selection.js   # Liquid param switching, compare checkbox logic
        └── pump_comparison.js  # Side-by-side comparison charts
```

## Architecture decisions

- **Polynomial curve model**: All curves stored as polynomial coefficients (a₀…a₃ for H-Q, b₀…b₃ for efficiency, c₀…c₂ for NPSHr). Evaluated client-side by the API and plotted with Plotly.
- **Warman slurry method**: HR, QR, ER factors stored per pump. Cv-based correction applied on top for finer control. Slurry density auto-calculated from Cv and ρ_solid.
- **HI viscosity correction**: Simplified Hydraulic Institute CH/CQ/CE correction applied to viscous duties (log-viscosity scaling).
- **Suitability scoring (0–100)**: BEP proximity (40 pts) + efficiency (40 pts) + NPSH adequacy (10 pts) + head surplus (10 pts).
- **Separate files**: Templates, CSS, and JS are in separate files per user preference.

## Product

- **Pump Catalogue**: Add/edit pumps with polynomial curve coefficients (H-Q, efficiency, NPSHr). 7 example Warman-style pumps seeded.
- **Curve Viewer**: Standalone 2×2 grid or isoline overlay mode. Water / slurry (Warman) / viscous (HI) derating. System curve overlay. BEP marker.
- **Pump Selection**: Input flow, head, NPSHa, liquid type → ranked list with suitability score, BEP proximity bar, NPSH check.
- **Pump Comparison**: Select up to 4 pumps, compare H-Q / efficiency / power / NPSHr on shared axes. BEP table.

## User preferences

- Flask, not React
- Separate files for HTML templates, scripts, and CSS
- SQL database for pump data (SQLite used in dev)

## Gotchas

- Polynomial coefficients must produce valid curves: hq_a1/a2 typically negative; eff_b2 negative (bell-shaped); npsh_c1/c2 positive.
- Flask runs from inside `pump-app/` directory so imports are relative to that folder.
- The SQLite DB file (`pumps.db`) is created in `pump-app/` on first run with 7 seeded pumps.

## Pointers

- See the `pnpm-workspace` skill for the Node.js side of the workspace
