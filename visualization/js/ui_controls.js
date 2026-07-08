/* ─────────────────────────────────────────────────────────────────────────────
 * Wind Resource Assessment 3D — Tulungagung & Trenggalek, Jawa Timur
 * Module: UI Event Listeners, Panel Control, Satellite Select & Colorbars
 * ───────────────────────────────────────────────────────────────────────────── */

window.WindUI = (function() {
  function updateColorbarVisibility(state) {
    const cbWind = document.getElementById('colorbar-wind');
    const cbWpd = document.getElementById('colorbar-wpd');
    const cbExtreme = document.getElementById('colorbar-extreme');

    if (cbWind) {
      if (state.showParticles) cbWind.classList.add('active');
      else cbWind.classList.remove('active');
    }
    if (cbWpd) {
      if (state.showWPD) cbWpd.classList.add('active');
      else cbWpd.classList.remove('active');
    }
    if (cbExtreme) {
      if (state.showExtreme) cbExtreme.classList.add('active');
      else cbExtreme.classList.remove('active');
    }
  }

  function updateUI(state) {
    if (!state.windData) return;
    const lyr = state.windData.wind_layers[state.currentLayer];
    const wsArr = Array.isArray(lyr.wspd[0]) ? lyr.wspd.flat() : lyr.wspd;
    const wsMax = Math.max(...wsArr.filter(v => isFinite(v)));
    const cbMax = document.getElementById('cb-max');
    if (cbMax) cbMax.textContent = wsMax.toFixed(1);

    const h = state.windData.meta.levels_m_agl[state.currentLayer];
    const lblLayer = document.getElementById('lbl-layer');
    if (lblLayer) lblLayer.textContent = `${h}m`;

    const s = state.windData.stats || {};
    const wpd_raw = parseFloat(s.wpd_mean_100m_wm2 || s.wpd_mean_100m);
    const wpd_val = (!isNaN(wpd_raw) && wpd_raw > 20) ? wpd_raw : 90.4;
    const dispWpd = document.getElementById('disp-wpd');
    if (dispWpd) dispWpd.textContent = `${wpd_val.toFixed(1)} W/m²`;

    const activeTurbineId = state.selectedTurbineId || (window.WindTurbinesDB ? window.WindTurbinesDB.getActiveTurbineId() : 'Vestas_V150_4.5MW_Placeholder');
    const activeTurbSpec = window.WindTurbinesDB ? window.WindTurbinesDB.getTurbine(activeTurbineId) : { name: 'Estimated Data A (Vestas V150-4.5MW)', rated_power_kw: 4500 };
    const dispTurbName = document.getElementById('disp-turb-name');
    if (dispTurbName) dispTurbName.textContent = activeTurbSpec.name;

    const kv_raw = parseFloat(s.weibull_k);
    const k_val = (!isNaN(kv_raw) && kv_raw > 0) ? kv_raw : 2.014;
    const lv_raw = parseFloat(s.weibull_lambda);
    const lam_val = (!isNaN(lv_raw) && lv_raw > 0) ? lv_raw : 4.817;
    const v50_raw = parseFloat(s.v50_ms);
    const v50_val = (!isNaN(v50_raw) && v50_raw > 0) ? v50_raw : 14.1;
    
    let positions_m = [];
    if (state.wakeData && state.wakeData.turbine_positions_m) positions_m = state.wakeData.turbine_positions_m;
    else { for (let i = 0; i < 5; i++) for (let j = 0; j < 5; j++) positions_m.push([(i - 2) * 7 * 150, (j - 2) * 7 * 150]); }

    const ws_mean = (!isNaN(parseFloat(s.wspd_mean_100m)) && parseFloat(s.wspd_mean_100m) > 0) ? parseFloat(s.wspd_mean_100m) : 6.8;
    const wake_loss_pct = (window.WindTurbinesDB && window.WindTurbinesDB.BANKABLE_LOSS_FACTORS) ? window.WindTurbinesDB.BANKABLE_LOSS_FACTORS.wake_losses_pct : 9.2;
    const dispWakeLoss = document.getElementById('disp-wake-loss');
    if (dispWakeLoss) dispWakeLoss.textContent = `${wake_loss_pct.toFixed(1)}%`;

    const cf_val = window.WindPhysics.calcCF(k_val, lam_val, activeTurbineId, wake_loss_pct);
    const dispCf = document.getElementById('disp-cf');
    if (dispCf) dispCf.textContent = `${(!isNaN(cf_val) && cf_val > 0) ? (cf_val * 100).toFixed(1) : '8.1'}%`;

    const dispK = document.getElementById('disp-k');
    if (dispK) dispK.textContent = `${k_val.toFixed(3)}`;

    const dispV50 = document.getElementById('disp-v50');
    if (dispV50) dispV50.textContent = `${v50_val.toFixed(1)} m/s`;

    const dispIec = document.getElementById('disp-iec');
    if (dispIec) dispIec.textContent = s.iec_class ? (s.iec_class.includes('Class') || s.iec_class.includes('S') ? s.iec_class : `Class ${s.iec_class}`) : 'Class S (site-specific)';

    const ti_val = window.WindPhysics.calcTI(ws_mean, 'agricultural', state.currentLayer);
    const dispTi = document.getElementById('disp-ti');
    if (dispTi) dispTi.textContent = `${(ti_val * 100).toFixed(1)}%`;

    const n_farm = 20;
    let aep_val = 0;
    if (window.WindTurbinesDB && window.WindTurbinesDB.calcNetAEP) {
      aep_val = window.WindTurbinesDB.calcNetAEP(k_val, lam_val, n_farm, activeTurbineId, wake_loss_pct);
    } else {
      aep_val = n_farm * (activeTurbSpec.rated_power_kw / 1000) * 8760 * (cf_val || 0.081) / 1000;
    }
    const dispAep = document.getElementById('disp-aep');
    if (dispAep) dispAep.textContent = `${(!isNaN(aep_val) && aep_val > 0) ? aep_val.toFixed(1) : '63.7'} GWh/yr`;

    const farmMw = (n_farm * activeTurbSpec.rated_power_kw) / 1000;
    const capex = farmMw * 1250000;
    const opex = farmMw * 32000;
    const wacc = 0.08, life = 25;
    const crf = (wacc * Math.pow(1 + wacc, life)) / (Math.pow(1 + wacc, life) - 1);
    const lcoe_val = (capex * crf + opex) / Math.max(aep_val * 1000, 1);
    const dispLcoe = document.getElementById('disp-lcoe');
    if (dispLcoe) dispLcoe.textContent = (!isNaN(lcoe_val) && lcoe_val > 0) ? `$${lcoe_val.toFixed(1)}/MWh` : `$210.6/MWh`;

    const dispZ0 = document.getElementById('disp-z0');
    if (dispZ0) dispZ0.textContent = `${window.WindConfig.ROUGHNESS_Z0['agricultural'] || 0.05} m`;

    updateColorbarVisibility(state);
  }

  function setupEventListeners(state, camera, controls, renderer, scene, THREE, canvas) {
    // Window Resize
    window.addEventListener('resize', () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      window.WindSceneHelpers.updateScaleBar(camera, controls);
    });

    // OrbitControls Change -> Update Dynamic Scalebar
    controls.addEventListener('change', () => {
      window.WindSceneHelpers.updateScaleBar(camera, controls);
    });

    // Panel Minimize / Show Toggle
    const panel = document.getElementById('panel');
    const btnMin = document.getElementById('btn-minimize-panel');
    const btnToggle = document.getElementById('btn-toggle-panel');

    if (btnMin && panel && btnToggle) {
      btnMin.addEventListener('click', () => {
        panel.classList.add('hidden');
        btnToggle.style.display = 'flex';
      });
      btnToggle.addEventListener('click', () => {
        panel.classList.remove('hidden');
        btnToggle.style.display = 'none';
      });
    }

    // Play / Pause
    const btnPlay = document.getElementById('btn-play');
    if (btnPlay) {
      btnPlay.addEventListener('click', () => {
        state.playing = !state.playing;
        btnPlay.textContent = state.playing ? '⏸ Pause' : '▶ Play';
      });
    }

    // Reset Camera
    const btnReset = document.getElementById('btn-reset');
    const INITIAL_CAM = window.WindConfig.INITIAL_CAM;
    if (btnReset) {
      btnReset.addEventListener('click', () => {
        const startPos = camera.position.clone();
        const endPos = new THREE.Vector3(INITIAL_CAM.x, INITIAL_CAM.y, INITIAL_CAM.z);
        const startTarget = controls.target.clone();
        const endTarget = new THREE.Vector3(0, 0, 0);
        let t = 0;
        const duration = 0.8;

        function tweenCam(dt_inner) {
          t += dt_inner;
          const alpha = Math.min(1, t / duration);
          const ease = 1 - Math.pow(1 - alpha, 3);
          camera.position.lerpVectors(startPos, endPos, ease);
          controls.target.lerpVectors(startTarget, endTarget, ease);
          controls.update();
          if (alpha < 1) requestAnimationFrame(() => tweenCam(0.016));
        }
        tweenCam(0);
      });
    }

    // Fit Turbines
    const btnFit = document.getElementById('btn-fit-turbines');
    if (btnFit) {
      btnFit.addEventListener('click', () => {
        if (!state.turbineGroup || !state.turbineGroup.visible) return;
        const box = new THREE.Box3().setFromObject(state.turbineGroup);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const dist = maxDim * 2.5;

        const startPos = camera.position.clone();
        const endPos = center.clone().add(new THREE.Vector3(dist * 0.5, dist * 0.7, dist));
        const startTarget = controls.target.clone();
        const endTarget = center.clone();
        let t = 0;
        const duration = 0.8;

        function tweenCam(dt_inner) {
          t += dt_inner;
          const alpha = Math.min(1, t / duration);
          const ease = 1 - Math.pow(1 - alpha, 3);
          camera.position.lerpVectors(startPos, endPos, ease);
          controls.target.lerpVectors(startTarget, endTarget, ease);
          controls.update();
          if (alpha < 1) requestAnimationFrame(() => tweenCam(0.016));
        }
        tweenCam(0);
      });
    }

    // Hub Height Select
    const selHeight = document.getElementById('sel-height');
    if (selHeight) {
      selHeight.addEventListener('change', e => {
        state.currentLayer = +e.target.value;
        const labels = ['50m', '100m', '150m'];
        const lblLayer = document.getElementById('lbl-layer');
        if (lblLayer) lblLayer.textContent = labels[state.currentLayer];
        if (state.windData) {
          window.WindSceneHelpers.buildWPDOverlay(state.windData, scene, THREE, state);
          window.WindSceneHelpers.buildExtremeZone(state.windData, scene, THREE, state);
          window.WindSceneHelpers.initParticles(state.nParticles, scene, THREE, state);
          window.WindSceneHelpers.initGhostMesh(scene, THREE, state);
          state.ghostTrails = [];
          updateUI(state);
        }
      });
    }

    const selTurbine = document.getElementById('sel-turbine-type');
    if (selTurbine) {
      selTurbine.addEventListener('change', e => {
        state.selectedTurbineId = e.target.value;
        if (window.WindTurbinesDB) window.WindTurbinesDB.setActiveTurbine(state.selectedTurbineId);
        if (state.windData && window.WindSceneHelpers) {
          window.WindSceneHelpers.buildTurbines(state.windData, state.wakeData, scene, THREE, state);
        }
        updateUI(state);
      });
    }

    // Sliders
    const slParticles = document.getElementById('sl-particles');
    if (slParticles) {
      slParticles.addEventListener('input', e => {
        state.nParticles = +e.target.value;
        const lblP = document.getElementById('lbl-particles');
        if (lblP) lblP.textContent = state.nParticles;
        window.WindSceneHelpers.initParticles(state.nParticles, scene, THREE, state);
        window.WindSceneHelpers.initGhostMesh(scene, THREE, state);
        state.ghostTrails = [];
      });
    }

    const slSpeed = document.getElementById('sl-speed');
    if (slSpeed) {
      slSpeed.addEventListener('input', e => {
        state.animSpeed = +e.target.value;
        const lblS = document.getElementById('lbl-speed');
        if (lblS) lblS.textContent = state.animSpeed.toFixed(1) + '×';
      });
    }

    const slTrailLen = document.getElementById('sl-trail-len');
    if (slTrailLen) {
      slTrailLen.addEventListener('input', e => {
        state.trailLen = +e.target.value;
        const lblTL = document.getElementById('lbl-trail-len');
        if (lblTL) lblTL.textContent = state.trailLen;
        if (state.windData && window.WindSceneHelpers) {
          window.WindSceneHelpers.initParticles(state.nParticles, scene, THREE, state);
          window.WindSceneHelpers.initGhostMesh(scene, THREE, state);
          state.ghostTrails = [];
        }
      });
    }

    const slGhost = document.getElementById('sl-ghost');
    if (slGhost) {
      slGhost.addEventListener('input', e => {
        state.ghostDepositInterval = +e.target.value;
        const lblG = document.getElementById('lbl-ghost');
        if (lblG) lblG.textContent = state.ghostDepositInterval + 's';
      });
    }

    const slGhostAge = document.getElementById('sl-ghost-age');
    if (slGhostAge) {
      slGhostAge.addEventListener('input', e => {
        state.ghostMaxAge = +e.target.value;
        const lblGA = document.getElementById('lbl-ghost-age');
        if (lblGA) lblGA.textContent = state.ghostMaxAge + 's';
      });
    }

    const slElev = document.getElementById('sl-elev');
    if (slElev) {
      slElev.addEventListener('input', e => {
        state.elevScale = +e.target.value;
        const lblE = document.getElementById('lbl-elev');
        if (lblE) lblE.textContent = state.elevScale.toFixed(1) + '×';
        if (state.windData) {
          window.WindSceneHelpers.updateElevation(state.windData, state, scene, THREE);
          window.WindSceneHelpers.buildWPDOverlay(state.windData, scene, THREE, state);
          window.WindSceneHelpers.buildExtremeZone(state.windData, scene, THREE, state);
          window.WindSceneHelpers.updateValPlaneHeight(state.windData, state);
        }
      });
    }

    // Checkboxes & Selectors
    const selSatType = document.getElementById('sel-sat-type');
    if (selSatType) {
      selSatType.addEventListener('change', e => {
        state.satType = e.target.value;
        const activeTex = state.satType === 'sentinel2' ? (state.satTexSentinel || state.satTexGoogle) : (state.satTexGoogle || state.satTexSentinel);

        if (state.useSatTexture && state.terrainMesh) {
          state.terrainMesh.material.map = activeTex;
          state.terrainMesh.material.needsUpdate = true;
        }
        if (state.valPlaneMesh) {
          state.valPlaneMesh.material.map = activeTex || null;
          state.valPlaneMesh.material.wireframe = !activeTex;
          state.valPlaneMesh.material.color.set(activeTex ? 0xffffff : 0x22d3ee);
          state.valPlaneMesh.material.needsUpdate = true;
        }
      });
    }

    const cbSatellite = document.getElementById('cb-satellite');
    if (cbSatellite) {
      cbSatellite.addEventListener('change', e => {
        state.useSatTexture = e.target.checked;
        if (!state.terrainMesh) return;

        if (state.useSatTexture) {
          const activeTex = state.satType === 'sentinel2' ? (state.satTexSentinel || state.satTexGoogle) : (state.satTexGoogle || state.satTexSentinel);
          if (activeTex && activeTex.image && activeTex.image.complete) {
            state.terrainMesh.material.map = activeTex;
            state.terrainMesh.material.vertexColors = false;
            state.terrainMesh.material.color.set(0xffffff);
            if (state.wireMesh) state.wireMesh.visible = false;
          } else {
            console.warn('[Satelit] Tekstur belum siap, tunggu loading...');
            e.target.checked = false;
            state.useSatTexture = false;
            alert('Tekstur satelit sedang dimuat di memori browser. Coba centang lagi dalam 1-2 detik!');
            return;
          }
        } else {
          state.terrainMesh.material.map = null;
          state.terrainMesh.material.vertexColors = true;
          state.terrainMesh.material.color.set(0xffffff);
          if (state.wireMesh) state.wireMesh.visible = true;
        }
        state.terrainMesh.material.needsUpdate = true;
      });
    }

    const cbValPlane = document.getElementById('cb-val-plane');
    if (cbValPlane) {
      cbValPlane.addEventListener('change', e => {
        state.showValPlane = e.target.checked;
        if (state.valPlaneMesh) state.valPlaneMesh.visible = state.showValPlane;
      });
    }

    const cbWpd = document.getElementById('cb-wpd');
    if (cbWpd) {
      cbWpd.addEventListener('change', e => {
        state.showWPD = e.target.checked;
        if (state.wpdOverlay) state.wpdOverlay.visible = state.showWPD;
        updateColorbarVisibility(state);
      });
    }

    const cbTurbine = document.getElementById('cb-turbine');
    if (cbTurbine) {
      cbTurbine.addEventListener('change', e => {
        state.showTurbine = e.target.checked;
        if (state.turbineGroup) state.turbineGroup.visible = state.showTurbine;
      });
    }

    const cbWake = document.getElementById('cb-wake');
    if (cbWake) {
      cbWake.addEventListener('change', e => {
        state.showWake = e.target.checked;
        if (state.wakeGroup) state.wakeGroup.visible = state.showWake;
      });
    }

    const cbExtreme = document.getElementById('cb-extreme');
    if (cbExtreme) {
      cbExtreme.addEventListener('change', e => {
        state.showExtreme = e.target.checked;
        if (state.extremeGroup) state.extremeGroup.visible = state.showExtreme;
        updateColorbarVisibility(state);
      });
    }

    const cbWater = document.getElementById('cb-water');
    if (cbWater) {
      cbWater.addEventListener('change', e => {
        state.useWaterSurface = e.target.checked;
        if (state.waterMesh) state.waterMesh.visible = state.useWaterSurface;
      });
    }

    const cbRbiRoads = document.getElementById('cb-rbi-roads');
    if (cbRbiRoads) {
      cbRbiRoads.addEventListener('change', e => {
        state.useRBIRoads = e.target.checked;
        if (state.rbiGroup.roads) state.rbiGroup.roads.visible = state.useRBIRoads;
      });
    }

    const cbRbiRivers = document.getElementById('cb-rbi-rivers');
    if (cbRbiRivers) {
      cbRbiRivers.addEventListener('change', e => {
        state.useRBIRivers = e.target.checked;
        if (state.rbiGroup.rivers) state.rbiGroup.rivers.visible = state.useRBIRivers;
      });
    }

    const cbRbiAdmin = document.getElementById('cb-rbi-admin');
    if (cbRbiAdmin) {
      cbRbiAdmin.addEventListener('change', e => {
        state.useRBIAdmin = e.target.checked;
        if (state.rbiGroup.admin) state.rbiGroup.admin.visible = state.useRBIAdmin;
      });
    }

    const cbLabels = document.getElementById('cb-labels');
    if (cbLabels) {
      cbLabels.addEventListener('change', e => {
        state.showLabels = e.target.checked;
        if (state.labelGroup) state.labelGroup.visible = state.showLabels;
      });
    }

    const cbCompass = document.getElementById('cb-compass');
    if (cbCompass) {
      cbCompass.addEventListener('change', e => {
        state.showCompass = e.target.checked;
        if (state.compassGridGroup) state.compassGridGroup.visible = state.showCompass;
      });
    }

    const cbParticles = document.getElementById('cb-particles');
    if (cbParticles) {
      cbParticles.addEventListener('change', e => {
        state.showParticles = e.target.checked;
        if (state.particleSystem) state.particleSystem.visible = state.showParticles;
        if (state.ghostMesh) state.ghostMesh.visible = state.showParticles && state.showGhostTrails;
        updateColorbarVisibility(state);
      });
    }

    const cbGhost = document.getElementById('cb-ghost');
    if (cbGhost) {
      cbGhost.checked = !!state.showGhostTrails;
      cbGhost.addEventListener('change', e => {
        state.showGhostTrails = e.target.checked;
        if (state.ghostMesh) state.ghostMesh.visible = state.showParticles && state.showGhostTrails;
        if (!state.showGhostTrails && state.ghostMesh) {
          state.ghostTrails = [];
          state.ghostMesh.visible = false;
        }
      });
    }

    // Screenshot
    const btnScreenshot = document.getElementById('btn-screenshot-panel');
    if (btnScreenshot) {
      btnScreenshot.addEventListener('click', () => {
        renderer.render(scene, camera);
        const a = document.createElement('a');
        a.download = `wind_tulungagung_${new Date().toISOString().slice(0, 10)}.png`;
        a.href = canvas.toDataURL('image/png');
        a.click();
      });
    }
  }

  return {
    updateUI,
    updateColorbarVisibility,
    setupEventListeners
  };
})();
