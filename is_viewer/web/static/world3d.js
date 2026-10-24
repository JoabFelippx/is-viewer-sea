const canvas = document.querySelector("canvas");
const context = canvas.getContext("2d");
const visibleAxes = { x: true, y: true, z: true };
let people = [];
let yaw = -0.8;
let elevation = 0.35;
let distance = 10;
const scene = new WorldScene();
const worldStatus = document.querySelector("#world-status");
const sceneStatus = document.querySelector("#scene-status");
let target = [0, 0, 0];
let dragMode = null;
let lastPointer = [0, 0];

// Pares de IDs de keypoints conectados pelo esqueleto IS.
const skeletonLinks = [
  [17, 15],
  [15, 13],
  [18, 16],
  [16, 14],
  [13, 14],
  [7, 13],
  [8, 14],
  [7, 8],
  [7, 9],
  [9, 11],
  [8, 10],
  [10, 12],
  [3, 4],
  [2, 3],
  [2, 4],
  [3, 5],
  [4, 6],
];

for (const input of document.querySelectorAll("[data-axis]")) {
  input.onchange = () => {
    visibleAxes[input.dataset.axis] = input.checked;
  };
}

function resize() {
  canvas.width = innerWidth * devicePixelRatio;
  canvas.height = innerHeight * devicePixelRatio;
  context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
}
addEventListener("resize", resize);
resize();

canvas.onpointerdown = (event) => {
  if (![0, 1].includes(event.button)) return;
  event.preventDefault();
  dragMode = event.button === 1 ? "pan" : "orbit";
  lastPointer = [event.clientX, event.clientY];
  canvas.setPointerCapture(event.pointerId);
};
canvas.onpointerup = canvas.onpointercancel = () => {
  dragMode = null;
};
canvas.onpointermove = (event) => {
  if (!dragMode) return;
  const deltaX = event.clientX - lastPointer[0];
  const deltaY = event.clientY - lastPointer[1];
  if (dragMode === "pan") {
    const view = cameraView();
    const metersPerPixel =
      (2 * distance * Math.tan(Math.PI / 6)) /
      Math.min(innerWidth, innerHeight);
    target = target.map(
      (value, axis) =>
        value +
        metersPerPixel * (-deltaX * view.right[axis] + deltaY * view.up[axis]),
    );
  } else {
    yaw -= deltaX * 0.006;
    elevation += deltaY * 0.006;
    elevation = Math.max(-1.45, Math.min(1.45, elevation));
  }
  lastPointer = [event.clientX, event.clientY];
};
canvas.onwheel = (event) => {
  event.preventDefault();
  distance *= Math.exp(event.deltaY * 0.001);
  distance = Math.max(2, Math.min(500, distance));
};

// Impede o autoscroll do navegador ao pressionar a roda do mouse.
canvas.onauxclick = (event) => {
  if (event.button === 1) event.preventDefault();
};
canvas.onlostpointercapture = () => {
  dragMode = null;
};

