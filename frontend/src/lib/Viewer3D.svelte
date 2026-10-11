<script lang="ts">
  import { onMount } from "svelte";
  import * as THREE from "three";
  import { OrbitControls } from "three/addons/controls/OrbitControls.js";
  import { api } from "./api";
  import Icon from "./Icon.svelte";
  import { app } from "./store.svelte";
  import { t } from "./i18n.svelte";

  const SKIN_COLOR = 0xb9c3d6;
  const EDGE_COLOR = 0x39414f;
  const HIGHLIGHT_COLOR = 0xff7a1a;
  const ISO = new THREE.Vector3(1, -1.25, 0.9).normalize();

  let host: HTMLDivElement;
  let renderer: THREE.WebGLRenderer;
  let camera: THREE.PerspectiveCamera;
  let controls: OrbitControls;
  const scene = new THREE.Scene();
  const gizmoScene = new THREE.Scene();
  const gizmoCamera = new THREE.OrthographicCamera(-1.6, 1.6, 1.6, -1.6, 0.1, 10);

  let positions: THREE.BufferAttribute | null = null;
  let skinMesh: THREE.Mesh | null = null;
  let edgeLines: THREE.LineSegments | null = null;
  let highlightObj: THREE.Object3D | null = null;
  let center = new THREE.Vector3();
  let radius = 1;
  let ready = $state(false);
  let loadedVersion = "";
  let frame = 0;

  const skinMaterial = new THREE.MeshStandardMaterial({
    color: SKIN_COLOR,
    flatShading: true,
    side: THREE.DoubleSide,
    roughness: 0.75,
    metalness: 0.05,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  });
  const edgeMaterial = new THREE.LineBasicMaterial({ color: EDGE_COLOR, transparent: true, opacity: 0.35 });

  function requestRender() {
    if (frame || !renderer) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      render();
    });
  }

  function render() {
    const size = renderer.getSize(new THREE.Vector2());
    renderer.setScissorTest(false);
    renderer.setViewport(0, 0, size.x, size.y);
    renderer.clear();
    renderer.render(scene, camera);

    // Trièdre dans le coin inférieur gauche, orienté comme la caméra.
    const g = 90;
    const dir = camera.position.clone().sub(controls.target).normalize();
    gizmoCamera.position.copy(dir.multiplyScalar(4));
    gizmoCamera.up.copy(camera.up);
    gizmoCamera.lookAt(0, 0, 0);
    renderer.setScissorTest(true);
    renderer.setScissor(6, 6, g, g);
    renderer.setViewport(6, 6, g, g);
    renderer.clearDepth();
    renderer.render(gizmoScene, gizmoCamera);
  }

  function buildGizmo() {
    const axes: [THREE.Vector3, number, string][] = [
      [new THREE.Vector3(1, 0, 0), 0xe5484d, "X"],
      [new THREE.Vector3(0, 1, 0), 0x30a46c, "Y"],
      [new THREE.Vector3(0, 0, 1), 0x3e7bfa, "Z"],
    ];
    for (const [dir, color, label] of axes) {
      gizmoScene.add(new THREE.ArrowHelper(dir, new THREE.Vector3(), 1, color, 0.28, 0.16));
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 64;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = `#${color.toString(16).padStart(6, "0")}`;
      ctx.font = "bold 44px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, 32, 34);
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false }),
      );
      sprite.position.copy(dir.clone().multiplyScalar(1.35));
      sprite.scale.setScalar(0.5);
      gizmoScene.add(sprite);
    }
  }

  export function frameView(direction: THREE.Vector3 = ISO) {
    if (!camera) return;
    const dist = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.05;
    camera.up.set(0, 0, 1);
    if (Math.abs(direction.z) > 0.99) camera.up.set(0, 1, 0);
    camera.position.copy(center).addScaledVector(direction, dist);
    camera.near = dist / 100;
    camera.far = dist * 100;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
    requestRender();
  }

  function disposeObject(obj: THREE.Object3D | null) {
    if (!obj) return;
    scene.remove(obj);
    const o = obj as THREE.Mesh;
    o.geometry?.dispose();
    const m = o.material as THREE.Material | undefined;
    if (m && m !== skinMaterial && m !== edgeMaterial) m.dispose();
  }

  function geometryWith(indices: Uint32Array): THREE.BufferGeometry {
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", positions!);
    geom.setIndex(new THREE.BufferAttribute(indices, 1));
    return geom;
  }

  async function loadMesh(version: string) {
    loadedVersion = version;
    const [pos, skin, edges] = await Promise.all([api.meshPositions(), api.meshSkin(), api.meshEdges()]);
    if (loadedVersion !== version) return;
    disposeObject(skinMesh);
    disposeObject(edgeLines);
    disposeObject(highlightObj);
    highlightObj = null;
    positions = new THREE.BufferAttribute(pos, 3);
    skinMesh = new THREE.Mesh(geometryWith(skin), skinMaterial);
    edgeLines = new THREE.LineSegments(geometryWith(edges), edgeMaterial);
    edgeLines.visible = app.showEdges;
    scene.add(skinMesh, edgeLines);

    const [lo, hi] = app.mesh!.bbox;
    const box = new THREE.Box3(new THREE.Vector3(...lo), new THREE.Vector3(...hi));
    center = box.getCenter(new THREE.Vector3());
    radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 1e-9);
    ready = true;
    frameView();
    showHighlight(app.highlight);
  }

  let highlightToken = 0;
  async function showHighlight(target: { entity: string; name: string } | null) {
    const token = ++highlightToken;
    disposeObject(highlightObj);
    highlightObj = null;
    skinMaterial.transparent = false;
    skinMaterial.opacity = 1;
    skinMaterial.depthWrite = true;
    if (!target || !positions) {
      skinMaterial.needsUpdate = true;
      requestRender();
      return;
    }
    let geo;
    try {
      geo = await api.meshGroup(target.entity, target.name);
    } catch (e) {
      app.error(e);
      return;
    }
    if (token !== highlightToken) return;
    const geom = geometryWith(geo.indices);
    if (geo.primitive === "triangles") {
      highlightObj = new THREE.Mesh(
        geom,
        new THREE.MeshStandardMaterial({
          color: HIGHLIGHT_COLOR,
          flatShading: true,
          side: THREE.DoubleSide,
          emissive: HIGHLIGHT_COLOR,
          emissiveIntensity: 0.25,
          polygonOffset: true,
          polygonOffsetFactor: -2,
          polygonOffsetUnits: -2,
        }),
      );
    } else if (geo.primitive === "lines") {
      highlightObj = new THREE.LineSegments(
        geom,
        new THREE.LineBasicMaterial({ color: HIGHLIGHT_COLOR, depthTest: false }),
      );
    } else {
      highlightObj = new THREE.Points(
        geom,
        new THREE.PointsMaterial({ color: HIGHLIGHT_COLOR, size: 7, sizeAttenuation: false, depthTest: false }),
      );
    }
    highlightObj.renderOrder = 10;
    // Peau translucide : le groupe reste visible même à l'intérieur du volume.
    skinMaterial.transparent = true;
    skinMaterial.opacity = 0.22;
    skinMaterial.depthWrite = false;
    skinMaterial.needsUpdate = true;
    scene.add(highlightObj);
    requestRender();
  }

  onMount(() => {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0x000000, 0);
    renderer.autoClear = false;
    host.appendChild(renderer.domElement);

    camera = new THREE.PerspectiveCamera(35, 1, 0.01, 1000);
    camera.up.set(0, 0, 1);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false; // centre de rotation fixe en v1
    controls.addEventListener("change", requestRender);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x5a6070, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(0.4, 0.6, 1);
    camera.add(key);
    scene.add(camera);
    buildGizmo();

    const observer = new ResizeObserver(() => {
      const { clientWidth: w, clientHeight: h } = host;
      if (!w || !h) return;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      requestRender();
    });
    observer.observe(host);

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      controls.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  });

  $effect(() => {
    const version = app.mesh?.version;
    if (!version) {
      disposeObject(skinMesh);
      disposeObject(edgeLines);
      disposeObject(highlightObj);
      skinMesh = edgeLines = highlightObj = null;
      positions = null;
      loadedVersion = "";
      ready = false;
      requestRender();
    } else if (version !== loadedVersion) {
      loadMesh(version).catch((e) => app.error(e));
    }
  });

  $effect(() => {
    const target = app.highlight;
    if (ready) showHighlight(target ? { ...target } : null);
  });

  $effect(() => {
    const visible = app.showEdges;
    if (edgeLines) {
      edgeLines.visible = visible;
      requestRender();
    }
  });
