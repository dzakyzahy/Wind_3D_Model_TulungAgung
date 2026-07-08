/* ─────────────────────────────────────────────────────────────────────────────
 * Wind Resource Assessment 3D — Tulungagung & Trenggalek, Jawa Timur
 * Module: 3D Scene Helpers, Meshes, GIS Overlay, Validation Plane & Scalebar
 * ───────────────────────────────────────────────────────────────────────────── */

window.WindSceneHelpers = (function() {
  function getTerrainH(col, row, state) {
    if (!state.windData || !state.windData.meta) return 0;
    const { nx, nz } = state.windData.meta;
    const { terrain } = state.windData;
    const c = Math.max(0, Math.min(nx - 1, Math.round(col)));
    const r = Math.max(0, Math.min(nz - 1, Math.round(row)));
    const h = Array.isArray(terrain[0]) ? (terrain[r]?.[c] || 0) : (terrain[r * nx + c] || 0);
    return Math.max(0, h) * state.elevScale * 6;
  }

  function getWind(col, row, state) {
    if (!state.windData || !state.windData.meta) return { u: 0, v: 0, ws: 0 };
    const { nx, nz } = state.windData.meta;
    const { wind_layers } = state.windData;
    const c = Math.max(0, Math.min(nx - 1, Math.round(col)));
    const r = Math.max(0, Math.min(nz - 1, Math.round(row)));
    const lyr = wind_layers[state.currentLayer];
    const getV = (arr, ri, ci) => Array.isArray(arr[ri]) ? arr[ri][ci] : arr[ri * nx + ci];
    return {
      u: getV(lyr.u, r, c) || 0,
      v: getV(lyr.v, r, c) || 0,
      ws: getV(lyr.wspd, r, c) || 0
    };
  }

  function buildTerrain(data, scene, THREE, state, renderer, camera) {
    if (state.terrainMesh) { scene.remove(state.terrainMesh); state.terrainMesh.geometry.dispose(); }
    if (state.wireMesh) { scene.remove(state.wireMesh); state.wireMesh.geometry.dispose(); }

    const TS = window.WindConfig.TS;
    const { nx, nz } = data.meta;
    const terrain = data.terrain;

    const geo = new THREE.PlaneGeometry(TS, TS, nx - 1, nz - 1);
    geo.rotateX(-Math.PI / 2);

    const pos = geo.attributes.position.array;
    const colors = new Float32Array(pos.length);
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const COLOR_STOPS = window.WindConfig.COLOR_STOPS;
    for (let idx = 0; idx < nx * nz; idx++) {
      const col = idx % nx;
      const row = Math.floor(idx / nx);
      const h = Array.isArray(terrain[0]) ? (terrain[row]?.[col] || 0) : (terrain[idx] || 0);
      pos[idx * 3 + 1] = h * state.elevScale * 6;
      const c = window.WindPhysics.lerpColor(h, COLOR_STOPS);
      colors[idx * 3] = c.r; colors[idx * 3 + 1] = c.g; colors[idx * 3 + 2] = c.b;
    }
    geo.computeVertexNormals();
    geo.attributes.position.needsUpdate = true;
    geo.attributes.color.needsUpdate = true;

    // UV Mapping Koreksi Presisi (Rotated Plane)
    const posAttr = geo.attributes.position;
    const uvAttr = geo.attributes.uv;
    const uvArr = uvAttr.array;

    for (let i = 0; i < posAttr.count; i++) {
      const vx = posAttr.getX(i);
      const vz = posAttr.getZ(i);
      const u = (vx / TS) + 0.5;
      const v = 1.0 - ((vz / TS) + 0.5);
      uvArr[i * 2] = u;
      uvArr[i * 2 + 1] = v;
    }
    uvAttr.needsUpdate = true;

    const loader = new THREE.TextureLoader();
    const texSrc1 = window.SATELLITE_TEXTURE_BASE64 || 'satellite_texture.jpg';
    const texSrc2 = window.SENTINEL2_TEXTURE_BASE64 || 'sentinel2_texture.jpg';

    state.satTexGoogle = loader.load(
      texSrc1,
      () => {
        if (renderer && scene && camera) renderer.render(scene, camera);
        if (state.useSatTexture && state.satType === 'google' && state.terrainMesh) {
          state.terrainMesh.material.map = state.satTexGoogle;
          state.terrainMesh.material.vertexColors = false;
          state.terrainMesh.material.color.set(0xffffff);
          state.terrainMesh.material.needsUpdate = true;
        }
        if (state.valPlaneMesh && state.satType === 'google') {
          state.valPlaneMesh.material.map = state.satTexGoogle;
          state.valPlaneMesh.material.needsUpdate = true;
        }
      },
      undefined,
      () => { console.warn('Tekstur Google Satelit tidak ditemukan'); }
    );
    if (state.satTexGoogle) {
      state.satTexGoogle.wrapS = THREE.ClampToEdgeWrapping;
      state.satTexGoogle.wrapT = THREE.ClampToEdgeWrapping;
      state.satTexGoogle.minFilter = THREE.LinearFilter;
    }

    state.satTexSentinel = loader.load(
      texSrc2,
      () => {
        if (renderer && scene && camera) renderer.render(scene, camera);
        if (state.useSatTexture && state.satType === 'sentinel2' && state.terrainMesh) {
          state.terrainMesh.material.map = state.satTexSentinel;
          state.terrainMesh.material.vertexColors = false;
          state.terrainMesh.material.color.set(0xffffff);
          state.terrainMesh.material.needsUpdate = true;
        }
        if (state.valPlaneMesh && state.satType === 'sentinel2') {
          state.valPlaneMesh.material.map = state.satTexSentinel;
          state.valPlaneMesh.material.needsUpdate = true;
        }
      },
      undefined,
      () => { console.warn('Tekstur Sentinel-2 tidak ditemukan'); }
    );
    if (state.satTexSentinel) {
      state.satTexSentinel.wrapS = THREE.ClampToEdgeWrapping;
      state.satTexSentinel.wrapT = THREE.ClampToEdgeWrapping;
      state.satTexSentinel.minFilter = THREE.LinearFilter;
    }

    const activeTex = state.satType === 'sentinel2' ? (state.satTexSentinel || state.satTexGoogle) : (state.satTexGoogle || state.satTexSentinel);

    const mat = new THREE.MeshPhongMaterial({
      vertexColors: !state.useSatTexture,
      map: state.useSatTexture ? activeTex : null,
      color: state.useSatTexture ? 0xffffff : 0xffffff,
      shininess: 4,
      side: THREE.FrontSide
    });
    state.terrainMesh = new THREE.Mesh(geo, mat);
    scene.add(state.terrainMesh);

    const wmat = new THREE.MeshBasicMaterial({ color: 0x0d1a2a, wireframe: true, transparent: true, opacity: 0.06 });
    state.wireMesh = new THREE.Mesh(geo.clone(), wmat);
    state.wireMesh.position.y = 0.008;
    scene.add(state.wireMesh);

    // Bidang Permukaan Laut (MSL 0.0m)
    if (state.waterMesh) { scene.remove(state.waterMesh); state.waterMesh.geometry.dispose(); }
    const waterGeo = new THREE.PlaneGeometry(TS, TS);
    waterGeo.rotateX(-Math.PI / 2);
    const waterMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7,
      transparent: true,
      opacity: 0.25,
      roughness: 0.10,
      metalness: 0.8,
      side: THREE.DoubleSide
    });
    state.waterMesh = new THREE.Mesh(waterGeo, waterMat);
    state.waterMesh.position.y = 0.02;
    state.waterMesh.visible = state.useWaterSurface;
    scene.add(state.waterMesh);
  }

  function buildValidationPlane(data, scene, THREE, state) {
    if (state.valPlaneMesh) { scene.remove(state.valPlaneMesh); state.valPlaneMesh.geometry.dispose(); }
    const TS = window.WindConfig.TS;
    const geo = new THREE.PlaneGeometry(TS, TS);
    geo.rotateX(-Math.PI / 2);

    const posAttr = geo.attributes.position;
    const uvAttr = geo.attributes.uv;
    const uvArr = uvAttr.array;
    for (let i = 0; i < posAttr.count; i++) {
      const vx = posAttr.getX(i);
      const vz = posAttr.getZ(i);
      const u = (vx / TS) + 0.5;
      const v = 1.0 - ((vz / TS) + 0.5);
      uvArr[i * 2] = u;
      uvArr[i * 2 + 1] = v;
    }
    uvAttr.needsUpdate = true;

    const activeTex = state.satType === 'sentinel2' ? (state.satTexSentinel || state.satTexGoogle) : (state.satTexGoogle || state.satTexSentinel);
    const mat = new THREE.MeshBasicMaterial({
      map: activeTex || null,
      color: activeTex ? 0xffffff : 0x22d3ee,
      wireframe: !activeTex,
      transparent: true,
      opacity: 0.68,
      side: THREE.DoubleSide,
      depthWrite: false
    });
    state.valPlaneMesh = new THREE.Mesh(geo, mat);

    const terrain = data.terrain;
    const max_h = Math.max(...(Array.isArray(terrain[0]) ? terrain.flat() : terrain));
    state.valPlaneMesh.position.y = max_h * state.elevScale * 6 + 0.35;
    state.valPlaneMesh.visible = state.showValPlane;
    scene.add(state.valPlaneMesh);
  }

  function updateValPlaneHeight(data, state) {
    if (!state.valPlaneMesh || !data) return;
    const terrain = data.terrain;
    const max_h = Math.max(...(Array.isArray(terrain[0]) ? terrain.flat() : terrain));
    state.valPlaneMesh.position.y = max_h * state.elevScale * 6 + 0.35;
  }

  function updateElevation(data, state, scene, THREE) {
    if (!state.terrainMesh) return;
    const { nx, nz } = data.meta;
    const terrain = data.terrain;
    const pos = state.terrainMesh.geometry.attributes.position;
    for (let idx = 0; idx < nx * nz; idx++) {
      const col = idx % nx, row = Math.floor(idx / nx);
      const h = Array.isArray(terrain[0]) ? (terrain[row]?.[col] || 0) : (terrain[idx] || 0);
      pos.array[idx * 3 + 1] = h * state.elevScale * 6;
    }
    pos.needsUpdate = true;
    state.terrainMesh.geometry.computeVertexNormals();
    state.wireMesh.geometry.attributes.position.array.set(pos.array);
    state.wireMesh.geometry.attributes.position.needsUpdate = true;
    buildRBIOverlay(data, scene, THREE, state);
    updateValPlaneHeight(data, state);
  }

  function buildRBIOverlay(data, scene, THREE, state) {
    ['roads', 'rivers', 'admin'].forEach(k => {
      if (state.rbiGroup[k]) {
        scene.remove(state.rbiGroup[k]);
        state.rbiGroup[k].children.forEach(c => c.geometry.dispose());
        state.rbiGroup[k] = null;
      }
    });
    if (!window.RBI_DATA || !data || !data.meta) return;

    const { nx, nz } = data.meta;
    const terrain = data.terrain;

    function createLines(linesArr, colorHex, yOffset) {
      if (!linesArr || !linesArr.length) return null;
      const group = new THREE.Group();
      const mat = new THREE.LineBasicMaterial({ color: colorHex, linewidth: 1.5 });

      linesArr.forEach(line => {
        if (!line || line.length < 2) return;
        const pts = [];
        line.forEach(pt => {
          const lon = pt[0], lat = pt[1];
          const x = (lon - 111.8) * 10;
          const z = (-8.29 - lat) * 10;
          const col = ((lon - 110.8) / 2.0) * (nx - 1);
          const row = ((-7.29 - lat) / 2.0) * (nz - 1);
          const c = Math.max(0, Math.min(nx - 1, Math.round(col)));
          const r = Math.max(0, Math.min(nz - 1, Math.round(row)));
          const hNorm = Array.isArray(terrain[0]) ? (terrain[r]?.[c] || 0) : (terrain[r * nx + c] || 0);
          const y = (Math.max(0, hNorm) * state.elevScale * 6) + yOffset;
          pts.push(new THREE.Vector3(x, y, z));
        });
        const geo = new THREE.BufferGeometry().setFromPoints(pts);
        group.add(new THREE.Line(geo, mat));
      });
      return group;
    }

    state.rbiGroup.roads = createLines(window.RBI_DATA.roads, 0xfbbf24, 0.08);
    state.rbiGroup.rivers = createLines(window.RBI_DATA.rivers, 0x38bdf8, 0.06);
    state.rbiGroup.admin = createLines(window.RBI_DATA.admin, 0xf8fafc, 0.10);

    if (state.rbiGroup.roads) { state.rbiGroup.roads.visible = state.useRBIRoads; scene.add(state.rbiGroup.roads); }
    if (state.rbiGroup.rivers) { state.rbiGroup.rivers.visible = state.useRBIRivers; scene.add(state.rbiGroup.rivers); }
    if (state.rbiGroup.admin) { state.rbiGroup.admin.visible = state.useRBIAdmin; scene.add(state.rbiGroup.admin); }
  }

  function buildWPDOverlay(data, scene, THREE, state) {
    if (state.wpdOverlay) { scene.remove(state.wpdOverlay); state.wpdOverlay.geometry.dispose(); }
    const TS = window.WindConfig.TS;
    const lyr = data.wind_layers[state.currentLayer];
    const { nx, nz } = data.meta;
    const wpd_flat = Array.isArray(lyr?.wpd?.[0]) ?
      lyr.wpd.flat() : (lyr?.wpd || (lyr?.wspd ? (Array.isArray(lyr.wspd[0]) ? lyr.wspd.flat() : lyr.wspd).map(v => 0.5 * 1.225 * Math.pow(v || 0, 3)) : new Array(nx * nz).fill(100)));
    const wpd_max = Math.max(...wpd_flat.filter(v => isFinite(v))) || 1;
    const terrain = data.terrain;

    const geo = new THREE.PlaneGeometry(TS, TS, nx - 1, nz - 1);
    geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position.array;
    const colors = new Float32Array(pos.length);
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    function wpdColor(t) {
      if (t < 0.5) { const f = t / 0.5; return { r: 0.98 * f, g: 0.78 * f, b: 0.004 }; }
      else { const f = (t - 0.5) / 0.5; return { r: 0.98, g: 0.78 * (1 - f), b: 0 }; }
    }

    for (let idx = 0; idx < nx * nz; idx++) {
      const col = idx % nx, row = Math.floor(idx / nx);
      const h = Array.isArray(terrain[0]) ? (terrain[row]?.[col] || 0) : (terrain[idx] || 0);
      pos[idx * 3 + 1] = Math.max(0, h) * state.elevScale * 6 + 0.15;
      const w = wpd_flat[row * nx + col] || 0;
      const t = Math.min(1, w / (wpd_max || 1));
      const c = wpdColor(t);
      colors[idx * 3] = c.r; colors[idx * 3 + 1] = c.g; colors[idx * 3 + 2] = c.b;
    }
    geo.computeVertexNormals();
    const mat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.55, depthWrite: false });
    state.wpdOverlay = new THREE.Mesh(geo, mat);
    scene.add(state.wpdOverlay);
    state.wpdOverlay.visible = state.showWPD;

    const cbMaxWpd = document.getElementById('cb-max-wpd');
    if (cbMaxWpd) cbMaxWpd.textContent = Math.round(wpd_max);
  }

  function buildTurbines(data, wdata, scene, THREE, state) {
    if (state.turbineGroup) { scene.remove(state.turbineGroup); }
    state.turbineGroup = new THREE.Group();

    let positions = [];
    if (wdata && wdata.turbine_positions_m) {
      positions = wdata.turbine_positions_m;
    } else {
      for (let i = 0; i < 5; i++) for (let j = 0; j < 5; j++)
        positions.push([(i - 2) * 7 * 150, (j - 2) * 7 * 150]);
    }

    const { nx, nz } = data.meta;
    const terrain = data.terrain;
    const TS = window.WindConfig.TS;
    const WU_PER_KM = window.WindConfig.WU_PER_KM;

    positions.slice(0, 25).forEach(([mx, my]) => {
      const wx = (mx / 1000) * WU_PER_KM;
      const wz = (my / 1000) * WU_PER_KM;
      const col = Math.max(0, Math.min(nx - 1, Math.round((wx / TS + 0.5) * nx)));
      const row = Math.max(0, Math.min(nz - 1, Math.round((wz / TS + 0.5) * nz)));
      const h = Array.isArray(terrain[0]) ? (terrain[row]?.[col] || 0) : (terrain[row * nx + col] || 0);
      const ty = Math.max(0, h) * state.elevScale * 6;

      const tower = new THREE.Mesh(
        new THREE.CylinderGeometry(0.001, 0.0015, 0.009, 8),
        new THREE.MeshPhongMaterial({ color: 0xdce8f0, shininess: 40 })
      );
      tower.position.set(wx, ty + 0.0045, wz);
      state.turbineGroup.add(tower);

      const nacelle = new THREE.Mesh(
        new THREE.BoxGeometry(0.002, 0.0008, 0.001),
        new THREE.MeshPhongMaterial({ color: 0xf0f4f8 })
      );
      nacelle.position.set(wx, ty + 0.0095, wz);
      state.turbineGroup.add(nacelle);

      const rotor = new THREE.Group();
      rotor.position.set(wx, ty + 0.0095, wz);
      rotor.rotation.y = Math.PI / 2;
      rotor.userData.isRotor = true;

      const disc = new THREE.Mesh(
        new THREE.CircleGeometry(0.0068, 16),
        new THREE.MeshBasicMaterial({ color: 0xe0eaf5, transparent: true, opacity: 0.45, side: THREE.DoubleSide })
      );
      rotor.add(disc);

      for (let b = 0; b < 3; b++) {
        const bladeGroup = new THREE.Group();
        bladeGroup.rotation.z = (b * 120) * Math.PI / 180;
        const blade = new THREE.Mesh(
          new THREE.BoxGeometry(0.0008, 0.006, 0.0002),
          new THREE.MeshPhongMaterial({ color: 0xffffff })
        );
        blade.position.y = 0.003;
        bladeGroup.add(blade);
        rotor.add(bladeGroup);
      }
      state.turbineGroup.add(rotor);
    });

    scene.add(state.turbineGroup);
    state.turbineGroup.visible = state.showTurbine;
  }

  function buildWake(data, wdata, scene, THREE, state) {
    if (state.wakeGroup) scene.remove(state.wakeGroup);
    state.wakeGroup = new THREE.Group();

    let positions = [];
    if (wdata && wdata.turbine_positions_m) positions = wdata.turbine_positions_m;
    else for (let i = 0; i < 5; i++) for (let j = 0; j < 5; j++) positions.push([(i - 2) * 7 * 150, (j - 2) * 7 * 150]);

    const { nx, nz } = data.meta;
    const terrain = data.terrain;
    const TS = window.WindConfig.TS;
    const WU_PER_KM = window.WindConfig.WU_PER_KM;
    const coneLen = 0.4;

    positions.slice(0, 25).forEach(([mx, my]) => {
      const wx = (mx / 1000) * WU_PER_KM;
      const wz = (my / 1000) * WU_PER_KM;
      const col = Math.max(0, Math.min(nx - 1, Math.round((wx / TS + 0.5) * nx)));
      const row = Math.max(0, Math.min(nz - 1, Math.round((wz / TS + 0.5) * nz)));
      const h = Array.isArray(terrain[0]) ? (terrain[row]?.[col] || 0) : (terrain[row * nx + col] || 0);
      const ty = Math.max(0, h) * state.elevScale * 6 + 0.0095;

      const cone = new THREE.Mesh(
        new THREE.ConeGeometry(0.015, coneLen, 8),
        new THREE.MeshBasicMaterial({ color: 0xef4444, transparent: true, opacity: 0.18, depthWrite: false })
      );
      cone.rotation.z = Math.PI / 2;
      cone.position.set(wx + coneLen / 2, ty, wz);
      state.wakeGroup.add(cone);
    });

    scene.add(state.wakeGroup);
    state.wakeGroup.visible = state.showWake;
  }

  function buildExtremeZone(data, scene, THREE, state) {
    if (state.extremeGroup) scene.remove(state.extremeGroup);
    state.extremeGroup = new THREE.Group();

    const TS = window.WindConfig.TS;
    const { nx, nz } = data.meta;
    const terrain = data.terrain;
    const lyr = data.wind_layers[state.currentLayer];
    const wspd_flat = Array.isArray(lyr.wspd[0]) ? lyr.wspd.flat() : lyr.wspd;
    const wspd_max = Math.max(...wspd_flat.filter(v => isFinite(v)));
    const threshold = wspd_max * 0.80;

    const geo = new THREE.PlaneGeometry(TS, TS, nx - 1, nz - 1);
    geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position.array;
    const colors = new Float32Array(pos.length);
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    for (let idx = 0; idx < nx * nz; idx++) {
      const col = idx % nx, row = Math.floor(idx / nx);
      const h = Array.isArray(terrain[0]) ? (terrain[row]?.[col] || 0) : (terrain[idx] || 0);
      pos[idx * 3 + 1] = Math.max(0, h) * state.elevScale * 6 + 0.3;
      const ws = wspd_flat[row * nx + col] || 0;
      const isEx = ws >= threshold;
      colors[idx * 3] = isEx ? 0.68 : 0; colors[idx * 3 + 1] = isEx ? 0.33 : 0; colors[idx * 3 + 2] = isEx ? 0.98 : 0;
    }
    geo.computeVertexNormals();
    const mat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.35, depthWrite: false });
    const mesh = new THREE.Mesh(geo, mat);
    state.extremeGroup.add(mesh);
    scene.add(state.extremeGroup);
    state.extremeGroup.visible = state.showExtreme;

    const cbMinEx = document.getElementById('cb-min-extreme');
    const cbMaxEx = document.getElementById('cb-max-extreme');
    if (cbMinEx) cbMinEx.textContent = threshold.toFixed(1);
    if (cbMaxEx) cbMaxEx.textContent = wspd_max.toFixed(1);
  }

  function resetParticle(i, wsMax, state) {
    if (!state.windData || !state.windData.meta) return;
    const { nx, nz } = state.windData.meta;
    const TS = window.WindConfig.TS;
    const TRAIL_LEN = window.WindConfig.TRAIL_LEN;
    const col = Math.random() * nx;
    const row = Math.random() * nz;
    const wx = (col / nx - 0.5) * TS;
    const wz = (row / nz - 0.5) * TS;
    const ty = getTerrainH(col, row, state) + 0.2 + Math.random() * 0.8;

    for (let k = 0; k < TRAIL_LEN; k++) {
      state.pHistX[i * TRAIL_LEN + k] = wx;
      state.pHistY[i * TRAIL_LEN + k] = ty;
      state.pHistZ[i * TRAIL_LEN + k] = wz;
    }
    state.pAges[i] = 0; state.pLife[i] = 2 + Math.random() * 4;
  }

  function initParticles(n, scene, THREE, state) {
    if (state.particleSystem) { scene.remove(state.particleSystem); state.particleSystem.geometry.dispose(); }
    if (!state.windData) return;
    const lyr = state.windData.wind_layers[state.currentLayer];
    const wsArr = Array.isArray(lyr.wspd[0]) ? lyr.wspd.flat() : lyr.wspd;
    const wsMax = Math.max(...wsArr.filter(v => isFinite(v))) || 8;
    const TRAIL_LEN = window.WindConfig.TRAIL_LEN;

    state.pHistX = new Float32Array(n * TRAIL_LEN);
    state.pHistY = new Float32Array(n * TRAIL_LEN);
    state.pHistZ = new Float32Array(n * TRAIL_LEN);
    state.pAges = new Float32Array(n);
    state.pLife = new Float32Array(n);

    for (let i = 0; i < n; i++) {
      resetParticle(i, wsMax, state);
      state.pAges[i] = Math.random() * state.pLife[i];
    }

    const nSegs = TRAIL_LEN - 1;
    const totalVerts = n * nSegs * 2;
    const posArr = new Float32Array(totalVerts * 3);
    const colArr = new Float32Array(totalVerts * 3);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(posArr, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colArr, 3));

    const mat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    state.particleSystem = new THREE.LineSegments(geo, mat);
    scene.add(state.particleSystem);
    state.particleSystem.visible = state.showParticles;

    const dispN = document.getElementById('disp-nparticle');
    if (dispN) dispN.textContent = n;
  }

  function updateParticles(dt, state, THREE) {
    if (!state.particleSystem || !state.windData || !state.windData.meta || !state.showParticles) return;
    const { nx, nz } = state.windData.meta;
    const { wind_layers } = state.windData;
    const lyr = wind_layers[state.currentLayer];
    const wsArr = Array.isArray(lyr.wspd[0]) ? lyr.wspd.flat() : lyr.wspd;
    const wsMax = Math.max(...wsArr.filter(v => isFinite(v))) || 8;
    const n = state.pAges.length;
    const posArr = state.particleSystem.geometry.attributes.position.array;
    const colArr = state.particleSystem.geometry.attributes.color.array;
    const TRAIL_LEN = window.WindConfig.TRAIL_LEN;
    const nSegs = TRAIL_LEN - 1;
    const TS = window.WindConfig.TS;

    for (let i = 0; i < n; i++) {
      state.pAges[i] += dt * state.animSpeed;
      if (state.pAges[i] >= state.pLife[i]) { resetParticle(i, wsMax, state); continue; }

      const wx = state.pHistX[i * TRAIL_LEN], wy = state.pHistY[i * TRAIL_LEN], wz = state.pHistZ[i * TRAIL_LEN];
      const col_g = (wx / TS + 0.5) * nx;
      const row_g = (wz / TS + 0.5) * nz;
      const { u, v, ws } = getWind(col_g, row_g, state);

      const speed_scale = 0.18;
      const nx2 = (wx + u * state.animSpeed * dt * speed_scale);
      const nz2 = (wz - v * state.animSpeed * dt * speed_scale);

      if (nx2 < -TS / 2 || nx2 > TS / 2 || nz2 < -TS / 2 || nz2 > TS / 2) {
        resetParticle(i, wsMax, state); continue;
      }
      const nc = (nx2 / TS + 0.5) * nx;
      const nr = (nz2 / TS + 0.5) * nz;
      const th = getTerrainH(nc, nr, state);
      const hub_offset = [0.4, 0.8, 1.4][state.currentLayer];
      const tgt = th + hub_offset;
      const ny = wy + (tgt - wy) * 0.04;

      for (let k = TRAIL_LEN - 1; k > 0; k--) {
        state.pHistX[i * TRAIL_LEN + k] = state.pHistX[i * TRAIL_LEN + k - 1];
        state.pHistY[i * TRAIL_LEN + k] = state.pHistY[i * TRAIL_LEN + k - 1];
        state.pHistZ[i * TRAIL_LEN + k] = state.pHistZ[i * TRAIL_LEN + k - 1];
      }
      state.pHistX[i * TRAIL_LEN] = nx2;
      state.pHistY[i * TRAIL_LEN] = Math.max(th + 0.05, ny);
      state.pHistZ[i * TRAIL_LEN] = nz2;

      const c = window.WindPhysics.wsColor(ws, wsMax, THREE);
      const t = state.pAges[i] / state.pLife[i];
      const lifeAlpha = t < 0.1 ? t / 0.1 : t > 0.85 ? (1 - t) / 0.15 : 1.0;

      for (let s = 0; s < nSegs; s++) {
        const vIdx = (i * nSegs + s) * 2;
        posArr[vIdx * 3] = state.pHistX[i * TRAIL_LEN + s];
        posArr[vIdx * 3 + 1] = state.pHistY[i * TRAIL_LEN + s];
        posArr[vIdx * 3 + 2] = state.pHistZ[i * TRAIL_LEN + s];

        posArr[(vIdx + 1) * 3] = state.pHistX[i * TRAIL_LEN + s + 1];
        posArr[(vIdx + 1) * 3 + 1] = state.pHistY[i * TRAIL_LEN + s + 1];
        posArr[(vIdx + 1) * 3 + 2] = state.pHistZ[i * TRAIL_LEN + s + 1];

        const f0 = (1.0 - s / TRAIL_LEN) * lifeAlpha;
        const f1 = (1.0 - (s + 1) / TRAIL_LEN) * lifeAlpha;

        colArr[vIdx * 3] = c.r * f0;
        colArr[vIdx * 3 + 1] = c.g * f0;
        colArr[vIdx * 3 + 2] = c.b * f0;

        colArr[(vIdx + 1) * 3] = c.r * f1;
        colArr[(vIdx + 1) * 3 + 1] = c.g * f1;
        colArr[(vIdx + 1) * 3 + 2] = c.b * f1;
      }
    }
    state.particleSystem.geometry.attributes.position.needsUpdate = true;
    state.particleSystem.geometry.attributes.color.needsUpdate = true;
  }

  function initGhostMesh(scene, THREE, state) {
    if (state.ghostMesh) { scene.remove(state.ghostMesh); state.ghostMesh.geometry.dispose(); }
    const TRAIL_LEN = window.WindConfig.TRAIL_LEN;
    const MAX_GHOST = window.WindConfig.MAX_GHOST_TRAILS;
    const maxVerts = MAX_GHOST * TRAIL_LEN * 2;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(maxVerts * 3), 3));
    geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(maxVerts * 3), 3));
    const mat = new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, opacity: 1.0,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    state.ghostMesh = new THREE.LineSegments(geo, mat);
    scene.add(state.ghostMesh);
    state.ghostMesh.visible = state.showParticles;
  }

  function depositGhostTrails(state, THREE) {
    if (!state.windData || !state.windData.meta || !state.showParticles) return;
    const lyr = state.windData.wind_layers[state.currentLayer];
    const wsArr = Array.isArray(lyr.wspd[0]) ? lyr.wspd.flat() : lyr.wspd;
    const wsMax = Math.max(...wsArr.filter(v => isFinite(v))) || 8;
    const TRAIL_LEN = window.WindConfig.TRAIL_LEN;
    const TS = window.WindConfig.TS;

    const n = state.pAges.length;
    for (let i = 0; i < n; i++) {
      if (state.pAges[i] < 0.5 || state.pAges[i] > state.pLife[i] * 0.9) continue;

      const wx = state.pHistX[i * TRAIL_LEN];
      const wz = state.pHistZ[i * TRAIL_LEN];
      const col_g = (wx / TS + 0.5) * state.windData.meta.nx;
      const row_g = (wz / TS + 0.5) * state.windData.meta.nz;
      const { ws } = getWind(col_g, row_g, state);

      const points = [];
      for (let k = 0; k < TRAIL_LEN; k++) {
        points.push([
          state.pHistX[i * TRAIL_LEN + k],
          state.pHistY[i * TRAIL_LEN + k],
          state.pHistZ[i * TRAIL_LEN + k]
        ]);
      }

      state.ghostTrails.push({
        points,
        color: window.WindPhysics.wsColor(ws, wsMax, THREE).clone(),
        age: 0,
        maxAge: state.ghostMaxAge
      });
    }

    while (state.ghostTrails.length > window.WindConfig.MAX_GHOST_TRAILS) {
      state.ghostTrails.shift();
    }
  }

  function updateGhostMesh(dt, state) {
    if (!state.ghostMesh || state.ghostTrails.length === 0 || !state.showParticles) return;

    state.ghostTrails = state.ghostTrails.filter(g => {
      g.age += dt;
      return g.age < g.maxAge;
    });

    const posArr = state.ghostMesh.geometry.attributes.position.array;
    const colArr = state.ghostMesh.geometry.attributes.color.array;
    posArr.fill(0); colArr.fill(0);

    let vi = 0;
    const TRAIL_LEN = window.WindConfig.TRAIL_LEN;
    const nSegs = TRAIL_LEN - 1;

    for (const g of state.ghostTrails) {
      const fadeAlpha = Math.max(0, 1 - g.age / g.maxAge);
      const pts = g.points;

      for (let s = 0; s < nSegs && s < pts.length - 1; s++) {
        const segAlpha = fadeAlpha * (1 - s / TRAIL_LEN);

        posArr[vi * 3] = pts[s][0];
        posArr[vi * 3 + 1] = pts[s][1];
        posArr[vi * 3 + 2] = pts[s][2];
        colArr[vi * 3] = g.color.r * segAlpha;
        colArr[vi * 3 + 1] = g.color.g * segAlpha;
        colArr[vi * 3 + 2] = g.color.b * segAlpha;
        vi++;

        posArr[vi * 3] = pts[s + 1][0];
        posArr[vi * 3 + 1] = pts[s + 1][1];
        posArr[vi * 3 + 2] = pts[s + 1][2];
        colArr[vi * 3] = g.color.r * segAlpha * 0.6;
        colArr[vi * 3 + 1] = g.color.g * segAlpha * 0.6;
        colArr[vi * 3 + 2] = g.color.b * segAlpha * 0.6;
        vi++;
      }
    }

    state.ghostMesh.geometry.attributes.position.needsUpdate = true;
    state.ghostMesh.geometry.attributes.color.needsUpdate = true;
    state.ghostMesh.geometry.setDrawRange(0, vi);
  }

  function addLabelsAndCompass(scene, THREE, state) {
    if (state.labelGroup) scene.remove(state.labelGroup);
    if (state.compassGridGroup) scene.remove(state.compassGridGroup);

    state.labelGroup = new THREE.Group();
    state.compassGridGroup = new THREE.Group();

    const TS = window.WindConfig.TS;

    function addLabel(text, wx, wy, wz, col = '#7dd3fc') {
      const c = document.createElement('canvas');
      c.width = 300; c.height = 70;
      const ctx = c.getContext('2d');
      ctx.font = 'bold 24px Segoe UI,sans-serif';
      ctx.fillStyle = 'rgba(0,0,0,0)'; ctx.fillRect(0, 0, 300, 70);
      ctx.strokeStyle = 'rgba(10,14,26,.8)'; ctx.lineWidth = 5;
      ctx.strokeText(text, 8, 46);
      ctx.fillStyle = col; ctx.fillText(text, 8, 46);
      const tex = new THREE.CanvasTexture(c);
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
      sp.position.set(wx, wy, wz); sp.scale.set(3.5, 0.82, 1);
      state.labelGroup.add(sp);
    }

    window.WindConfig.LABELS.forEach(l => addLabel(l.text, l.x, l.y, l.z, l.color));

    // North Arrow
    const cv = document.createElement('canvas'); cv.width = 80; cv.height = 80;
    const ctx = cv.getContext('2d');
    ctx.fillStyle = 'rgba(0,0,0,0)'; ctx.fillRect(0, 0, 80, 80);
    ctx.fillStyle = '#ef4444';
    ctx.beginPath(); ctx.moveTo(40, 8); ctx.lineTo(50, 40); ctx.lineTo(40, 35);
    ctx.lineTo(30, 40); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#94a3b8';
    ctx.beginPath(); ctx.moveTo(40, 72); ctx.lineTo(50, 40); ctx.lineTo(40, 45);
    ctx.lineTo(30, 40); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.font = 'bold 14px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('N', 40, 20);
    const tex = new THREE.CanvasTexture(cv);
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
    sp.position.set(-TS / 2 + 1.5, 2, -TS / 2 + 1.5);
    sp.scale.set(1.2, 1.2, 1);
    state.compassGridGroup.add(sp);

    // Geo Grid Lines
    const mat = new THREE.LineBasicMaterial({ color: 0x334455, transparent: true, opacity: 0.35 });
    const LAT_LINES = 5, LON_LINES = 5;
    for (let i = 0; i <= LAT_LINES; i++) {
      const z = (i / LAT_LINES - 0.5) * TS;
      const points = [new THREE.Vector3(-TS / 2, 0.05, z), new THREE.Vector3(TS / 2, 0.05, z)];
      state.compassGridGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), mat));
    }
    for (let i = 0; i <= LON_LINES; i++) {
      const x = (i / LON_LINES - 0.5) * TS;
      const points = [new THREE.Vector3(x, 0.05, -TS / 2), new THREE.Vector3(x, 0.05, TS / 2)];
      state.compassGridGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), mat));
    }

    scene.add(state.labelGroup);
    scene.add(state.compassGridGroup);
    state.labelGroup.visible = state.showLabels;
    state.compassGridGroup.visible = state.showCompass;
  }

  // Dynamic Scalebar adapting to camera zoom
  function updateScaleBar(camera, controls) {
    if (!camera || !controls || !controls.target) return;
    const dist = camera.position.distanceTo(controls.target);
    const fovRad = (camera.fov * Math.PI) / 180;
    const hWorld = 2 * dist * Math.tan(fovRad / 2);
    const screenHeightPx = window.innerHeight || 800;
    const wuPerPx = hWorld / screenHeightPx;

    // 1 WU = 11.1 km
    const kmPerPx = wuPerPx * 11.1;
    const targetDistKm = 100 * kmPerPx;

    const increments = window.WindConfig.SCALE_INCREMENTS_KM;
    let chosenKm = increments[0];
    for (let i = 0; i < increments.length; i++) {
      if (targetDistKm <= increments[i] * 1.4) {
        chosenKm = increments[i];
        break;
      }
      chosenKm = increments[i];
    }

    const widthPx = Math.max(30, Math.min(240, Math.round(chosenKm / kmPerPx)));
    const inner = document.getElementById('scalebar-inner');
    const label = document.getElementById('scalebar-text');
    if (inner && label) {
      inner.style.width = widthPx + 'px';
      label.textContent = chosenKm >= 1 ? `${chosenKm} km` : `${chosenKm * 1000} m`;
    }
  }

  return {
    getTerrainH,
    getWind,
    buildTerrain,
    buildValidationPlane,
    updateValPlaneHeight,
    updateElevation,
    buildRBIOverlay,
    buildWPDOverlay,
    buildTurbines,
    buildWake,
    buildExtremeZone,
    initParticles,
    updateParticles,
    initGhostMesh,
    depositGhostTrails,
    updateGhostMesh,
    addLabelsAndCompass,
    updateScaleBar
  };
})();
