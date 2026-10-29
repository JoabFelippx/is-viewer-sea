import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import "/static/skeleton-links.js";

const view = document.querySelector("#scene-view");
const labels = document.querySelector("#camera-labels");
const modelStatus = document.querySelector("#model-status");
const worldStatus = document.querySelector("#world-status");
const annotations = new window.AnnotationState();
const options = {
  lab: document.querySelector("#show-lab"),
  walls: document.querySelector("#show-walls"),
  chairs: document.querySelector("#show-chairs"),
  axes: document.querySelector("#show-axes"),
  cameras: document.querySelector("#show-cameras"),
  map: document.querySelector("#show-map"),
  extraCameras: document.querySelector("#show-extra-cameras"),
  people: document.querySelector("#show-people"),
};

const scene = new THREE.Scene();
scene.background = new THREE.Color("#e7ecf1");
const camera = new THREE.PerspectiveCamera(55, 1, 0.05, 1000);
camera.up.set(0, 0, 1);
camera.position.set(14, -16, 11);

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  view.prepend(renderer.domElement);
} catch (error) {
  modelStatus.textContent = `WebGL indisponível: ${error.message}`;
  throw error;
}

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 1);
controls.mouseButtons = {
  LEFT: THREE.MOUSE.ROTATE,
  MIDDLE: THREE.MOUSE.PAN,
  RIGHT: THREE.MOUSE.PAN,
};
controls.enableDamping = true;
controls.minDistance = 0.8;
controls.maxDistance = 500;
controls.update();
renderer.domElement.addEventListener("auxclick", (event) => {
  if (event.button === 1) event.preventDefault();
});

scene.add(new THREE.HemisphereLight("#ffffff", "#9ca3af", 2.4));
const sunlight = new THREE.DirectionalLight("#ffffff", 2.2);
sunlight.position.set(7, -6, 12);
scene.add(sunlight);

const laboratory = new THREE.Group();
const mapGroup = new THREE.Group();
const cameraGroup = new THREE.Group();
const extraCameraGroup = new THREE.Group();
const axesGroup = new THREE.Group();
const peopleGroup = new THREE.Group();
scene.add(laboratory, mapGroup, cameraGroup, extraCameraGroup, axesGroup, peopleGroup);

const axes = new THREE.AxesHelper(2);
const grid = new THREE.GridHelper(10, 10, "#9ba7b5", "#ced6de");
grid.rotation.x = Math.PI / 2;
grid.position.z = -0.01;
axesGroup.add(axes, grid);

const pointGeometry = new THREE.BufferGeometry();
const lineGeometry = new THREE.BufferGeometry();
const peoplePoints = new THREE.Points(
  pointGeometry,
  new THREE.PointsMaterial({ color: "#0891b2", size: 7, sizeAttenuation: false }),
);
const peopleLines = new THREE.LineSegments(
  lineGeometry,
  new THREE.LineBasicMaterial({ color: "#7c3aed", linewidth: 2 }),
);
peopleGroup.add(peopleLines, peoplePoints);

let labObject;
let wallParts = [];
let chairs = [];
const cameraLabels = [];
const markerGeometry = new THREE.SphereGeometry(0.09, 12, 8);

function applyVisibility() {
  laboratory.visible = options.lab.checked;
  for (const part of wallParts) part.visible = options.walls.checked;
  for (const chair of chairs) chair.visible = options.chairs.checked;
  axesGroup.visible = options.axes.checked;
  cameraGroup.visible = options.cameras.checked;
  extraCameraGroup.visible = options.extraCameras.checked;
  mapGroup.visible = options.map.checked;
  peopleGroup.visible = options.people.checked;
}

for (const input of Object.values(options)) input.addEventListener("change", applyVisibility);

function addCameraMarker(data) {
  const extra = data.map_only;
  const group = extra ? extraCameraGroup : cameraGroup;
  const color = extra ? "#c2410c" : "#0369a1";
  const center = new THREE.Vector3(...data.position);
  const tip = center.clone().addScaledVector(new THREE.Vector3(...data.forward), 0.75);
  const marker = new THREE.Mesh(
    markerGeometry,
    new THREE.MeshBasicMaterial({ color, depthTest: false }),
  );
  marker.position.copy(center);
  marker.renderOrder = 4;
  const direction = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([center, tip]),
    new THREE.LineBasicMaterial({ color, depthTest: false }),
  );
  direction.renderOrder = 4;
  group.add(marker, direction);

  const label = document.createElement("a");
  label.href = `/calib/${data.id}`;
  label.className = `camera-label${extra ? " extra" : ""}`;
  label.textContent = `C${data.id}`;
  label.title = `Abrir calibração da câmera ${data.id}`;
  labels.append(label);
  cameraLabels.push({ label, position: center.clone().add(new THREE.Vector3(0, 0, 0.2)), extra });
}

function addMap(polygons) {
  const material = new THREE.LineBasicMaterial({ color: "#536b80" });
  for (const polygon of polygons) {
    const positions = polygon.map(([x, y, z]) => new THREE.Vector3(x, y, z + 0.025));
    const line = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(positions),
      material,
    );
    mapGroup.add(line);
  }
}

