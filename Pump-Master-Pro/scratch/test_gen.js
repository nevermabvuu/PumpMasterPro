function generateStandardPipesCatalog() {
  const pipes = [];
  let id = 1;

  // 1. ASME B36.10M Carbon Steel
  const cs = [
    [15, '1/2"', 21.3, [['Sch 40 (STD)', 2.77, 197], ['Sch 80 (XS)', 3.73, 265]]],
    [20, '3/4"', 26.7, [['Sch 40 (STD)', 2.87, 161], ['Sch 80 (XS)', 3.91, 220]]],
    [25, '1"', 33.4, [['Sch 40 (STD)', 3.38, 152], ['Sch 80 (XS)', 4.55, 205]]],
    [32, '1-1/4"', 42.2, [['Sch 40 (STD)', 3.56, 127], ['Sch 80 (XS)', 4.85, 172]]],
    [40, '1-1/2"', 48.3, [['Sch 40 (STD)', 3.68, 114], ['Sch 80 (XS)', 5.08, 158]]],
    [50, '2"', 60.3, [['Sch 10', 2.77, 69], ['Sch 40 (STD)', 3.91, 97], ['Sch 80 (XS)', 5.54, 138], ['Sch 160', 8.74, 217]]],
    [65, '2-1/2"', 73.0, [['Sch 40 (STD)', 5.16, 106], ['Sch 80 (XS)', 7.01, 144]]],
    [80, '3"', 88.9, [['Sch 10', 3.05, 51], ['Sch 40 (STD)', 5.49, 93], ['Sch 80 (XS)', 7.62, 129], ['Sch 160', 11.13, 188]]],
    [100, '4"', 114.3, [['Sch 10', 3.05, 40], ['Sch 40 (STD)', 6.02, 79], ['Sch 80 (XS)', 8.56, 112], ['Sch 120', 11.13, 146], ['Sch 160', 13.49, 177]]],
    [125, '5"', 141.3, [['Sch 40 (STD)', 6.55, 70], ['Sch 80 (XS)', 9.53, 101]]],
    [150, '6"', 168.3, [['Sch 10', 3.40, 30], ['Sch 40 (STD)', 7.11, 63], ['Sch 80 (XS)', 10.97, 98], ['Sch 160', 18.26, 163]]],
    [200, '8"', 219.1, [['Sch 10', 3.76, 26], ['Sch 20', 6.35, 44], ['Sch 40 (STD)', 8.18, 56], ['Sch 80 (XS)', 12.70, 87], ['Sch 120', 18.26, 125], ['Sch 160', 23.01, 158]]],
    [250, '10"', 273.0, [['Sch 20', 6.35, 35], ['Sch 40 (STD)', 9.27, 51], ['Sch 80 (XS)', 15.09, 83], ['Sch 120', 21.44, 118], ['Sch 160', 28.58, 157]]],
    [300, '12"', 323.8, [['Sch 20', 6.35, 29], ['Sch 40 (STD)', 10.31, 48], ['Sch 80 (XS)', 17.48, 81]]],
    [350, '14"', 355.6, [['Sch 30', 9.53, 40], ['Sch 40 (STD)', 11.13, 47], ['Sch 80 (XS)', 19.05, 80]]],
    [400, '16"', 406.4, [['Sch 30', 9.53, 35], ['Sch 40 (STD)', 12.70, 47], ['Sch 80 (XS)', 21.44, 79]]],
    [450, '18"', 457.0, [['Sch 40 (STD)', 14.27, 47], ['Sch 80 (XS)', 23.83, 78]]],
    [500, '20"', 508.0, [['Sch 40 (STD)', 15.09, 45], ['Sch 80 (XS)', 26.19, 77]]],
    [600, '24"', 610.0, [['Sch 40 (STD)', 17.48, 43], ['Sch 80 (XS)', 30.96, 76]]]
  ];
  cs.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, p]) => {
      pipes.push({
        id: id++, standard: 'ASME B36.10M', material: 'Carbon Steel', material_key: 'commercial_steel',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: `PN ${p} bar (${Math.round(p * 14.5038)} psi)`, is_active: true
      });
    });
  });

  // 2. ASME B36.19M Stainless Steel
  const ss = [
    [15, '1/2"', 21.3, [['Sch 10S', 2.11, 148], ['Sch 40S', 2.77, 197], ['Sch 80S', 3.73, 265]]],
    [20, '3/4"', 26.7, [['Sch 10S', 2.11, 118], ['Sch 40S', 2.87, 161], ['Sch 80S', 3.91, 220]]],
    [25, '1"', 33.4, [['Sch 10S', 2.77, 124], ['Sch 40S', 3.38, 152], ['Sch 80S', 4.55, 205]]],
    [32, '1-1/4"', 42.2, [['Sch 10S', 2.77, 98], ['Sch 40S', 3.56, 127], ['Sch 80S', 4.85, 172]]],
    [40, '1-1/2"', 48.3, [['Sch 10S', 2.77, 86], ['Sch 40S', 3.68, 114], ['Sch 80S', 5.08, 158]]],
    [50, '2"', 60.3, [['Sch 10S', 2.77, 69], ['Sch 40S', 3.91, 97], ['Sch 80S', 5.54, 138]]],
    [65, '2-1/2"', 73.0, [['Sch 10S', 3.05, 63], ['Sch 40S', 5.16, 106], ['Sch 80S', 7.01, 144]]],
    [80, '3"', 88.9, [['Sch 10S', 3.05, 51], ['Sch 40S', 5.49, 93], ['Sch 80S', 7.62, 129]]],
    [100, '4"', 114.3, [['Sch 10S', 3.05, 40], ['Sch 40S', 6.02, 79], ['Sch 80S', 8.56, 112]]],
    [150, '6"', 168.3, [['Sch 10S', 3.40, 30], ['Sch 40S', 7.11, 63], ['Sch 80S', 10.97, 98]]],
    [200, '8"', 219.1, [['Sch 10S', 3.76, 26], ['Sch 40S', 8.18, 56], ['Sch 80S', 12.70, 87]]],
    [250, '10"', 273.0, [['Sch 10S', 4.19, 23], ['Sch 40S', 9.27, 51], ['Sch 80S', 12.70, 70]]],
    [300, '12"', 323.8, [['Sch 10S', 4.57, 21], ['Sch 40S', 9.53, 44], ['Sch 80S', 12.70, 59]]]
  ];
  ss.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, p]) => {
      pipes.push({
        id: id++, standard: 'ASME B36.19M', material: 'Stainless Steel', material_key: 'stainless_steel',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: `PN ${p} bar (${Math.round(p * 14.5038)} psi)`, is_active: true
      });
    });
  });

  // 3. ISO 4427 / SANS 4427 HDPE PE100
  const hdpe_sdrs = [
    ['SDR 7.4', 7.4, 'PN 25 (25 bar / 363 psi)'],
    ['SDR 9', 9.0, 'PN 20 (20 bar / 290 psi)'],
    ['SDR 11', 11.0, 'PN 16 (16 bar / 232 psi)'],
    ['SDR 13.6', 13.6, 'PN 12.5 (12.5 bar / 181 psi)'],
    ['SDR 17', 17.0, 'PN 10 (10 bar / 145 psi)'],
    ['SDR 21', 21.0, 'PN 8 (8 bar / 116 psi)'],
    ['SDR 26', 26.0, 'PN 6 (6 bar / 87 psi)'],
  ];
  const hdpe_ods = [
    [25, 20], [32, 25], [40, 32], [50, 40], [63, 50], [75, 65], [90, 80],
    [110, 100], [125, 100], [140, 125], [160, 150], [180, 150], [200, 200],
    [225, 200], [250, 250], [280, 250], [315, 300], [355, 350], [400, 400],
    [450, 450], [500, 500], [560, 500], [630, 600]
  ];
  hdpe_sdrs.forEach(([sch, sdr, rating]) => {
    hdpe_ods.forEach(([od, nb]) => {
      let wall = +(od / sdr).toFixed(2);
      if (wall < 2.0) wall = 2.0;
      const idVal = +(od - 2 * wall).toFixed(2);
      if (idVal > 0) {
        pipes.push({
          id: id++, standard: 'ISO 4427 / SANS 4427', material: 'HDPE (PE100)', material_key: 'plastic_pe',
          schedule_sdr: sch, nb_mm: nb, nb_inch: `${nb}mm`, od_mm: od, wall_thickness_mm: wall,
          id_mm: idVal, sdr: sdr, pressure_rating: rating, is_active: true
        });
      }
    });
  });

  // 4. DIN 8062 / ISO 1452 uPVC Metric
  const pvc_classes = [
    ['Class 6 / SDR 41', 41.0, 'PN 6 (6 bar / 87 psi)'],
    ['Class 9 / SDR 26', 26.0, 'PN 9 (9 bar / 130 psi)'],
    ['Class 12 / SDR 21', 21.0, 'PN 12 (12 bar / 174 psi)'],
    ['Class 16 / SDR 13.5', 13.5, 'PN 16 (16 bar / 232 psi)'],
    ['Class 20 / SDR 11', 11.0, 'PN 20 (20 bar / 290 psi)'],
  ];
  const pvc_ods = [
    [32, 25], [40, 32], [50, 40], [63, 50], [75, 65], [90, 80],
    [110, 100], [125, 100], [140, 125], [160, 150], [200, 200],
    [250, 250], [315, 300], [400, 400], [500, 500]
  ];
  pvc_classes.forEach(([sch, sdr, rating]) => {
    pvc_ods.forEach(([od, nb]) => {
      let wall = +(od / sdr).toFixed(2);
      if (wall < 1.5) wall = 1.5;
      const idVal = +(od - 2 * wall).toFixed(2);
      if (idVal > 0) {
        pipes.push({
          id: id++, standard: 'DIN 8062 / ISO 1452', material: 'uPVC', material_key: 'pvc',
          schedule_sdr: sch, nb_mm: nb, nb_inch: `${nb}mm`, od_mm: od, wall_thickness_mm: wall,
          id_mm: idVal, sdr: sdr, pressure_rating: rating, is_active: true
        });
      }
    });
  });

  // 5. ASTM D1785 PVC IPS
  const pvc_ips = [
    [15, '1/2"', 21.3, [['Sch 40', 2.77, 'PN 41 (600 psi)'], ['Sch 80', 3.73, 'PN 59 (850 psi)']]],
    [20, '3/4"', 26.7, [['Sch 40', 2.87, 'PN 33 (480 psi)'], ['Sch 80', 3.91, 'PN 48 (690 psi)']]],
    [25, '1"', 33.4, [['Sch 40', 3.38, 'PN 31 (450 psi)'], ['Sch 80', 4.55, 'PN 43 (630 psi)']]],
    [32, '1-1/4"', 42.2, [['Sch 40', 3.56, 'PN 25 (370 psi)'], ['Sch 80', 4.85, 'PN 36 (520 psi)']]],
    [40, '1-1/2"', 48.3, [['Sch 40', 3.68, 'PN 23 (330 psi)'], ['Sch 80', 5.08, 'PN 32 (470 psi)']]],
    [50, '2"', 60.3, [['Sch 40', 3.91, 'PN 19 (280 psi)'], ['Sch 80', 5.54, 'PN 28 (400 psi)']]],
    [65, '2-1/2"', 73.0, [['Sch 40', 5.16, 'PN 21 (300 psi)'], ['Sch 80', 7.01, 'PN 29 (420 psi)']]],
    [80, '3"', 88.9, [['Sch 40', 5.49, 'PN 18 (260 psi)'], ['Sch 80', 7.62, 'PN 26 (370 psi)']]],
    [100, '4"', 114.3, [['Sch 40', 6.02, 'PN 15 (220 psi)'], ['Sch 80', 8.56, 'PN 22 (320 psi)']]],
    [150, '6"', 168.3, [['Sch 40', 7.11, 'PN 12 (180 psi)'], ['Sch 80', 10.97, 'PN 19 (280 psi)']]],
    [200, '8"', 219.1, [['Sch 40', 8.18, 'PN 11 (160 psi)'], ['Sch 80', 12.70, 'PN 17 (250 psi)']]],
    [250, '10"', 273.0, [['Sch 40', 9.27, 'PN 10 (140 psi)'], ['Sch 80', 15.09, 'PN 16 (230 psi)']]],
    [300, '12"', 323.8, [['Sch 40', 10.31, 'PN 9 (130 psi)'], ['Sch 80', 17.48, 'PN 16 (230 psi)']]]
  ];
  pvc_ips.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, rating]) => {
      pipes.push({
        id: id++, standard: 'ASTM D1785 (PVC)', material: 'uPVC', material_key: 'pvc',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: rating, is_active: true
      });
    });
  });

  // 6. EN 545 / ISO 2531 Ductile Iron
  const di = [
    [80, '3"', 98.0, [['Class C40', 4.4, 'PN 40 (40 bar)'], ['Class K9', 6.0, 'PN 50 (50 bar)']]],
    [100, '4"', 118.0, [['Class C40', 4.4, 'PN 40 (40 bar)'], ['Class K9', 6.0, 'PN 50 (50 bar)']]],
    [150, '6"', 170.0, [['Class C40', 4.5, 'PN 40 (40 bar)'], ['Class K9', 6.0, 'PN 45 (45 bar)']]],
    [200, '8"', 222.0, [['Class C40', 4.7, 'PN 40 (40 bar)'], ['Class K9', 6.3, 'PN 40 (40 bar)']]],
    [250, '10"', 274.0, [['Class C40', 5.5, 'PN 40 (40 bar)'], ['Class K9', 6.8, 'PN 35 (35 bar)']]],
    [300, '12"', 326.0, [['Class C40', 6.2, 'PN 40 (40 bar)'], ['Class K9', 7.2, 'PN 32 (32 bar)']]],
    [350, '14"', 378.0, [['Class C30', 6.3, 'PN 30 (30 bar)'], ['Class K9', 7.7, 'PN 30 (30 bar)']]],
    [400, '16"', 429.0, [['Class C30', 6.5, 'PN 30 (30 bar)'], ['Class K9', 8.1, 'PN 30 (30 bar)']]],
    [500, '20"', 532.0, [['Class C30', 7.5, 'PN 30 (30 bar)'], ['Class K9', 9.0, 'PN 28 (28 bar)']]],
    [600, '24"', 635.0, [['Class C25', 7.9, 'PN 25 (25 bar)'], ['Class K9', 9.9, 'PN 25 (25 bar)']]]
  ];
  di.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, rating]) => {
      pipes.push({
        id: id++, standard: 'EN 545 / ISO 2531', material: 'Ductile Iron', material_key: 'ductile_iron',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: rating, is_active: true
      });
    });
  });

  // 7. SANS 62 / BS 1387 Galvanised Steel
  const galv = [
    [15, '1/2"', 21.3, [['Medium (Class B)', 2.65, 'PN 25 (25 bar)'], ['Heavy (Class C)', 3.25, 'PN 32 (32 bar)']]],
    [20, '3/4"', 26.9, [['Medium (Class B)', 2.65, 'PN 25 (25 bar)'], ['Heavy (Class C)', 3.25, 'PN 32 (32 bar)']]],
    [25, '1"', 33.7, [['Medium (Class B)', 3.25, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.05, 'PN 32 (32 bar)']]],
    [32, '1-1/4"', 42.4, [['Medium (Class B)', 3.25, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.05, 'PN 32 (32 bar)']]],
    [40, '1-1/2"', 48.3, [['Medium (Class B)', 3.25, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.05, 'PN 32 (32 bar)']]],
    [50, '2"', 60.3, [['Medium (Class B)', 3.65, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.50, 'PN 32 (32 bar)']]],
    [65, '2-1/2"', 76.1, [['Medium (Class B)', 3.65, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.50, 'PN 32 (32 bar)']]],
    [80, '3"', 88.9, [['Medium (Class B)', 4.05, 'PN 25 (25 bar)'], ['Heavy (Class C)', 4.85, 'PN 32 (32 bar)']]],
    [100, '4"', 114.3, [['Medium (Class B)', 4.50, 'PN 25 (25 bar)'], ['Heavy (Class C)', 5.40, 'PN 32 (32 bar)']]],
    [150, '6"', 165.1, [['Medium (Class B)', 4.85, 'PN 25 (25 bar)'], ['Heavy (Class C)', 5.40, 'PN 32 (32 bar)']]]
  ];
  galv.forEach(([nb, inch, od, list]) => {
    list.forEach(([sch, wall, rating]) => {
      pipes.push({
        id: id++, standard: 'SANS 62 / BS 1387', material: 'Galvanised Steel', material_key: 'galvanized_iron',
        schedule_sdr: sch, nb_mm: nb, nb_inch: inch, od_mm: od, wall_thickness_mm: wall,
        id_mm: +(od - 2 * wall).toFixed(2), sdr: +(od / wall).toFixed(1),
        pressure_rating: rating, is_active: true
      });
    });
  });

  return pipes;
}

const catalog = generateStandardPipesCatalog();
console.log('Generated catalog count:', catalog.length);
const standards = Array.from(new Set(catalog.map(p => p.standard)));
console.log('Standards:', standards);