function fitScene() {
  const bounds = scene.bounds();
  target = bounds.min.map((value, axis) => (value + bounds.max[axis]) / 2);
  const radius = Math.hypot(...subtract(bounds.max, bounds.min)) / 2;
  distance = Math.max(10, radius * 2.3);
}
document.querySelector("#fit-scene").onclick = fitScene;
document.querySelector("#show-map").onchange = (event) => {
  scene.showMap = event.target.checked;
  fitScene();
};
document.querySelector("#topic-form").onsubmit = (event) => {
  event.preventDefault();
  const input = document.querySelector("#world-topic");
  const topic = input.value.trim();
  if (
    !topic ||
    topic.includes("/") ||
    topic.length > 255 ||
    /[#*]/.test(topic)
  ) {
    input.setCustomValidity(
      "Informe um tópico completo, por exemplo MeuServico.World3D.",
    );
    input.reportValidity();
    return;
  }
  window.location.assign("/world3d/" + encodeURIComponent(topic));
};
document.querySelector("#world-topic").oninput = (event) =>
  event.target.setCustomValidity("");
scene
  .load()
  .then(fitScene)
  .catch((error) => {
    sceneStatus.textContent = error.message;
  });

function dot(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
function subtract(a, b) {
  return a.map((value, index) => value - b[index]);
}
function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}
function normalize(vector) {
  const length = Math.hypot(...vector) || 1;
  return vector.map((value) => value / length);
}

function cameraView() {
  const position = [
    target[0] + distance * Math.cos(elevation) * Math.cos(yaw),
    target[1] + distance * Math.cos(elevation) * Math.sin(yaw),
    target[2] + distance * Math.sin(elevation),
  ];
  const forward = normalize(subtract(target, position));
  const right = normalize(cross(forward, [0, 0, 1]));
  const up = cross(right, forward);
  return { position, forward, right, up };
}

// Projeta metros no espaço 3D em pixels do canvas, com perspectiva.
function project(point, view) {
  const relative = subtract(point, view.position);
  const depth = dot(relative, view.forward);
  if (depth <= 0.05) return null;
  const focal = Math.min(innerWidth, innerHeight) / (2 * Math.tan(Math.PI / 6));
  return {
    x: innerWidth / 2 + (focal * dot(relative, view.right)) / depth,
    y: innerHeight / 2 - (focal * dot(relative, view.up)) / depth,
  };
}

function drawLine(start, end, color, width, view) {
  const from = project(start, view);
  const to = project(end, view);
  if (!from || !to) return;
  context.strokeStyle = color;
  context.lineWidth = width;
  context.beginPath();
  context.moveTo(from.x, from.y);
  context.lineTo(to.x, to.y);
  context.stroke();
}

function drawLabel(point, text, color, view, offsetX = 5, offsetY = -5) {
  const pixel = project(point, view);
  if (!pixel) return;
  context.fillStyle = color;
  context.font = "12px system-ui";
  context.fillText(text, pixel.x + offsetX, pixel.y + offsetY);
}

function drawGrid(view) {
  for (let meter = -5; meter <= 5; meter++) {
    drawLine([meter, -5, 0], [meter, 5, 0], "#d1d5db", 1, view);
    drawLine([-5, meter, 0], [5, meter, 0], "#d1d5db", 1, view);
    if (!meter) continue;
    if (visibleAxes.x)
      drawLabel([meter, 0, 0], meter.toFixed(1), "#991b1b", view);
    if (visibleAxes.y)
      drawLabel([0, meter, 0], meter.toFixed(1), "#166534", view);
  }
  if (visibleAxes.z) {
    for (let meter = 1; meter <= 3; meter++) {
      drawLine([-0.08, 0, meter], [0.08, 0, meter], "#2563eb", 1, view);
      drawLabel([0, 0, meter], meter.toFixed(1), "#1d4ed8", view, 7, 4);
    }
  }
  const axes = [
    ["x", [5.4, 0, 0], "X (m)", "#dc2626"],
    ["y", [0, 5.4, 0], "Y (m)", "#16a34a"],
    ["z", [0, 0, 3.4], "Z (m)", "#2563eb"],
  ];
  for (const [name, end, label, color] of axes) {
    if (!visibleAxes[name]) continue;
    drawLine([0, 0, 0], end, color, 2, view);
    drawLabel(end, label, color, view);
  }
}

function drawCameraMarker(point, color, view) {
  const pixel = project(point, view);
  if (!pixel) return;
  context.fillStyle = color;
  context.fillRect(pixel.x - 4, pixel.y - 4, 8, 8);
}

function drawPeople(view) {
  for (const person of people) {
    const skeleton = person.skeleton_3d;
    for (const [start, end] of skeletonLinks) {
      if (skeleton[start] && skeleton[end]) {
        drawLine(skeleton[start], skeleton[end], "#7c3aed", 4, view);
      }
    }
    for (const point of Object.values(skeleton)) {
      const pixel = project(point, view);
      if (!pixel) continue;
      context.fillStyle = "#0891b2";
      context.beginPath();
      context.arc(pixel.x, pixel.y, 5, 0, 7);
      context.fill();
    }
  }
}

function draw() {
  const view = cameraView();
  context.fillStyle = "#f4f5f7";
  context.fillRect(0, 0, innerWidth, innerHeight);
  drawGrid(view);
  scene.draw(view, {
    line: drawLine,
    label: drawLabel,
    marker: drawCameraMarker,
  });
  drawPeople(view);
  context.fillStyle = "#475569";
  context.fillText(
    `Grade: 1 m | distância ${distance.toFixed(1)} m | centro: ${target.map((value) => value.toFixed(1)).join(", ")} m`,
    16,
    innerHeight - 16,
  );
  requestAnimationFrame(draw);
}

function updatePeople(line) {
  const value = JSON.parse(line);
  const message = value.message || value;
  people = (message.objects || []).map((object) => ({
    id: object.id,
    skeleton_3d: Object.fromEntries(
      (object.keypoints || []).map((keypoint) => [
        keypoint.id,
        // Campos protobuf escalares zerados podem ser omitidos no JSON.
        [
          keypoint.position?.x ?? 0,
          keypoint.position?.y ?? 0,
          keypoint.position?.z ?? 0,
        ],
      ]),
    ),
  }));
  worldStatus.textContent = `${people.length} objeto(s) · leitura às ${new Date().toLocaleTimeString("pt-BR")}`;
}

async function readAnnotations() {
  const response = await fetch(canvas.dataset.source);
  if (!response.ok) throw Error("HTTP " + response.status);
  worldStatus.textContent = "Conectado — aguardando anotações…";
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const part = await reader.read();
    if (part.done) {
      buffer += decoder.decode();
      if (buffer.trim()) updatePeople(buffer);
      worldStatus.textContent =
        "Fluxo encerrado. Abra o tópico novamente para reconectar.";
      break;
    }
    buffer += decoder.decode(part.value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        updatePeople(line);
      } catch (error) {
        worldStatus.textContent = "Anotação 3D inválida: " + error.message;
      }
    }
  }
}

draw();
readAnnotations().catch((error) => {
  worldStatus.textContent = "Falha no fluxo: " + error.message;
});
