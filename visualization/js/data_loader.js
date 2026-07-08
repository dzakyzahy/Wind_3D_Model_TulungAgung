/* ─────────────────────────────────────────────────────────────────────────────
 * Wind Resource Assessment 3D — Tulungagung & Trenggalek, Jawa Timur
 * Module: Data Loader & Demo Data Generator (window.WindDataLoader)
 * ───────────────────────────────────────────────────────────────────────────── */

window.WindDataLoader = (function() {
  function smoothTerrain(arr, nx, nz, passes = 3) {
    let out = arr.slice();
    for (let p = 0; p < passes; p++) {
      const tmp = out.slice();
      for (let r = 1; r < nz - 1; r++) {
        for (let c = 1; c < nx - 1; c++) {
          tmp[r * nx + c] = (
            out[(r - 1) * nx + c] + out[(r + 1) * nx + c] +
            out[r * nx + (c - 1)] + out[r * nx + (c + 1)] + out[r * nx + c] * 2
          ) / 6;
        }
      }
      out = tmp;
    }
    return out;
  }

  function makeDemoData() {
    const NX = 60, NZ = 60;
    const flat_terrain = [];
    for (let r = 0; r < NZ; r++) {
      for (let c = 0; c < NX; c++) {
        const x = (c / NX - 0.5) * 2, y = (r / NZ - 0.5) * 2;
        const wilis = 0.88 * Math.exp(-((x + 0.38) ** 2 + (y - 0.42) ** 2) / 0.18);
        const hills = 0.52 * Math.exp(-((x - 0.55) ** 2 + (y + 0.38) ** 2) / 0.15)
          + 0.42 * Math.exp(-((x + 0.10) ** 2 + (y + 0.50) ** 2) / 0.10)
          + 0.36 * Math.exp(-((x - 0.25) ** 2 + (y + 0.42) ** 2) / 0.12);
        const ridge = 0.38 * Math.exp(-Math.pow(x + 0.65, 2) / 0.022) * Math.exp(-Math.pow(y, 2) / 0.45);
        const valley = 0.18 * Math.max(0, 1 - Math.abs(x + 0.05) * 6) * Math.exp(-Math.pow(y, 2) / 0.25);
        const coastal_slope = 0.12 * Math.max(0, y + 0.3);
        const noise = 0.03 * Math.sin(x * 8.3 + 1.2) * Math.cos(y * 7.1 + 0.8)
          + 0.015 * Math.sin(x * 15.2 + y * 11.3);
        const raw = wilis + hills + ridge + valley - coastal_slope + noise;
        flat_terrain.push(raw);
      }
    }
    const tMin = Math.min(...flat_terrain);
    const tMax = Math.max(...flat_terrain);
    const tRange = tMax - tMin;
    for (let i = 0; i < flat_terrain.length; i++) {
      flat_terrain[i] = (flat_terrain[i] - tMin) / tRange;
    }
    const terrain = smoothTerrain(flat_terrain, NX, NZ, 4);
    const AIR_RHO = window.WindConfig.AIR_RHO || 1.225;
    const layers = [50, 100, 150].map(h => {
      const u = [], v = [], wspd = [];
      for (let r = 0; r < NZ; r++) {
        const ru = [], rv = [], rw = [];
        for (let c = 0; c < NX; c++) {
          const x = (c / NX - 0.5) * 2, y = (r / NZ - 0.5) * 2;
          const uv = (3.5 + 2 * Math.sin(x * 2) * Math.cos(y)) * (h / 100);
          const vv = (-1.2 + 0.8 * Math.cos(x)) * (h / 100);
          ru.push(uv); rv.push(vv); rw.push(Math.sqrt(uv ** 2 + vv ** 2));
        }
        u.push(ru); v.push(rv); wspd.push(rw);
      }
      const wpd = wspd.map(rw => rw.map(w => 0.5 * AIR_RHO * w ** 3));
      return { agl: h, u, v, wspd, wpd };
    });
    return {
      meta: {
        nx: NX, nz: NZ, n_levels: 3, levels_m_agl: [50, 100, 150],
        elev_min_m: 0, elev_max_m: 2550, is_demo: true
      },
      terrain, wind_layers: layers,
      stats: {
        wspd_mean_100m: 6.8, wpd_mean_100m: 185, cf_mean_100m: 0.28,
        weibull_k: 2.15, weibull_lambda: 7.5, v50_ms: 27.5, iec_class: 'III', is_demo: true
      }
    };
  }

  async function tryFetch(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function loadData(setProgress) {
    let windData = null;
    let wakeData = null;

    setProgress(10, 'Memuat data pemodelan angin…');
    if (window.WIND_DATA_BUNDLE) {
      console.log('[DataLoader] Memuat dari window.WIND_DATA_BUNDLE');
      windData = window.WIND_DATA_BUNDLE.windData || null;
      wakeData = window.WIND_DATA_BUNDLE.wakeData || null;
      const ss = window.WIND_DATA_BUNDLE.statsSummary;
      if (ss && windData) {
        windData.stats = {
          ...(windData.stats || {}), ...ss.wind_resource,
          v50_ms: ss.extreme_wind?.v50_ms, iec_class: ss.extreme_wind?.iec_class
        };
      }
    } else {
      console.log('[DataLoader] Bundle tidak ada, mencoba fetch file JSON…');
      try {
        windData = await tryFetch('wind_data.json');
      } catch (e) {
        console.warn('wind_data.json tidak ditemukan atau CORS block, pakai demo:', e);
        windData = makeDemoData();
      }

      setProgress(35, 'Memuat wake_data.json…');
      try {
        wakeData = await tryFetch('wake_data.json');
      } catch (e) {
        console.warn('wake_data.json tidak ditemukan');
        wakeData = null;
      }

      setProgress(55, 'Memuat stats_summary.json…');
      try {
        const ss = await tryFetch('stats_summary.json');
        if (ss) {
          windData.stats = {
            ...(windData.stats || {}), ...ss.wind_resource,
            v50_ms: ss.extreme_wind?.v50_ms, iec_class: ss.extreme_wind?.iec_class
          };
        }
      } catch (e) {
        console.warn('stats_summary.json tidak ditemukan');
      }
    }

    if (windData.meta?.is_demo || windData.stats?.is_demo) {
      const demoOverlay = document.getElementById('demo-overlay');
      if (demoOverlay) demoOverlay.style.display = 'block';
    }

    return { windData, wakeData };
  }

  return {
    smoothTerrain,
    makeDemoData,
    loadData
  };
})();
