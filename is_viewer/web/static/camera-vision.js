// O servidor projeta anotações nos espaços original e corrigido da câmera.
async function setupCameraVision(card, cameraId) {
  const image = card.querySelector(".camera-frame img");
  const canvas = card.querySelector(".camera-overlay");
  const context = canvas.getContext("2d");
  const toolbar = card.querySelector(".camera-toolbar");
  const undistort = card.querySelector(".undistort-toggle");
  const overlay3D = card.querySelector(".overlay-toggle");
  const overlay2D = card.querySelector(".overlay-2d-toggle");
  const topic3DLabel = card.querySelector(".annotation-topic");
  const topic2DLabel = card.querySelector(".annotation-2d-topic");
  const coordinatesLabel = card.querySelector(".annotation-2d-coordinates");
  const topic3D = topic3DLabel.querySelector("input");
  const topic2D = topic2DLabel.querySelector("input");
  const coordinates2D = coordinatesLabel.querySelector("select");
  const note = card.querySelector(".calibration-note");
  const topic = card.dataset.topic;
  const state3D = new window.AnnotationState();
  const state2D = new window.AnnotationState(3000, "snapshot");
  let camera;
  let corrected = false;
  let active3D = false;
  let active2D = false;
  let controller3D;
  let controller2D;

  function showNote(message) {
    note.hidden = false;
    note.textContent = message;
  }

  function drawOverlay() {
    canvas.hidden = !active3D && !active2D;
    if (!camera || canvas.hidden) return;
    const [sourceWidth, sourceHeight] = camera.intrinsics.image_size
      ? [camera.intrinsics.image_size.width, camera.intrinsics.image_size.height]
      : [1280, 720];
    const [, , roiWidth, roiHeight] = camera.intrinsics.roi_xywh;
    const [baseWidth, baseHeight] = corrected
      ? [roiWidth, roiHeight]
      : [sourceWidth, sourceHeight];
    canvas.width = image.naturalWidth || baseWidth;
    canvas.height = image.naturalHeight || baseHeight;
    const scaleX = canvas.width / baseWidth;
    const scaleY = canvas.height / baseHeight;
    const pixelOf = (point) => {
      if (!point) return null;
      const values = corrected ? point.corrected : point.raw;
      if (!values || !values.every(Number.isFinite)) return null;
      return [values[0] * scaleX, values[1] * scaleY];
    };

    if (active3D) {
      context.lineWidth = Math.max(2, canvas.width / 450);
      context.strokeStyle = "#c084fc";
      context.fillStyle = "#22d3ee";
      for (const person of state3D.objects()) {
        const points = new Map((person.keypoints || []).map((point) => [point.id, point]));
        for (const [start, end] of window.IS_SKELETON_LINKS) {
          const first = pixelOf(points.get(start));
          const second = pixelOf(points.get(end));
          if (!first || !second) continue;
          context.beginPath();
          context.moveTo(...first);
          context.lineTo(...second);
          context.stroke();
        }
        for (const point of person.keypoints || []) {
          const pixel = pixelOf(point);
          if (!pixel) continue;
          context.beginPath();
          context.arc(pixel[0], pixel[1], Math.max(3, canvas.width / 250), 0, 2 * Math.PI);
          context.fill();
        }
      }
    }

    if (active2D) {
      context.lineWidth = Math.max(2, canvas.width / 500);
      context.strokeStyle = "#fbbf24";
      context.fillStyle = "#fb7185";
      context.font = `${Math.max(12, canvas.width / 85)}px system-ui`;
      for (const object of state2D.objects()) {
        const vertices = (object.region || []).map(pixelOf).filter(Boolean);
        if (vertices.length === 2) {
          const [first, second] = vertices;
          context.strokeRect(
            Math.min(first[0], second[0]),
            Math.min(first[1], second[1]),
            Math.abs(second[0] - first[0]),
            Math.abs(second[1] - first[1]),
          );
        } else if (vertices.length > 2) {
          context.beginPath();
          context.moveTo(...vertices[0]);
          for (const vertex of vertices.slice(1)) context.lineTo(...vertex);
          context.closePath();
          context.stroke();
        }
        for (const point of object.keypoints || []) {
          const pixel = pixelOf(point);
          if (!pixel) continue;
          context.beginPath();
          context.arc(pixel[0], pixel[1], Math.max(3, canvas.width / 260), 0, 2 * Math.PI);
          context.fill();
        }
        const anchor = vertices[0] || pixelOf(object.keypoints?.[0]);
        if (anchor && object.label) context.fillText(object.label, anchor[0] + 4, anchor[1] - 7);
      }
    }
  }

  function stop3D() {
    active3D = false;
    controller3D?.abort();
    controller3D = undefined;
    state3D.clear();
    overlay3D.setAttribute("aria-pressed", "false");
    overlay3D.textContent = "Sobrepor 3D";
    drawOverlay();
  }

  function stop2D() {
    active2D = false;
    controller2D?.abort();
    controller2D = undefined;
    state2D.clear();
    overlay2D.setAttribute("aria-pressed", "false");
    overlay2D.textContent = "Sobrepor 2D";
    drawOverlay();
  }

  async function readAnnotations(source, signal, state, label) {
    const response = await fetch(source, { signal });
    if (!response.ok) throw Error(`HTTP ${response.status}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (!signal.aborted) {
      const part = await reader.read();
      if (part.done) throw Error("fluxo encerrado");
      buffer += decoder.decode(part.value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const objects = state.update(JSON.parse(line));
        drawOverlay();
        showNote(`${objects.length} objeto(s) ${label} · ${label === "3D" ? topic3D.value.trim() : topic2D.value.trim()}`);
      }
    }
  }

  function validTopic(value) {
    return value && value.length <= 255 && !/[/#*]/.test(value);
  }

  function start3D() {
    const name = topic3D.value.trim();
    if (!validTopic(name)) {
      showNote("Informe um tópico 3D concreto, sem /, * ou #");
      return;
    }
    stop3D();
    active3D = true;
    overlay3D.setAttribute("aria-pressed", "true");
    overlay3D.textContent = "Ocultar 3D";
    controller3D = new AbortController();
    const controller = controller3D;
    showNote("Aguardando anotações 3D");
    drawOverlay();
    readAnnotations(`/projection/${cameraId}/${encodeURIComponent(name)}`, controller.signal, state3D, "3D")
      .catch((error) => {
        if (controller.signal.aborted) return;
        stop3D();
        showNote(`Falha nas anotações 3D: ${error.message}`);
      });
  }

  function start2D() {
    const name = topic2D.value.trim();
    if (!validTopic(name)) {
      showNote("Informe um tópico 2D concreto, sem /, * ou #");
      return;
    }
    stop2D();
    active2D = true;
    overlay2D.setAttribute("aria-pressed", "true");
    overlay2D.textContent = "Ocultar 2D";
    controller2D = new AbortController();
    const controller = controller2D;
    const source = `/projection2d/${cameraId}/${encodeURIComponent(name)}?coordinates=${coordinates2D.value}`;
    showNote("Aguardando anotações 2D");
    drawOverlay();
    readAnnotations(source, controller.signal, state2D, "2D").catch((error) => {
      if (controller.signal.aborted) return;
      stop2D();
      showNote(`Falha nas anotações 2D: ${error.message}`);
    });
  }

  let calibrated = false;
  try {
    const response = await fetch("/static/world3d-scene.json");
    if (!response.ok) throw Error(`HTTP ${response.status}`);
    const scene = await response.json();
    camera = scene.cameras.find((item) => item.id === Number(cameraId));
    calibrated = Boolean(camera);
  } catch (error) {
    showNote(`Calibração indisponível: ${error.message}`);
  }
  if (!camera) {
    camera = { intrinsics: {
      image_size: { width: 1280, height: 720 },
      roi_xywh: [0, 0, 1280, 720],
    } };
  }
  toolbar.hidden = false;
  if (calibrated) {
    undistort.hidden = false;
    overlay3D.hidden = false;
    topic3DLabel.hidden = false;
    showNote(`Calibração da câmera ${cameraId} · ROI aplicado ao corrigir · 3D válido na pose PTZ calibrada`);
  }
  overlay2D.hidden = false;
  topic2DLabel.hidden = false;
  coordinatesLabel.hidden = false;
  topic2D.value = `SkeletonDetector.${cameraId}.Detection`;
  const params = new URLSearchParams(location.search);
  if (params.get("annotations")) topic3D.value = params.get("annotations");
  if (params.get("annotations2d")) topic2D.value = params.get("annotations2d");

  undistort.onclick = () => {
    corrected = !corrected;
    undistort.setAttribute("aria-pressed", String(corrected));
    undistort.textContent = corrected ? "Imagem original" : "Sem distorção";
    image.src = `/stream/${encodeURIComponent(topic)}${corrected ? "?undistort=1" : ""}`;
    drawOverlay();
  };
  overlay3D.onclick = () => active3D ? stop3D() : start3D();
  overlay2D.onclick = () => active2D ? stop2D() : start2D();
  topic3D.onchange = () => { if (active3D) start3D(); };
  topic2D.onchange = () => { if (active2D) start2D(); };
  coordinates2D.onchange = () => { if (active2D) start2D(); };
  image.addEventListener("load", drawOverlay);
  const expiryTimer = setInterval(() => {
    const before = state3D.sources.size + state2D.sources.size;
    state3D.objects();
    state2D.objects();
    if (state3D.sources.size + state2D.sources.size !== before) {
      drawOverlay();
      if (!state3D.sources.size && !state2D.sources.size)
        showNote("Aguardando anotações; desenhos anteriores removidos");
    }
  }, 250);
  window.addEventListener("pagehide", () => {
    clearInterval(expiryTimer);
    stop3D();
    stop2D();
  }, { once: true });
}
