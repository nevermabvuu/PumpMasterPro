"""
features_data.py — Marketing and SEO Metadata Catalog for Pump Master Pro.

Defines comprehensive, non-technical marketing information for all software modules:
- Pump Selection & Duty Point Matching
- Performance Curve Fitting & Digitization
- Slurry & Viscous Fluid Derating
- Fire Protection Pump Sizing (NFPA 20 / 13 / 14 & EN 12845)
- Interactive Pipe Network Hydraulic Sizing
- Multi-Pump Arrays & Variable Speed Drive (VSD)
- Engineering Projects & Quotation Submittals
- Technical Data Sheets & PDF Engineering Reports
"""

FEATURES_CATALOG = {
    'pump-selection': {
        'slug': 'pump-selection',
        'title': 'Intelligent Pump Selection & Sizing Engine',
        'short_title': 'Pump Selection',
        'badge': 'Core Hydraulic Sizing',
        'tagline': 'Instantly match your required flow and head against hundreds of pump models with Best Efficiency Point (BEP) optimization and motor sizing.',
        'meta_description': 'Professional pump selection software for mechanical engineers and distributors. Enter flow, head, and NPSHa to get ranked pump models with BEP analysis.',
        'icon': 'bi-bullseye',
        'accent_color': '#58a6ff',
        'accent_bg': 'rgba(88, 166, 255, 0.15)',
        'screenshot': 'screenshots/screenshot_pump_selection.png',
        'summary': 'Selecting the optimal pump for an industrial application requires matching hydraulic operating conditions against manufacturer performance envelopes while maximizing efficiency and service life. Pump Master Pro automates this complex process in seconds.',
        'what_it_does': [
            'Ranks all compatible pumps in your catalogue based on hydraulic efficiency, motor power, and proximity to Best Efficiency Point (BEP).',
            'Evaluates suction conditions and checks NPSHa against NPSHr to safeguard against cavitation damage.',
            'Sizes standard IEC and NEMA electric motors non-overloading across the entire pump curve.',
            'Supports clean water, industrial effluent, municipal supply, and multi-stage booster applications.',
            'Provides quick 1-click filters for pump manufacturer, speed (RPM), casing size, and impeller trims.'
        ],
        'benefits': [
            'Eliminates manual catalog lookups and oversized pump selections.',
            'Reduces lifetime energy costs by pinpointing high-efficiency models.',
            'Ensures hydraulic reliability with clear cavitation safety margins.',
            'Generates rapid selections during client meetings and tenders.'
        ],
        'applications': [
            'Municipal Water Supply & Distribution',
            'Commercial Building Services & HVAC Booster Systems',
            'Industrial Process Cooling & Water Circulation',
            'Agricultural Irrigation & Drainage Projects'
        ],
        'seo_keywords': [
            'pump selection software', 'centrifugal pump sizing', 'pump duty point matching',
            'BEP analysis', 'NPSHa calculation', 'motor power sizing', 'hydraulic pump selector'
        ],
        'cta_text': 'Launch Pump Selection',
        'cta_url': '/pump-selection'
    },

    'fire-protection': {
        'slug': 'fire-protection',
        'title': 'NFPA 20 & EN 12845 Fire Protection Pump Sizing',
        'short_title': 'Fire Protection Module',
        'badge': 'Life Safety Standards',
        'tagline': 'Certified fire protection pump sizing and hydraulic compliance evaluation covering NFPA 20, NFPA 13, NFPA 14, EN 12845, and AS 2941.',
        'meta_description': 'Fire pump sizing software compliant with NFPA 20, NFPA 13, EN 12845, and AS 2941. Automatic sprinkler demand, standpipe flows, churn pressure, and storage tank sizing.',
        'icon': 'bi-fire',
        'accent_color': '#f85149',
        'accent_bg': 'rgba(248, 81, 73, 0.15)',
        'screenshot': 'screenshots/screenshot_fire_protection.png',
        'carousel': [
            {
                'id': 'nfpa13',
                'title': 'NFPA 13 (Automatic Sprinklers)',
                'badge': 'Sprinkler Standard',
                'image': 'screenshots/screenshot_fire_nfpa13.png',
                'caption': 'Pre-configures hydraulic fire sprinkler demand according to hazard classification (Light Hazard, Ordinary Hazard, Extra Hazard, and High-Bay Storage) with automatic design density, operating area, and hose stream demand.',
                'icon': 'bi-droplet-half'
            },
            {
                'id': 'nfpa14',
                'title': 'NFPA 14 (Standpipe & Hose Systems)',
                'badge': 'Riser Hydraulics',
                'image': 'screenshots/screenshot_fire_nfpa14.png',
                'caption': 'Sizes Class I, II, and III standpipe systems with 500 GPM for the primary riser plus 250 GPM per additional riser, verifying 100 PSI minimum residual pressure at the most remote outlet.',
                'icon': 'bi-signpost-split'
            },
            {
                'id': 'en12845',
                'title': 'EN 12845 / LPC (European Rules)',
                'badge': 'European Standard',
                'image': 'screenshots/screenshot_fire_en12845.png',
                'caption': 'European and LPC code-compliant fire pump sizing covering LH, OH1–4, and High Hazard (HHP/HHS) storage arrays with metric density rates (mm/min) and water supply durations.',
                'icon': 'bi-shield-check'
            },
            {
                'id': 'as2941',
                'title': 'AS 2941 (Australian Standards)',
                'badge': 'ANZ Code',
                'image': 'screenshots/screenshot_fire_as2941.png',
                'caption': 'Australian Standards certified fire pump selection with specialized safety factor margins, overpressure envelope limits, and dedicated suction storage reservoir duration sizing.',
                'icon': 'bi-globe-americas'
            },
            {
                'id': 'nfpa20',
                'title': 'NFPA 20 Compliance & Sizing',
                'badge': 'Auxiliary Sizing',
                'image': 'screenshots/screenshot_fire_compliance.png',
                'caption': 'Direct duty point entry with automated pressure-maintenance Jockey Pump sizing, fire water storage tank volume calculation, and NFPA 20 curve compliance checks (churn shutoff < 140%, 150% flow > 65% head).',
                'icon': 'bi-sliders'
            }
        ],
        'summary': 'Fire protection pump systems protect lives and major infrastructure. Unlike continuous-duty pumps, fire pumps must satisfy strict international codes governing shutoff pressures, overload flow rates, and driver sizing.',
        'what_it_does': [
            'Pre-configures hydraulic fire sprinkler demand according to hazard classification (Light Hazard, Ordinary Hazard, Extra Hazard, and High-Bay Storage).',
            'Calculates Standpipe & Hose stream requirements under NFPA 14 (500 GPM for 1st riser + 250 GPM additional).',
            'Evaluates NFPA 20 curve compliance: confirms rated pressure at 100% flow, churn shutoff head below 140%, and overload pressure above 65% at 150% flow.',
            'Sizes dedicated fire water storage tanks and determines usable volume based on system duration (30 to 120+ minutes).',
            'Sizes pressure-maintenance Jockey Pumps to prevent unnecessary main pump starts on minor pressure drops.'
        ],
        'benefits': [
            'Ensures immediate compliance with fire department and insurance underwriting criteria.',
            'Eliminates guesswork in complex hazard density and hose stream demand equations.',
            'Guarantees driver non-overloading across full fire demand curves.',
            'Streamlines regulatory approval with clear code-compliance indicators.'
        ],
        'applications': [
            'High-Rise Commercial Buildings & Office Towers',
            'Industrial Warehouses & Logistics Distribution Centers',
            'Oil & Gas Refineries, Petrochemical Plants & Fuel Depots',
            'Hospitals, Universities & Critical Public Infrastructure'
        ],
        'seo_keywords': [
            'fire pump sizing software', 'NFPA 20 fire pump', 'NFPA 13 sprinkler calculation',
            'EN 12845 fire pump', 'churn pressure calculation', 'fire water storage tank sizing',
            'jockey pump sizing', 'fire protection hydraulic calculation'
        ],
        'cta_text': 'Explore Fire Pump Sizing',
        'cta_url': '/pump-selection?filter_pump_type=fire+pump'
    },

    'slurry-derating': {
        'slug': 'slurry-derating',
        'title': 'Slurry & Viscous Fluid Performance Derating',
        'short_title': 'Slurry & Viscous Sizing',
        'badge': 'Mining & Heavy Solids',
        'tagline': 'Accurate solids handling and viscous fluid correction factors utilizing the PumpMasterPro slurry method and Hydraulic Institute ANSI/HI standards.',
        'meta_description': 'Slurry pump selection and viscous correction software. Apply PumpMasterPro HR, QR, ER derating factors and ANSI/HI viscosity correction curves to standard pump models.',
        'icon': 'bi-layers-fill',
        'accent_color': '#e3b341',
        'accent_bg': 'rgba(227, 179, 65, 0.15)',
        'screenshot': 'screenshots/screenshot_slurry_derating.png',
        'carousel': [
            {
                'id': 'slurry',
                'title': 'PumpMasterPro Slurry Derating',
                'badge': 'Heavy Solids & Tailings',
                'image': 'screenshots/screenshot_fluid_slurry.png',
                'caption': 'Solids handling correction applying the PumpMasterPro slurry derating model to compute Head Ratio (HR), Flow Ratio (QR), and Efficiency Ratio (ER) based on particle diameter d50 and volumetric concentration Cv.',
                'icon': 'bi-layers-fill'
            },
            {
                'id': 'water',
                'title': 'Clean Water Standard Baseline',
                'badge': 'ISO / HI Reference',
                'image': 'screenshots/screenshot_fluid_water.png',
                'caption': 'Standard test condition performance curves evaluated at 20°C and 1000 kg/m³ density, providing the exact hydraulic baseline for Best Efficiency Point (BEP) matching and cavitation analysis.',
                'icon': 'bi-droplet'
            },
            {
                'id': 'viscous',
                'title': 'ANSI/HI Viscous Fluid Correction',
                'badge': 'Viscosity Sizing',
                'image': 'screenshots/screenshot_fluid_viscous.png',
                'caption': 'Hydraulic Institute empirical viscosity correction factors (CH, CQ, CE) for heavy oils, molasses, polymers, and non-Newtonian viscous fluids with automated Reynolds number adjustments.',
                'icon': 'bi-funnel-fill'
            }
        ],
        'summary': 'Handling slurries, tailings, abrasives, or high-viscosity liquids drastically alters pump performance compared to clean water. Pump Master Pro applies proven empirical derating models directly to clean water curves.',
        'what_it_does': [
            'Applies the PumpMasterPro slurry derating method to compute Head Ratio (HR), Flow Ratio (QR), and Efficiency Ratio (ER) based on particle diameter d50 and volumetric concentration Cv.',
            'Derates standard pump performance curves automatically to show realistic delivered slurry head and increased shaft power.',
            'Supports ANSI/HI viscous fluid correction factors (CH, CQ, CE) for heavy oils, syrups, polymers, and sludges.',
            'Calculates slurry mixture specific gravity (SGm) and dynamic slurry density from solid and carrier fluid inputs.',
            'Protects against premature motor trip-outs caused by slurry weight and high specific gravity.'
        ],
        'benefits': [
            'Prevents under-sizing slurry pumps that fail to clear system discharge elevation.',
            'Sizes electric motors accurately for high-density slurries to prevent motor failure.',
            'Enables clean-water pumps to be evaluated for light slurry without custom manual testing.',
            'Optimizes pump wear life by matching lower operating speeds for abrasive duties.'
        ],
        'applications': [
            'Mining Beneficiation, Mineral Processing & Tailings Disposal',
            'Sand, Gravel & Dredging Operations',
            'Coal Washing, Fly Ash Handling & Power Plants',
            'Food Processing, Oils, Resins & Viscous Chemical Fluids'
        ],
        'seo_keywords': [
            'slurry pump selection', 'slurry derating software', 'PumpMasterPro HR ER QR factor',
            'viscous pump correction', 'ANSI HI viscosity correction', 'slurry specific gravity calculation',
            'solids handling pump sizing'
        ],
        'cta_text': 'Size Slurry Pumps',
        'cta_url': '/pump-selection?filter_pump_type=slurry'
    },

    'curve-management': {
        'slug': 'curve-management',
        'title': 'Automated Curve Fitting & Digital Catalogue',
        'short_title': 'Curve Fitting & Digitization',
        'badge': 'Performance Analytics',
        'tagline': 'Convert printed manufacturer datasheets into interactive, mathematical polynomial performance curves with Iso-Efficiency contours.',
        'meta_description': 'Pump curve fitting and digitization software. Transform raw Q-H-Eff-NPSH points into polynomial curves with affinity law impeller trims and VFD speed overlays.',
        'icon': 'bi-graph-up',
        'accent_color': '#3fb950',
        'accent_bg': 'rgba(63, 185, 80, 0.15)',
        'screenshot': 'screenshots/screenshot_add_pump.png',
        'summary': 'Ditch paper catalogues and static PDF graphs. Pump Master Pro digitizes manufacturer performance data into high-precision continuous mathematical curves that can be evaluated at any flow rate.',
        'what_it_does': [
            'Accepts discrete test points (Flow, Head, Efficiency, Power, NPSHr) and fits smooth 2nd to 5th order polynomial equations.',
            'Generates full impeller trim families automatically using hydrodynamic affinity laws.',
            'Renders closed Iso-Efficiency contour loops across multiple impeller diameters or RPM speeds.',
            'Overlays system resistance curves and operating duty points with interactive zoom and pan.',
            'Displays mini sparkline curve previews directly in your organization’s pump database.'
        ],
        'benefits': [
            'Empowers pump manufacturers to publish digital, interactive product catalogues.',
            'Enables exact head and power calculations at any non-tested operating point.',
            'Saves hours of manual graph interpolation and spreadsheet plotting.',
            'Stores proprietary OEM test data securely under multi-organization access levels.'
        ],
        'applications': [
            'Centrifugal Pump Manufacturers & OEM Engineering Teams',
            'Pump Repair Facilities & Re-rating Workshops',
            'Engineering Consultancy & Hydraulic Design Firms',
            'Plant Operations & Maintenance Asset Managers'
        ],
        'seo_keywords': [
            'pump curve fitting software', 'pump curve digitizer', 'head flow curve calculator',
            'iso efficiency curves', 'impeller trim calculator', 'affinity laws pump curve',
            'pump performance map generator'
        ],
        'cta_text': 'View Pump Catalogue',
        'cta_url': '/pumps'
    },

    'pipe-network': {
        'slug': 'pipe-network',
        'title': 'Interactive Pipe Network & System Head Modeling',
        'short_title': 'Pipe Network Designer',
        'badge': 'Hydraulic Modeling',
        'tagline': 'Model piping loops, series/parallel branches, static elevation changes, and friction head losses using Darcy-Weisbach and Colebrook-White.',
        'meta_description': 'Interactive pipe network hydraulic calculator software. Calculate friction losses, fitting K-values, static head, and system curves with visual schematic canvas.',
        'icon': 'bi-diagram-3-fill',
        'accent_color': '#22c55e',
        'accent_bg': 'rgba(34, 197, 94, 0.15)',
        'screenshot': 'screenshots/screenshot_pipe_network.png',
        'carousel': [
            {
                'id': 'visual',
                'title': 'Visual Industrial CAD Canvas',
                'badge': 'Interactive Canvas',
                'image': 'screenshots/screenshot_pipe_visual.png',
                'caption': 'Drag-and-drop interactive canvas featuring true-to-scale industrial equipment: suction reservoirs, pumps, control valves, check valves, and discharge vessels with animated fluid elevations.',
                'icon': 'bi-water'
            },
            {
                'id': 'schematic',
                'title': 'Engineering P&ID Schematic View',
                'badge': 'Schematic Diagram',
                'image': 'screenshots/screenshot_pipe_schematic.png',
                'caption': 'Clean single-line engineering schematic displaying pipe branch lengths, node elevations, fitting K-factor labels, and dynamic velocity indicators for rapid hydraulic review.',
                'icon': 'bi-bezier2'
            },
            {
                'id': 'simple',
                'title': 'Simple Mode (Branch Configurator)',
                'badge': 'Tabular Configurator',
                'image': 'screenshots/screenshot_pipe_simple.png',
                'caption': 'Fast tabular branch builder ideal for quick series/parallel pipe sizing. Select materials, pipe schedules, and valves from comprehensive dropdown libraries to compute Darcy-Weisbach head loss.',
                'icon': 'bi-list-columns-reverse'
            }
        ],
        'summary': 'Before sizing a pump, engineers must know the exact system resistance. Pump Master Pro features an integrated piping hydraulic calculator that models complex pipeline routes and transfers system curves directly into pump selection.',
        'what_it_does': [
            'Calculates major friction loss using the Darcy-Weisbach equation and Colebrook-White friction factor.',
            'Accounts for minor losses across elbows, valves, tees, strainers, and non-return valves with standard equivalent K-factors.',
            'Models static head changes between suction source reservoirs and final discharge delivery points.',
            'Offers dual designer modes: a simple Series/Parallel branch configurator and an interactive Visual Schematic Canvas.',
            'Includes comprehensive pipe material libraries (Carbon Steel, HDPE, Ductile Iron, PVC, Copper, Stainless Steel).'
        ],
        'benefits': [
            'Calculates exact Total Dynamic Head (TDH) without manual Moody diagram lookups.',
            'Connects system resistance curves directly into pump selection with zero duplicate data entry.',
            'Allows rapid "what-if" testing of pipe diameters to optimize capital pipe cost versus pumping energy.',
            'Visually validates line sizing to maintain recommended liquid velocities (1.5 – 3.0 m/s).'
        ],
        'applications': [
            'Pipeline Sizing & Industrial Pumping Stations',
            'Chilled Water & District Heating Loops',
            'Water Treatment Plant Process Piping',
            'Mine Dewatering & Slurry Transmission Lines'
        ],
        'seo_keywords': [
            'pipe network calculation software', 'hydraulic friction loss calculator',
            'Darcy Weisbach calculator', 'system head curve', 'pipe sizing software',
            'minor loss K factor valves', 'pipe network designer'
        ],
        'cta_text': 'Open Pipe Network Designer',
        'cta_url': '/pipe-network'
    },

    'multi-pump-vsd': {
        'slug': 'multi-pump-vsd',
        'title': 'Multi-Pump Arrays & Variable Speed Drive (VSD)',
        'short_title': 'Multi-Pump & VSD Analysis',
        'badge': 'Energy Optimization',
        'tagline': 'Analyze parallel pump staging, series pressure boosting, and Variable Frequency Drive (VFD) speed modulation envelopes.',
        'meta_description': 'Multi-pump selection and VSD analysis software. Model parallel pumps for flow boosting, series pumps for high head, and VFD speed curves to optimize energy efficiency.',
        'icon': 'bi-speedometer2',
        'accent_color': '#a371f7',
        'accent_bg': 'rgba(163, 113, 247, 0.15)',
        'screenshot': 'screenshots/screenshot_pump_comparison.png',
        'summary': 'Modern pumping systems frequently utilize multiple identical pumps in parallel or variable speed drives to follow fluctuating process demands while drastically cutting electrical power consumption.',
        'what_it_does': [
            'Simulates parallel pump operation: computes combined flow rate at shared system head for 1 to 8 operating pumps.',
            'Models series multi-pump configurations: sums head delivery for high-pressure deep well and cross-country transport duties.',
            'Calculates Variable Frequency Drive (VFD) speed reduction curves using hydraulic affinity laws from 30 Hz to 60 Hz.',
            'Identifies minimum continuous stable flow and maximum motor thermal limits at reduced speeds.',
            'Visualizes intersection points between variable system curves and modulated pump speed curves.'
        ],
        'benefits': [
            'Sizes energy-efficient duplex, triplex, and quadruplex booster systems with built-in duty/standby staging.',
            'Uncovers massive energy savings by running pumps at reduced RPM during low-demand periods.',
            'Prevents pump dead-heading and thermal run-out by establishing safe VFD operating envelopes.',
            'Demonstrates return on investment (ROI) for installing variable frequency drives.'
        ],
        'applications': [
            'Municipal Booster Pumping Stations & City Water Grids',
            'Variable Flow Chilled Water Cooling Towers',
            'Mine Deep-Well Dewatering & Multi-Stage Lift Stations',
            'Multi-Pump Boiler Feed & Irrigation Header Systems'
        ],
        'seo_keywords': [
            'multi pump selection software', 'parallel pump curve calculation',
            'variable speed pump sizing', 'VFD pump energy calculation',
            'duty standby pump staging', 'series pump calculation'
        ],
        'cta_text': 'Compare Pump Curves',
        'cta_url': '/pump-comparison'
    },

    'projects-management': {
        'slug': 'projects-management',
        'title': 'Engineering Projects & Multi-Scenario Management',
        'short_title': 'Projects & Portfolios',
        'badge': 'Collaboration Suite',
        'tagline': 'Organize pump selections by client, job site, and operating condition with multi-scenario comparison and team collaboration.',
        'meta_description': 'Engineering project management for pump selection. Organize saved pump selections, manage multiple site operating scenarios, and export tender submittal packages.',
        'icon': 'bi-folder2-open',
        'accent_color': '#38bdf8',
        'accent_bg': 'rgba(56, 189, 248, 0.15)',
        'screenshot': 'screenshots/screenshot_projects.png',
        'summary': 'Engineering projects rarely require just one pump. EPC contractors and design firms manage dozens of duty points across plant areas, operating seasons, and project stages.',
        'what_it_does': [
            'Groups multiple pump selections into organized Projects with site location, client details, and reference numbers.',
            'Saves multiple operational scenarios per project (e.g. Normal Duty, Peak Storm Flow, Winter Low Demand).',
            'Tracks selected pump models, motor specifications, impeller trims, and fluid properties in one unified view.',
            'Enables team members and clients to collaborate on selections under role-based access control.',
            'Exports complete project equipment schedules and bills of materials with single-click ease.'
        ],
        'benefits': [
            'Eliminates lost calculation files and scattered spreadsheets across engineering teams.',
            'Maintains a single source of truth for pump selections from initial proposal to final commissioning.',
            'Speed up client revisions by updating duty points across an entire project package in seconds.',
            'Improves proposal professionalism for pump vendors and EPC bidding teams.'
        ],
        'applications': [
            'EPC Engineering & Turnkey Plant Contractors',
            'Equipment Distributors & Manufacturer Sales Reps',
            'Consulting Hydraulic & Civil Engineering Firms',
            'Corporate Facility & Utility Asset Managers'
        ],
        'seo_keywords': [
            'pump project management', 'pump equipment schedule software',
            'tender pump selection', 'engineering pump portfolio', 'saved pump selections',
            'client submittal software'
        ],
        'cta_text': 'View Projects Suite',
        'cta_url': '/projects'
    },

    'technical-reports': {
        'slug': 'technical-reports',
        'title': 'Professional Engineering Reports & PDF Submittals',
        'short_title': 'Reports & Submittals',
        'badge': 'Documentation & Export',
        'tagline': 'Generate publication-ready PDF datasheets, customer proposal packages, performance curves, and motor specifications with your company branding.',
        'meta_description': 'Automated pump datasheet and PDF submittal generator. Produce branded engineering reports, curve plots, motor specs, and ISO compliance data sheets.',
        'icon': 'bi-file-earmark-pdf-fill',
        'accent_color': '#ff7b72',
        'accent_bg': 'rgba(255, 123, 114, 0.15)',
        'screenshot': 'screenshots/screenshot_reports_settings.png',
        'summary': 'Delivering professional documentation wins contracts. Pump Master Pro automatically generates client-ready PDF submittals complete with high-resolution performance curves, operating data, and custom corporate branding.',
        'what_it_does': [
            'Produces comprehensive 1-page and multi-page technical datasheets formatted to international engineering standards.',
            'Renders publication-quality vector performance curves showing Head, Efficiency, Power, and NPSHr at the exact duty point.',
            'Includes complete electric motor nameplate specs: efficiency rating (IE1–IE4), poles, frame size, full load current, and frequency.',
            'Supports company branding: upload organization logo, customize report headers, footer disclaimers, and contact details.',
            'Generates printable NFPA 20 fire pump compliance sheets with churn ratio and overload verifications.'
        ],
        'benefits': [
            'Replaces hours of manual report compiling with instant 1-click PDF generation.',
            'Delivers branded submittals that impress clients and win commercial tenders.',
            'Ensures data integrity: all numbers and curves come directly from the calibrated database.',
            'Standardizes reporting format across all engineers and office branches.'
        ],
        'applications': [
            'Equipment Submittals for Architectural & Civil Approvals',
            'Client Quotations, Commercial Bids & Tender Documents',
            'Factory Acceptance Testing (FAT) & Commissioning Records',
            'Operations & Maintenance (O&M) Facility Manuals'
        ],
        'seo_keywords': [
            'pump datasheet generator', 'pump submittal PDF report',
            'pump performance curve PDF', 'engineering report generator pump',
            'branded pump quotation datasheet'
        ],
        'cta_text': 'View Report Capabilities',
        'cta_url': '/pumps'
    }
}
