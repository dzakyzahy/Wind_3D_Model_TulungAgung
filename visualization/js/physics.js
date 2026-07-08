/* ─────────────────────────────────────────────────────────────────────────────
 * Wind Resource Assessment 3D — Tulungagung & Trenggalek, Jawa Timur
 * Module: Handbook Physics Models & Color Interpolations (window.WindPhysics)
 * ───────────────────────────────────────────────────────────────────────────── */

window.WindPhysics = (function() {
  function lerpColor(t, stops) {
    if (t <= stops[0].t) return stops[0];
    for (let i = 1; i < stops.length; i++) {
      if (t <= stops[i].t) {
        const a = stops[i - 1], b = stops[i];
        const f = (t - a.t) / (b.t - a.t);
        return { r: a.r + (b.r - a.r) * f, g: a.g + (b.g - a.g) * f, b: a.b + (b.b - a.b) * f };
      }
    }
    return stops[stops.length - 1];
  }

  function wsColor(ws, wsMax, THREE) {
    const t = Math.min(1, Math.max(0, ws / (wsMax || 1)));
    if (t < 0.25) {
      const f = t / 0.25;
      return new THREE.Color(0.08 + 0.02 * f, 0.40 + 0.40 * f, 0.84 + 0.16 * f); // #1565d6 to Cyan
    } else if (t < 0.5) {
      const f = (t - 0.25) / 0.25;
      return new THREE.Color(0.10 + 0.10 * f, 0.80 + 0.05 * f, 1.00 - 0.70 * f); // Cyan to Green
    } else if (t < 0.75) {
      const f = (t - 0.5) / 0.25;
      return new THREE.Color(0.20 + 0.80 * f, 0.85, 0.30 - 0.30 * f); // Green to Yellow
    } else {
      const f = (t - 0.75) / 0.25;
      return new THREE.Color(1.00 - 0.06 * f, 0.85 - 0.58 * f, 0.00 + 0.27 * f); // Yellow to Red
    }
  }

  function wpdColor(t) {
    if (t < 0.5) {
      const f = t / 0.5;
      return { r: 0.98 * f, g: 0.78 * f, b: 0.004 };
    } else {
      const f = (t - 0.5) / 0.5;
      return { r: 0.98, g: 0.78 * (1 - f), b: 0 };
    }
  }

  function getPowerFromCurve(ws_ms) {
    const curve = window.WindConfig.POWER_CURVE;
    for (let i = 1; i < curve.length; i++) {
      if (ws_ms <= curve[i][0]) {
        const t = (ws_ms - curve[i - 1][0]) / (curve[i][0] - curve[i - 1][0]);
        return curve[i - 1][1] + t * (curve[i][1] - curve[i - 1][1]);
      }
    }
    return 0;
  }

  function calcCF(k, lambda) {
    if (!k || !lambda) return 0.28;
    let sum = 0, dU = 0.1;
    for (let u = 0; u < 30; u += dU) {
      const f = (k / lambda) * Math.pow(u / lambda, k - 1) * Math.exp(-Math.pow(u / lambda, k));
      sum += getPowerFromCurve(u) * f * dU;
    }
    return sum / 4500;
  }

  function calcTI(ws_mean, roughness_class = 'agricultural', layerIdx = 1) {
    const z0 = window.WindConfig.ROUGHNESS_Z0[roughness_class] || 0.05;
    const hub_h = [50, 100, 150][layerIdx] || 100;
    const sigma_u = 2.5 * 0.4 * (ws_mean || 6.8) / Math.log(hub_h / z0) * 1.15;
    return sigma_u / (ws_mean || 6.8);
  }

  function jensenWake(U_inf, x_m, Ct = 0.8, k_wake = 0.05, r0_m = 75) {
    if (x_m <= 0) return U_inf;
    const deficit = (1 - Math.sqrt(1 - Ct)) * Math.pow(r0_m / (r0_m + k_wake * x_m), 2);
    return U_inf * (1 - deficit);
  }

  function calcFarmWakeLoss(positions_m, U_inf, windDir_deg) {
    if (!positions_m || !positions_m.length) return [U_inf];
    const rad = windDir_deg * Math.PI / 180;
    const ux = Math.sin(rad), uz = Math.cos(rad);
    const U_eff = positions_m.map(() => U_inf);

    for (let j = 0; j < positions_m.length; j++) {
      for (let i = 0; i < positions_m.length; i++) {
        if (i === j) continue;
        const dx = positions_m[j][0] - positions_m[i][0];
        const dz = positions_m[j][1] - positions_m[i][1];
        const x_down = dx * ux + dz * uz;
        const y_cross = Math.abs(-dx * uz + dz * ux);
        const wake_r = 75 + 0.05 * Math.max(0, x_down);
        if (x_down > 0 && y_cross < wake_r) {
          U_eff[j] = Math.min(U_eff[j], jensenWake(U_inf, x_down));
        }
      }
    }
    return U_eff;
  }

  return {
    lerpColor,
    wsColor,
    wpdColor,
    getPowerFromCurve,
    calcCF,
    calcTI,
    jensenWake,
    calcFarmWakeLoss
  };
})();
