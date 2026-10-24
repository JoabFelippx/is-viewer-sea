const page = document.body;
const overview = page.dataset.overview === "true";
const selectedId = page.dataset.camera ? Number(page.dataset.camera) : null;
const cameraIds = [1, 2, 3, 4, 6, 7, 8];
const colors = new Map([
  [1, "#087da1"],
  [2, "#438b5c"],
  [3, "#7457a6"],
  [4, "#c28a21"],
  [6, "#cf6335"],
  [7, "#b04a64"],
  [8, "#586b7c"],
]);
const table = document.querySelector("#camera-table");
const map = document.querySelector("#calibration-map");
const toggle = document.querySelector("#include-map");
const selector = document.querySelector("#camera-picker");
const details = document.querySelector("#selected-calibration");
let scene;

function format(value) {
  return Number(value).toFixed(3);
}
function vector(values) {
  return values.map(format).join(" / ");
}
function addCell(row, text, className = "") {
  const cell = document.createElement("td");
  cell.textContent = text;
  if (className) cell.className = className;
  row.append(cell);
}
function linkToCamera(id, label = `Câmera ${id}`) {
  const link = document.createElement("a");
  link.className = "camera-link";
  link.href = `/calib/${id}`;
  link.style.setProperty("--camera-color", colors.get(id));
  const swatch = document.createElement("i");
  swatch.className = "camera-swatch";
  const text = document.createElement("span");
  text.textContent = label;
  link.append(swatch, text);
  return link;
}
function visibleCameras() {
  return scene.cameras.filter((camera) => toggle.checked || !camera.map_only);
}

function renderTable() {
  const cameras = visibleCameras();
  table.replaceChildren();
  for (const camera of cameras) {
    const row = document.createElement("tr");
    row.classList.toggle("selected", camera.id === selectedId);
    const name = document.createElement("td");
    name.append(linkToCamera(camera.id));
    row.append(name);
    addCell(row, vector(camera.position));
    addCell(row, vector(camera.forward));
    const [x, y, width, height] = camera.intrinsics.roi_xywh;
    addCell(row, `${width} × ${height} a partir de ${x}, ${y}`);
    addCell(row, `${camera.world_to_camera.length} × 4`, "matrix-label");
    row.addEventListener("click", (event) => {
      if (event.target.closest("a")) return;
      window.location.assign(`/calib/${camera.id}`);
    });
    table.append(row);
  }
  document.querySelector("#scene-summary").textContent =
    `${cameras.length} câmeras · posições em metros · direção óptica em XYZ`;
}

function matrixText(matrix) {
  return matrix
    .map((row) =>
      row.map((value) => Number(value).toFixed(6).padStart(11)).join("  "),
    )
    .join("\n");
}
function showDetails(camera) {
  details.hidden = false;
  document.querySelector("#detail-title").textContent = `Câmera ${camera.id}`;
  document.querySelector("#source-file").textContent = camera.source;
  document.querySelector("#world-to-camera").textContent = matrixText(
    camera.world_to_camera,
  );
  document.querySelector("#camera-to-world").textContent = matrixText(
    camera.camera_to_world,
  );
  document.querySelector("#raw-intrinsics").textContent = matrixText(
    camera.intrinsics.raw,
  );
  document.querySelector("#undistorted-intrinsics").textContent = matrixText(
    camera.intrinsics.undistorted,
  );
  document.querySelector("#distortion").textContent = matrixText([
    camera.intrinsics.distortion,
  ]);
  document.querySelector("#roi").textContent = matrixText([
    camera.intrinsics.roi_xywh,
  ]);
  const imageSize = camera.intrinsics.image_size;
  const roiSize = camera.intrinsics.roi_size;
  const text = [];
  if (imageSize)
    text.push(`Imagem original: ${imageSize.width} × ${imageSize.height} px`);
  if (roiSize)
    text.push(
      `Dimensão registrada do ROI: ${roiSize.width} × ${roiSize.height} px`,
    );
  document.querySelector("#image-size").textContent =
    `${text.join(" · ")} · SHA-256: ${camera.sha256}`;
}