</script>

<div class="viewer">
  <div class="canvas" bind:this={host}></div>
  {#if ready}
    <div class="tools">
      <button class="ghost" title={t("Recadrer (vue isométrique)")} onclick={() => frameView()}><Icon name="cube" size={15} />{t("Recadrer")}</button>
      <button class="ghost" title={t("Vue suivant X")} onclick={() => frameView(new THREE.Vector3(1, 0, 0))}>X</button>
      <button class="ghost" title={t("Vue suivant Y")} onclick={() => frameView(new THREE.Vector3(0, -1, 0))}>Y</button>
      <button class="ghost" title={t("Vue suivant Z")} onclick={() => frameView(new THREE.Vector3(0, 0, 1))}>Z</button>
      <label class="edges" title={t("Afficher les arêtes du maillage")}>
        <input type="checkbox" bind:checked={app.showEdges} />{t("Arêtes")}
      </label>
    </div>
  {/if}
</div>

<style>
  .viewer {
    position: relative;
    flex: 1;
    min-width: 0;
    min-height: 0;
  }
  .canvas {
    position: absolute;
    inset: 0;
  }
  .canvas :global(canvas) {
    display: block;
  }
  .tools {
    position: absolute;
    top: 8px;
    left: 8px;
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 3px;
    background: color-mix(in srgb, var(--panel) 85%, transparent);
    border: 1px solid var(--border);
    border-radius: 8px;
    backdrop-filter: blur(4px);
  }
  .tools button {
    padding: 3px 8px;
    font-size: 12px;
  }
  .edges {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 0 8px;
    font-size: 12px;
    cursor: pointer;
  }
</style>