function fitScene() {
  const bounds = new THREE.Box3();
  if (laboratory.visible && labObject) bounds.expandByObject(labObject);
  if (cameraGroup.visible) bounds.expandByObject(cameraGroup);
  if (extraCameraGroup.visible) bounds.expandByObject(extraCameraGroup);
  if (mapGroup.visible) bounds.expandByObject(mapGroup);
  if (bounds.isEmpty()) {
    bounds.expandByPoint(new THREE.Vector3(-5, -5, 0));
    bounds.expandByPoint(new THREE.Vector3(5, 5, 3));
  }
  const center = bounds.getCenter(new THREE.Vector3());
  const radius = Math.max(bounds.getSize(new THREE.Vector3()).length() / 2, 3);
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(radius * 1.5, -radius * 1.7, radius));
  camera.near = Math.max(radius / 1000, 0.01);
  camera.far = Math.max(radius * 30, 100);
  camera.updateProjectionMatrix();
  controls.update();
}
document.querySelector("#fit-scene").addEventListener("click", fitScene);

function updateLabels() {
  const width = view.clientWidth;
  const height = view.clientHeight;
  for (const item of cameraLabels) {
    const visible = item.extra ? extraCameraGroup.visible : cameraGroup.visible;
    if (!visible) {
      item.label.hidden = true;
      continue;
    }
    const point = item.position.clone().project(camera);
    item.label.hidden = point.z < -1 || point.z > 1 || Math.abs(point.x) > 1 || Math.abs(point.y) > 1;
    if (!item.label.hidden) {
      item.label.style.left = `${((point.x + 1) / 2) * width}px`;
      item.label.style.top = `${((1 - point.y) / 2) * height}px`;
    }
  }
}

function resize() {
  const width = view.clientWidth;
  const height = view.clientHeight;
  renderer.setSize(width, height);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
resize();
applyVisibility();
renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
  updateLabels();
});

async function loadScene() {
  const response = await fetch("/static/world3d-scene.json");
  if (!response.ok) throw Error(`Calibrações indisponíveis: HTTP ${response.status}`);
  const data = await response.json();
  for (const item of data.cameras) addCameraMarker(item);
  addMap(data.map.polygons);
  applyVisibility();
  fitScene();

  const loader = new GLTFLoader();
  const gltf = await loader.loadAsync("/static/models/labsea.glb", (event) => {
    if (event.total) {
      modelStatus.textContent = `Carregando laboratório: ${Math.round((100 * event.loaded) / event.total)}%`;
    }
  });
  labObject = gltf.scene;
  // O GLB foi exportado Y-up: (x, y, z) → (x, -z, y) no mundo calibrado Z-up.
  labObject.rotation.x = Math.PI / 2;
  labObject.traverse((node) => {
    if (/^(Parede_|Tile_|Ceiling_)/.test(node.name)) wallParts.push(node);
    // Cada Chair_### é a raiz das peças daquela cadeira no GLB.
    if (/^Chair_\d{3}$/.test(node.name)) chairs.push(node);
  });
  laboratory.add(labObject);
  applyVisibility();
  fitScene();
  modelStatus.textContent = "Laboratório carregado · metros · Z para cima";
}

function replacePositions(object, positions) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  object.geometry.dispose();
  object.geometry = geometry;
}

function renderPeople(objects) {
  const points = [];
  const lines = [];
  for (const person of objects) {
    const keypoints = new Map();
    for (const item of person.keypoints || []) {
      const position = item.position || {};
      const xyz = [position.x ?? 0, position.y ?? 0, position.z ?? 0].map(Number);
      if (!xyz.every(Number.isFinite)) continue;
      points.push(...xyz);
      keypoints.set(Number(item.id), xyz);
    }
    for (const [start, end] of window.IS_SKELETON_LINKS) {
      if (keypoints.has(start) && keypoints.has(end)) {
        lines.push(...keypoints.get(start), ...keypoints.get(end));
      }
    }
  }
  replacePositions(peoplePoints, points);
  replacePositions(peopleLines, lines);
}

function updatePeople(line) {
  const objects = annotations.update(JSON.parse(line));
  renderPeople(objects);
  worldStatus.textContent = `${objects.length} objeto(s) · leitura às ${new Date().toLocaleTimeString("pt-BR")}`;
}

setInterval(() => {
  const before = annotations.sources.size;
  const active = annotations.objects();
  if (annotations.sources.size !== before) {
    renderPeople(active);
    worldStatus.textContent = `${active.length} objeto(s) · fontes inativas removidas`;
  }
}, 250);

async function readAnnotations() {
  const response = await fetch(view.dataset.source);
  if (!response.ok) throw Error(`HTTP ${response.status}`);
  worldStatus.textContent = "Conectado · aguardando anotações…";
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const part = await reader.read();
    if (part.done) break;
    buffer += decoder.decode(part.value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        updatePeople(line);
      } catch (error) {
        worldStatus.textContent = `Anotação inválida: ${error.message}`;
      }
    }
  }
  worldStatus.textContent = "Fluxo encerrado. Abra o tópico novamente para reconectar.";
}

document.querySelector("#topic-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.querySelector("#world-topic");
  const topic = input.value.trim();
  if (!topic || topic.includes("/") || topic.length > 255 || /[#*]/.test(topic)) {
    input.setCustomValidity("Informe um tópico concreto, sem /, # ou *.");
    input.reportValidity();
    return;
  }
  location.assign(`/world3d-sintetico/${encodeURIComponent(topic)}`);
});
document.querySelector("#world-topic").addEventListener("input", (event) => {
  event.target.setCustomValidity("");
});

loadScene().catch((error) => {
  modelStatus.textContent = `Falha ao carregar o laboratório: ${error.message}`;
});
readAnnotations().catch((error) => {
  worldStatus.textContent = `Falha no fluxo 3D: ${error.message}`;
});
