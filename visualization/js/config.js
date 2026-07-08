/* ─────────────────────────────────────────────────────────────────────────────
 * Wind Resource Assessment 3D — Tulungagung & Trenggalek, Jawa Timur
 * Module: Configuration & Domain Constants (window.WindConfig)
 * ───────────────────────────────────────────────────────────────────────────── */

window.WindConfig = (function() {
  const TS = 20;            // Terrain Scene Size in World Units (WU)
  const DOMAIN_KM = 222.0;  // Real world domain size in km (2° x 2° WGS84 bounding box)
  const WU_PER_KM = TS / DOMAIN_KM;

  const COLOR_STOPS = [
    { t: -1.37, r: 0.010, g: 0.040, b: 0.150 },  // Palung Jawa terdalam (-3665m) - Deep Navy
    { t: -0.80, r: 0.020, g: 0.100, b: 0.320 },  // Abyssal plain (-2100m) - Royal Blue
    { t: -0.40, r: 0.030, g: 0.220, b: 0.500 },  // Lereng benua tengah (-1000m) - Oceanic Blue
    { t: -0.15, r: 0.060, g: 0.400, b: 0.650 },  // Lereng benua atas (-400m) - Cerulean
    { t: -0.03, r: 0.120, g: 0.600, b: 0.750 },  // Paparan benua dangkal (-80m) - Tropical Teal/Cyan
    { t:  0.00, r: 0.820, g: 0.750, b: 0.520 },  // Bibir pantai pasir emas (0m) - Sand Gold
    { t:  0.05, r: 0.140, g: 0.380, b: 0.200 },  // Dataran rendah (130m)
    { t:  0.20, r: 0.259, g: 0.490, b: 0.173 },  // Hutan perkebunan (500m)
    { t:  0.45, r: 0.545, g: 0.400, b: 0.149 },  // Lereng pegunungan (1200m)
    { t:  0.72, r: 0.686, g: 0.545, b: 0.345 },  // Bebatuan pegunungan (1900m)
    { t:  1.00, r: 0.918, g: 0.918, b: 0.949 },  // Puncak gunung Wilis (2563m)
  ];

  const ROUGHNESS_Z0 = {
    sea: 0.0001,
    shore: 0.001,
    open_flat: 0.01,
    agricultural: 0.05,
    forest: 0.30,
    urban: 0.50
  };

  const POWER_CURVE = [
    [0, 0], [1, 0], [2, 0], [3, 50], [4, 170], [5, 390], [6, 745], [7, 1200],
    [8, 1810], [9, 2560], [10, 3290], [11, 3870], [12, 4350], [13, 4460],
    [14, 4490], [15, 4500], [16, 4500], [17, 4500], [18, 4500], [19, 4500],
    [20, 4500], [25, 4500], [26, 0]
  ];

  const INITIAL_CAM = { x: 0, y: 10, z: 22 };

  const LABELS = [
    { text: '⛰ G. Wilis (2563m)', x: -0.42, y: 3.8, z: -4.82, color: '#ffd700' },
    { text: '⛰ G. Kelud (1731m)', x: 5.08, y: 2.6, z: -3.60, color: '#fde047' },
    { text: '🏙 Tulungagung', x: 1.03, y: 0.7, z: -2.32, color: '#7dd3fc' },
    { text: '🏙 Trenggalek', x: -0.84, y: 0.7, z: -2.40, color: '#38bdf8' },
    { text: '🏙 Blitar', x: 3.65, y: 0.8, z: -1.92, color: '#60a5fa' },
    { text: '🏖 Pantai Niyama', x: 0.00, y: 0.4, z: -0.35, color: '#ff6b35' },
    { text: '🏖 Pantai Prigi', x: -0.70, y: 0.4, z: -0.05, color: '#fb923c' }
  ];

  const SCALE_INCREMENTS_KM = [0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500];

  return {
    AIR_RHO: 1.225,
    TS,
    DOMAIN_KM,
    WU_PER_KM,
    COLOR_STOPS,
    ROUGHNESS_Z0,
    POWER_CURVE,
    INITIAL_CAM,
    LABELS,
    SCALE_INCREMENTS_KM,
    TRAIL_LEN: 8,
    MAX_GHOST_TRAILS: 200
  };
})();