function drawMap() {
  const cameras = visibleCameras();
  const points = cameras.map((camera) => camera.position);
  for (const polygon of toggle.checked ? scene.map.polygons : [])
    points.push(...polygon);
  const minX = Math.min(...points.map((point) => point[0]));
  const maxX = Math.max(...points.map((point) => point[0]));
  const minY = Math.min(...points.map((point) => point[1]));
  const maxY = Math.max(...points.map((point) => point[1]));
  const paddingX = Math.max((maxX - minX) * 0.1, 1.5);
  const paddingY = Math.max((maxY - minY) * 0.14, 1.5);
  const left = minX - paddingX,
    right = maxX + paddingX;
  const bottom = minY - paddingY,
    top = maxY + paddingY;
  const width = right - left,
    height = top - bottom;
  const svgWidth = 1000,
    svgHeight = 520,
    pad = 45;
  const scale = Math.min(
    (svgWidth - 2 * pad) / width,
    (svgHeight - 2 * pad) / height,
  );
  const xAt = (x) =>
    pad + (x - left) * scale + (svgWidth - 2 * pad - width * scale) / 2;
  const yAt = (y) =>
    svgHeight -
    pad -
    (y - bottom) * scale -
    (svgHeight - 2 * pad - height * scale) / 2;
  const element = (name, attrs = {}) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attrs))
      node.setAttribute(key, value);
    return node;
  };
  map.replaceChildren();

  const step = Math.pow(
    10,
    Math.floor(Math.log10(Math.max(width, height) / 6)),
  );
  for (let x = Math.ceil(left / step) * step; x <= right; x += step) {
    map.append(
      element("line", {
        x1: xAt(x),
        y1: pad,
        x2: xAt(x),
        y2: svgHeight - pad,
        class: "map-grid-line",
      }),
    );
    const label = element("text", {
      x: xAt(x),
      y: svgHeight - 15,
      class: "map-tick",
      "text-anchor": "middle",
    });
    label.textContent = `${x.toFixed(0)} m`;
    map.append(label);
  }
  for (let y = Math.ceil(bottom / step) * step; y <= top; y += step) {
    map.append(
      element("line", {
        x1: pad,
        y1: yAt(y),
        x2: svgWidth - pad,
        y2: yAt(y),
        class: "map-grid-line",
      }),
    );
    const label = element("text", { x: 12, y: yAt(y) + 4, class: "map-tick" });
    label.textContent = `${y.toFixed(0)} m`;
    map.append(label);
  }
  map.append(
    element("line", {
      x1: pad,
      y1: yAt(0),
      x2: svgWidth - pad,
      y2: yAt(0),
      class: "map-axis",
    }),
  );
  map.append(
    element("line", {
      x1: xAt(0),
      y1: pad,
      x2: xAt(0),
      y2: svgHeight - pad,
      class: "map-axis",
    }),
  );
  if (toggle.checked) {
    for (const polygon of scene.map.polygons) {
      map.append(
        element("polygon", {
          points: polygon
            .map((point) => `${xAt(point[0])},${yAt(point[1])}`)
            .join(" "),
          class: "map-polygon",
        }),
      );
    }
  }
  for (const camera of cameras) {
    const x = xAt(camera.position[0]),
      y = yAt(camera.position[1]);
    const group = element("g", {
      class: "map-camera",
      tabindex: "0",
      role: "link",
      "aria-label": `Abrir calibração da câmera ${camera.id}`,
    });
    const color = colors.get(camera.id);
    const endX = xAt(
      camera.position[0] + camera.forward[0] * Math.max(width, height) * 0.07,
    );
    const endY = yAt(
      camera.position[1] + camera.forward[1] * Math.max(width, height) * 0.07,
    );
    group.append(
      element("line", {
        x1: x,
        y1: y,
        x2: endX,
        y2: endY,
        stroke: color,
        class: "map-direction",
      }),
    );
    group.append(element("circle", { cx: x, cy: y, r: 8, fill: color }));
    const label = element("text", { x: x + 11, y: y - 9, fill: color });
    label.textContent = `C${camera.id}`;
    group.append(label);
    group.addEventListener("click", () => {
      window.location.assign(`/calib/${camera.id}`);
    });
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ")
        window.location.assign(`/calib/${camera.id}`);
    });
    if (camera.id === selectedId) group.classList.add("selected");
    map.append(group);
  }
}

async function initialize() {
  const response = await fetch("/static/world3d-scene.json");
  if (!response.ok) throw Error(`HTTP ${response.status}`);
  scene = await response.json();
  toggle.checked = Boolean(selectedId && selectedId >= 6);
  for (const camera of scene.cameras) {
    const option = document.createElement("option");
    option.value = camera.id;
    option.textContent = `Câmera ${camera.id}`;
    selector.append(option);
  }
  if (selectedId) selector.value = String(selectedId);
  selector.addEventListener("change", () => {
    window.location.assign(
      selector.value ? `/calib/${selector.value}` : "/calib",
    );
  });
  toggle.addEventListener("change", () => {
    renderTable();
    drawMap();
  });
  renderTable();
  drawMap();
  const selected = scene.cameras.find((camera) => camera.id === selectedId);
  if (selected) showDetails(selected);
}

initialize().catch((error) => {
  document.querySelector("#calibration-error").textContent =
    `Erro ao carregar calibrações: ${error.message}`;
  document.querySelector("#scene-summary").textContent =
    "Falha ao carregar dados.";
});
