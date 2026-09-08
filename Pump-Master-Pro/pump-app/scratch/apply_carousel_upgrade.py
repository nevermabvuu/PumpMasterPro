# scratch/apply_carousel_upgrade.py
# Upgrades login.html with a 5-slide interactive horizontal carousel and controller JS

with open('templates/auth/login.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Replace CSS for marketing slides with carouselTrack transform styles
old_css_part = """  /* Horizontal track carousel transition */
  #carouselTrack {
    transition: transform 0.5s cubic-bezier(0.2, 1, 0.3, 1);
    will-change: transform;
  }
</style>"""

new_css = """  /* Horizontal track carousel transition */
  #carouselTrack {
    transition: transform 0.5s cubic-bezier(0.2, 1, 0.3, 1);
    will-change: transform;
  }
  .carousel-slide-card {
    transition: border-color 0.2s ease, transform 0.2s ease;
  }
  .carousel-slide-card:hover {
    transform: translateY(-2px);
  }
</style>"""

if old_css_part in text:
    text = text.replace(old_css_part, new_css, 1)

# 2. Locate the marketing slide container in login.html
container_start = text.find('<div class="rounded-2xl border border-[#30363d] bg-[#161b22]/90')
container_end = text.find('<!-- ─────────────────────────────────────────────────────────────────\n             INTERACTIVE MINI "VIDEO" SIMULATOR CONSOLE')

if container_start == -1 or container_end == -1:
    # Alternative search
    container_start = text.find('id="marketingSlideContainer"')
    # Find enclosing div start
    container_start = text.rfind('<div', 0, container_start)
    container_end = text.find('id="mockVideoPlayer"')
    container_end = text.rfind('<div', 0, container_end)

print(f"Container range: {container_start} to {container_end}")

new_carousel_markup = '''        <!-- ─────────────────────────────────────────────────────────────────
             INTERACTIVE MARKETING CAROUSEL: 5 ENGINEERING FEATURE PILLARS
             Beginners Note: Horizontal sliding carousel with smooth CSS transforms,
             animated progress timer bar, category badges, and rich engineering data.
             Fully compliant with zero third-party trademark restrictions.
             ───────────────────────────────────────────────────────────────── -->
        <div class="rounded-2xl border border-[#30363d] bg-[#161b22]/95 backdrop-blur-md shadow-2xl relative overflow-hidden flex flex-col" id="marketingCarousel">
          
          <!-- Top Animated Countdown Timer Progress Bar -->
          <div class="h-1 w-full bg-[#21262d] overflow-hidden">
            <div id="carouselProgressBar" class="h-full bg-gradient-to-r from-[#58a6ff] via-[#39d3c0] to-[#a371f7] w-0 transition-all ease-linear"></div>
          </div>

          <!-- Carousel Navigation Header -->
          <div class="flex items-center justify-between px-5 py-3 border-b border-[#30363d]/80 bg-[#1c2330]/60">
            <div class="flex items-center gap-2.5">
              <span id="slideCategoryBadge" class="px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-[#58a6ff]/15 text-[#58a6ff] border border-[#58a6ff]/30">
                MULTI-DISCIPLINE
              </span>
              <span id="slideNumberBadge" class="font-mono text-xs text-[#8b949e] font-semibold">
                SLIDE 01 / 05
              </span>
            </div>

            <!-- Slide Arrows & Dots -->
            <div class="flex items-center gap-2">
              <div class="flex items-center gap-1.5 me-2" id="carouselDots">
                <button type="button" onclick="goToCarouselSlide(0)" class="w-6 h-1.5 rounded-full bg-[#58a6ff] transition-all cursor-pointer" id="cdot-0" title="Slide 1: Fleet Coverage"></button>
                <button type="button" onclick="goToCarouselSlide(1)" class="w-2 h-1.5 rounded-full bg-[#30363d] hover:bg-[#8b949e] transition-all cursor-pointer" id="cdot-1" title="Slide 2: OEM Customization"></button>
                <button type="button" onclick="goToCarouselSlide(2)" class="w-2 h-1.5 rounded-full bg-[#30363d] hover:bg-[#8b949e] transition-all cursor-pointer" id="cdot-2" title="Slide 3: Slurry Derating"></button>
                <button type="button" onclick="goToCarouselSlide(3)" class="w-2 h-1.5 rounded-full bg-[#30363d] hover:bg-[#8b949e] transition-all cursor-pointer" id="cdot-3" title="Slide 4: Duty Matching"></button>
                <button type="button" onclick="goToCarouselSlide(4)" class="w-2 h-1.5 rounded-full bg-[#30363d] hover:bg-[#8b949e] transition-all cursor-pointer" id="cdot-4" title="Slide 5: Security &amp; PDFs"></button>
              </div>
              <button type="button" onclick="prevCarouselSlide()" class="w-7 h-7 rounded-lg bg-[#21262d] hover:bg-[#30363d] text-[#c9d1d9] hover:text-white flex items-center justify-center transition-colors cursor-pointer border border-[#30363d]" title="Previous Slide">
                <i class="bi bi-chevron-left text-xs"></i>
              </button>
              <button type="button" onclick="nextCarouselSlide()" class="w-7 h-7 rounded-lg bg-[#21262d] hover:bg-[#30363d] text-[#c9d1d9] hover:text-white flex items-center justify-center transition-colors cursor-pointer border border-[#30363d]" title="Next Slide">
                <i class="bi bi-chevron-right text-xs"></i>
              </button>
            </div>
          </div>

          <!-- Carousel Sliding Track Container -->
          <div class="overflow-hidden w-full">
            <div id="carouselTrack" class="flex transition-transform duration-500 ease-out">
              
              <!-- SLIDE 1: UNIVERSAL MULTI-DISCIPLINE PUMP COVERAGE -->
              <div class="w-full shrink-0 p-5 space-y-3.5">
                <div class="flex items-start gap-3">
                  <span class="w-10 h-10 rounded-xl bg-gradient-to-br from-[#58a6ff]/20 to-[#39d3c0]/20 text-[#58a6ff] flex items-center justify-center text-lg shrink-0 border border-[#58a6ff]/30 shadow-inner">
                    <i class="bi bi-diagram-3-fill"></i>
                  </span>
                  <div>
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                      Universal Sizing: Centrifugal, PD, Multi-Stage &amp; Submersible
                      <span class="text-[10px] font-normal px-2 py-0.2 rounded-full bg-[#58a6ff]/10 text-[#58a6ff] border border-[#58a6ff]/30">All Pump Types</span>
                    </h3>
                    <p class="text-xs text-[#8b949e] mt-1 leading-relaxed">
                      Engineered for all fluid dynamics. The solver handles everything from high-volume single-stage end-suction volutes to progressive cavity positive displacement, high-pressure boiler feeds, and heavy slurry sumps.
                    </p>
                  </div>
                </div>

                <!-- Type Badges Grid (4 Pillars) -->
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] text-center carousel-slide-card hover:border-[#58a6ff]/40">
                    <div class="text-[#58a6ff] font-bold text-xs"><i class="bi bi-arrow-repeat"></i> Centrifugal</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5 font-mono">ISO, DIN, ANSI B73.1</div>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] text-center carousel-slide-card hover:border-[#39d3c0]/40">
                    <div class="text-[#39d3c0] font-bold text-xs"><i class="bi bi-gear-wide-connected"></i> Positive Displ.</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5 font-mono">PC, Gear, Screw, Lobe</div>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] text-center carousel-slide-card hover:border-[#bc8cff]/40">
                    <div class="text-[#bc8cff] font-bold text-xs"><i class="bi bi-layers-fill"></i> Multi-Stage</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5 font-mono">High-Head / Mine Stacks</div>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] text-center carousel-slide-card hover:border-[#3fb950]/40">
                    <div class="text-[#3fb950] font-bold text-xs"><i class="bi bi-water"></i> Submersible</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5 font-mono">Slurry &amp; Cantilever</div>
                  </div>
                </div>

                <!-- Slide Metric Strip -->
                <div class="flex items-center justify-between text-[11px] text-[#8b949e] pt-1.5 border-t border-[#30363d]/50 font-mono">
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>400+ Hydraulic Geometries</span>
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>Dynamic Impeller Trimming</span>
                  <span class="hidden sm:inline"><i class="bi bi-check2 text-[#3fb950] me-1"></i>Universal Viscosity Support</span>
                </div>
              </div>

              <!-- SLIDE 2: 100% BESPOKE OEM CUSTOMIZATION -->
              <div class="w-full shrink-0 p-5 space-y-3.5">
                <div class="flex items-start gap-3">
                  <span class="w-10 h-10 rounded-xl bg-gradient-to-br from-[#bc8cff]/20 to-[#58a6ff]/20 text-[#bc8cff] flex items-center justify-center text-lg shrink-0 border border-[#bc8cff]/30 shadow-inner">
                    <i class="bi bi-sliders"></i>
                  </span>
                  <div>
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                      100% Bespoke OEM Customization: User-Defined Engines
                      <span class="text-[10px] font-normal px-2 py-0.2 rounded-full bg-[#bc8cff]/10 text-[#bc8cff] border border-[#bc8cff]/30">OEM Freedom</span>
                    </h3>
                    <p class="text-xs text-[#8b949e] mt-1 leading-relaxed">
                      Full authority over mathematical curve regression and fleet parameters. Configure custom polynomial orders, affinity law scaling exponents, customer safety factors, and up to 30 custom spec fields per organisation.
                    </p>
                  </div>
                </div>

                <!-- Customization Features (3 Pillars) -->
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1 text-xs">
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-1 carousel-slide-card hover:border-[#bc8cff]/40">
                    <div class="text-[#bc8cff] font-bold flex items-center gap-1.5"><i class="bi bi-graph-up-arrow"></i> Polynomial Orders 2-6</div>
                    <p class="text-[11px] text-[#8b949e] leading-snug">Least-squares curve regression with exact shutoff head &amp; power curves.</p>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-1 carousel-slide-card hover:border-[#58a6ff]/40">
                    <div class="text-[#58a6ff] font-bold flex items-center gap-1.5"><i class="bi bi-arrow-left-right"></i> Affinity Exponents</div>
                    <p class="text-[11px] text-[#8b949e] leading-snug">User-calibrated speed scaling exponents (H &prop; N^x, P &prop; N^y) for unique impellers.</p>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-1 carousel-slide-card hover:border-[#39d3c0]/40">
                    <div class="text-[#39d3c0] font-bold flex items-center gap-1.5"><i class="bi bi-tags"></i> 30 Custom Attributes</div>
                    <p class="text-[11px] text-[#8b949e] leading-snug">API 682 seal plans, exotic alloys (28% Cr, CD4MCu), flange drillings, and notes.</p>
                  </div>
                </div>

                <!-- Slide Metric Strip -->
                <div class="flex items-center justify-between text-[11px] text-[#8b949e] pt-1.5 border-t border-[#30363d]/50 font-mono">
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>User-Defined Equations</span>
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>Custom Duty Margins %</span>
                  <span class="hidden sm:inline"><i class="bi bi-check2 text-[#3fb950] me-1"></i>White-Label Brand Colors</span>
                </div>
              </div>

              <!-- SLIDE 3: HEAVY SLURRY & NON-NEWTONIAN VISCOUS DERATING -->
              <div class="w-full shrink-0 p-5 space-y-3.5">
                <div class="flex items-start gap-3">
                  <span class="w-10 h-10 rounded-xl bg-gradient-to-br from-[#d29922]/20 to-[#f0883e]/20 text-[#d29922] flex items-center justify-center text-lg shrink-0 border border-[#d29922]/30 shadow-inner">
                    <i class="bi bi-droplet-half"></i>
                  </span>
                  <div>
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                      Abrasive Slurry &amp; Viscous Fluid Derating Engine
                      <span class="text-[10px] font-normal px-2 py-0.2 rounded-full bg-[#d29922]/10 text-[#d29922] border border-[#d29922]/30">Severe Media</span>
                    </h3>
                    <p class="text-xs text-[#8b949e] mt-1 leading-relaxed">
                      Predict real-world head, efficiency, and power deratings for dense mineral slurries. Built-in ANSI/HI solid concentration modeling (Cw/Cv), particle size distribution (d50), and Hydraulic Institute viscous correction.
                    </p>
                  </div>
                </div>

                <!-- Slurry Parameters Grid -->
                <div class="grid grid-cols-3 gap-2.5 pt-1 font-mono text-xs text-center">
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] carousel-slide-card hover:border-[#d29922]/40">
                    <div class="text-[#d29922] font-bold text-sm">SG up to 3.8</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5">High Specific Gravity</div>
                    <div class="text-[9px] text-[#d29922]/70 mt-0.5">Dense Tailings &amp; Ores</div>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] carousel-slide-card hover:border-[#3fb950]/40">
                    <div class="text-[#3fb950] font-bold text-sm">Cw up to 70%</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5">Solids by Weight</div>
                    <div class="text-[9px] text-[#3fb950]/70 mt-0.5">ANSI/HI HR &amp; ER Derate</div>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] carousel-slide-card hover:border-[#58a6ff]/40">
                    <div class="text-[#58a6ff] font-bold text-sm">3,000 cSt</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5">Viscous Correction</div>
                    <div class="text-[9px] text-[#58a6ff]/70 mt-0.5">HI 9.6.7 Model (CH, CQ, C_eta)</div>
                  </div>
                </div>

                <!-- Slide Metric Strip -->
                <div class="flex items-center justify-between text-[11px] text-[#8b949e] pt-1.5 border-t border-[#30363d]/50 font-mono">
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>d50 Micron Wear Sizing</span>
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>Tip Speed Limit Check</span>
                  <span class="hidden sm:inline"><i class="bi bi-check2 text-[#3fb950] me-1"></i>Non-Newtonian Rheology</span>
                </div>
              </div>

              <!-- SLIDE 4: REAL-TIME HYDRAULIC SIZING & BEP PROXIMITY -->
              <div class="w-full shrink-0 p-5 space-y-3.5">
                <div class="flex items-start gap-3">
                  <span class="w-10 h-10 rounded-xl bg-gradient-to-br from-[#3fb950]/20 to-[#58a6ff]/20 text-[#3fb950] flex items-center justify-center text-lg shrink-0 border border-[#3fb950]/30 shadow-inner">
                    <i class="bi bi-bullseye"></i>
                  </span>
                  <div>
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                      Precision Duty Matching &amp; Best Efficiency Point (BEP)
                      <span class="text-[10px] font-normal px-2 py-0.2 rounded-full bg-[#3fb950]/10 text-[#3fb950] border border-[#3fb950]/30">Lifecycle Optics</span>
                    </h3>
                    <p class="text-xs text-[#8b949e] mt-1 leading-relaxed">
                      Identify the optimal hydraulic match in seconds. Analyze operating regions (POR / ROR), evaluate available NPSH headroom, plot system curves, and automatically configure IEC/NEMA electric motor drives.
                    </p>
                  </div>
                </div>

                <!-- Features Grid -->
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1 text-xs">
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-1 carousel-slide-card hover:border-[#3fb950]/40">
                    <div class="text-[#3fb950] font-bold flex items-center gap-1.5"><i class="bi bi-check-circle"></i> POR &amp; ROR Compliance</div>
                    <p class="text-[11px] text-[#8b949e] leading-snug">Evaluates Preferred Operating Region (70%–120% BEP) to prevent shaft fatigue.</p>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-1 carousel-slide-card hover:border-[#58a6ff]/40">
                    <div class="text-[#58a6ff] font-bold flex items-center gap-1.5"><i class="bi bi-signpost-split"></i> System Friction Overlay</div>
                    <p class="text-[11px] text-[#8b949e] leading-snug">Calculates static head (H_stat) + parabolic pipe resistance (H = H_s + k&middot;Q^2).</p>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] space-y-1 carousel-slide-card hover:border-[#f0883e]/40">
                    <div class="text-[#f0883e] font-bold flex items-center gap-1.5"><i class="bi bi-cpu"></i> Motor &amp; VFD Sizing</div>
                    <p class="text-[11px] text-[#8b949e] leading-snug">Automated IEC/NEMA electric motor kW selection with speed turndown envelopes.</p>
                  </div>
                </div>

                <!-- Slide Metric Strip -->
                <div class="flex items-center justify-between text-[11px] text-[#8b949e] pt-1.5 border-t border-[#30363d]/50 font-mono">
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>NPSHa vs NPSHr Safety</span>
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>Parallel &amp; Series Staging</span>
                  <span class="hidden sm:inline"><i class="bi bi-check2 text-[#3fb950] me-1"></i>Life-Cycle Energy Costing</span>
                </div>
              </div>

              <!-- SLIDE 5: ENTERPRISE PDF SUBMITTALS & 3-TIER RBAC -->
              <div class="w-full shrink-0 p-5 space-y-3.5">
                <div class="flex items-start gap-3">
                  <span class="w-10 h-10 rounded-xl bg-gradient-to-br from-[#8957e5]/20 to-[#bc8cff]/20 text-[#a371f7] flex items-center justify-center text-lg shrink-0 border border-[#a371f7]/30 shadow-inner">
                    <i class="bi bi-shield-lock-fill"></i>
                  </span>
                  <div>
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                      Submittal-Ready Vector PDFs &amp; Multi-Tenant RBAC
                      <span class="text-[10px] font-normal px-2 py-0.2 rounded-full bg-[#a371f7]/10 text-[#a371f7] border border-[#a371f7]/30">Enterprise Security</span>
                    </h3>
                    <p class="text-xs text-[#8b949e] mt-1 leading-relaxed">
                      Publish publication-grade 300 DPI vector datasheets for tender submissions. Restrict proprietary catalogue visibility with strict 3-tier Role-Based Access Control (No Access, Read-Only, Full Access).
                    </p>
                  </div>
                </div>

                <!-- Feature Badges -->
                <div class="grid grid-cols-3 gap-2.5 pt-1 font-mono text-xs text-center">
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] carousel-slide-card hover:border-[#3fb950]/40">
                    <div class="text-[#3fb950] font-bold text-sm"><i class="bi bi-file-earmark-pdf"></i> Vector PDF</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5">300 DPI Submittals</div>
                    <div class="text-[9px] text-[#3fb950]/70 mt-0.5">Multi-Graph Split Layout</div>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] carousel-slide-card hover:border-[#58a6ff]/40">
                    <div class="text-[#58a6ff] font-bold text-sm"><i class="bi bi-buildings"></i> Multi-Tenant</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5">SQL Scoping Ceilings</div>
                    <div class="text-[9px] text-[#58a6ff]/70 mt-0.5">Competitor Data Privacy</div>
                  </div>
                  <div class="p-2.5 rounded-lg bg-[#0d1117] border border-[#30363d] carousel-slide-card hover:border-[#bc8cff]/40">
                    <div class="text-[#bc8cff] font-bold text-sm"><i class="bi bi-person-lock"></i> 3-Tier RBAC</div>
                    <div class="text-[10px] text-[#8b949e] mt-0.5">Strict Access Levels</div>
                    <div class="text-[9px] text-[#bc8cff]/70 mt-0.5">0=None, 1=Read, 2=Full</div>
                  </div>
                </div>

                <!-- Slide Metric Strip -->
                <div class="flex items-center justify-between text-[11px] text-[#8b949e] pt-1.5 border-t border-[#30363d]/50 font-mono">
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>Pixel-Perfect Branding</span>
                  <span><i class="bi bi-check2 text-[#3fb950] me-1"></i>Zero URL Parameter Leak</span>
                  <span class="hidden sm:inline"><i class="bi bi-check2 text-[#3fb950] me-1"></i>10-Module Permission Matrix</span>
                </div>
              </div>

            </div>
          </div>

        </div>\n\n        '''

text = text[:container_start] + new_carousel_markup + text[container_end:]

# 3. Replace the controller Javascript
old_js_start = text.find('// ── 3. Marketing Carousel / Slides Controller ─────────────────────────────')
old_js_end = text.find('// ── 4. Mini "Video" Simulator Steps Data & Playback ───────────────────────')

new_js = '''  // ── 3. Marketing Carousel Controller (5-Slide Horizontal Track) ─────────────
  // Beginners Note: Controls the horizontal track carousel with smooth CSS transforms,
  // dynamic category badges, dot pagination pills, and an animated progress bar.
  // Automatically advances every 6 seconds, and pauses when hovered.
  const carouselMeta = [
    { category: "MULTI-DISCIPLINE", colorClass: "bg-[#58a6ff]/15 text-[#58a6ff] border-[#58a6ff]/30" },
    { category: "OEM CUSTOMIZATION", colorClass: "bg-[#bc8cff]/15 text-[#bc8cff] border-[#bc8cff]/30" },
    { category: "SLURRY & VISCOUS", colorClass: "bg-[#d29922]/15 text-[#d29922] border-[#d29922]/30" },
    { category: "DUTY MATCHING", colorClass: "bg-[#3fb950]/15 text-[#3fb950] border-[#3fb950]/30" },
    { category: "SECURITY & EXPORT", colorClass: "bg-[#a371f7]/15 text-[#a371f7] border-[#a371f7]/30" }
  ];

  let currentCarouselSlide = 0;
  const totalCarouselSlides = 5;
  const slideDurationMs = 6000;
  let carouselTimer = null;

  function goToCarouselSlide(idx) {
    currentCarouselSlide = (idx + totalCarouselSlides) % totalCarouselSlides;
    
    // Slide the track horizontally
    const track = document.getElementById('carouselTrack');
    if (track) {
      track.style.transform = `translateX(-${currentCarouselSlide * 100}%)`;
    }

    // Update badges
    const numBadge = document.getElementById('slideNumberBadge');
    if (numBadge) {
      numBadge.textContent = `SLIDE 0${currentCarouselSlide + 1} / 0${totalCarouselSlides}`;
    }

    const catBadge = document.getElementById('slideCategoryBadge');
    if (catBadge && carouselMeta[currentCarouselSlide]) {
      const meta = carouselMeta[currentCarouselSlide];
      catBadge.textContent = meta.category;
      catBadge.className = `px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider border ${meta.colorClass}`;
    }

    // Update dot pagination indicators
    for (let i = 0; i < totalCarouselSlides; i++) {
      const dot = document.getElementById(`cdot-${i}`);
      if (dot) {
        if (i === currentCarouselSlide) {
          dot.className = "w-6 h-1.5 rounded-full bg-[#58a6ff] transition-all cursor-pointer";
        } else {
          dot.className = "w-2 h-1.5 rounded-full bg-[#30363d] hover:bg-[#8b949e] transition-all cursor-pointer";
        }
      }
    }

    // Reset progress animation
    restartProgressBar();
  }

  function nextCarouselSlide() { goToCarouselSlide(currentCarouselSlide + 1); }
  function prevCarouselSlide() { goToCarouselSlide(currentCarouselSlide - 1); }

  // Aliases for backwards compatibility
  function goToSlide(idx) { goToCarouselSlide(idx); }
  function nextSlide() { nextCarouselSlide(); }
  function prevSlide() { prevCarouselSlide(); }

  function restartProgressBar() {
    const bar = document.getElementById('carouselProgressBar');
    if (bar) {
      bar.style.transition = 'none';
      bar.style.width = '0%';
      void bar.offsetWidth; // trigger reflow
      bar.style.transition = `width ${slideDurationMs}ms linear`;
      bar.style.width = '100%';
    }
  }

  function startCarouselAutoPlay() {
    if (carouselTimer) clearInterval(carouselTimer);
    restartProgressBar();
    carouselTimer = setInterval(nextCarouselSlide, slideDurationMs);
  }

  function stopCarouselAutoPlay() {
    if (carouselTimer) {
      clearInterval(carouselTimer);
      carouselTimer = null;
    }
    const bar = document.getElementById('carouselProgressBar');
    if (bar) {
      const computed = window.getComputedStyle(bar);
      bar.style.transition = 'none';
      bar.style.width = computed.width;
    }
  }

  // Hook pause on user hover
  const carouselEl = document.getElementById('marketingCarousel');
  if (carouselEl) {
    carouselEl.addEventListener('mouseenter', stopCarouselAutoPlay);
    carouselEl.addEventListener('mouseleave', startCarouselAutoPlay);
  }

  // Alias for autoplay start
  function startSlideAutoPlay() { startCarouselAutoPlay(); }

  '''

if old_js_start != -1 and old_js_end != -1:
    text = text[:old_js_start] + new_js + text[old_js_end:]
    print("Replaced JS controller successfully.")
else:
    print("Could not find JS controller markers:", old_js_start, old_js_end)

# 4. In DOMContentLoaded, make sure goToCarouselSlide(0) and startCarouselAutoPlay() are called
old_init = "goToSlide(0);\n    startSlideAutoPlay();"
new_init = "goToCarouselSlide(0);\n    startCarouselAutoPlay();"
if old_init in text:
    text = text.replace(old_init, new_init, 1)

with open('templates/auth/login.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("login.html updated successfully with 5-slide horizontal carousel.")
