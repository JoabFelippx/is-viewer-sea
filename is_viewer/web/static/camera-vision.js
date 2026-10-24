// A correção do JPEG e a projeção dos pontos são calculadas no servidor com a
// mesma calibração. O canvas fica alinhado ao tamanho visível do <img> MJPEG.
async function setupCameraVision(card, cameraId) {
  const image = card.querySelector(".camera-frame img");
  const canvas = card.querySelector(".camera-overlay");
  const context = canvas.getContext("2d");
  const toolbar = card.querySelector(".camera-toolbar");
  const undistort = card.querySelector(".undistort-toggle");
  const overlay = card.querySelector(".overlay-toggle");
  const topicLabel = card.querySelector(".annotation-topic");
  const topicInput = topicLabel.querySelector("input");
  const note = card.querySelector(".calibration-note");
  const topic = card.dataset.topic;
  let camera;
  let corrected = false;
  let overlayOn = false;
  let latestObjects = [];
  let streamController;

  function showNote(message) {
    note.hidden = false;
    note.textContent = `${message} · Projeção válida na pose PTZ calibrada.`;
  }

  function drawOverlay() {
    if (!camera || !overlayOn) return;
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
      return [values[0] * scaleX, values[1] * scaleY];
    };
    context.lineWidth = Math.max(2, canvas.width / 450);
    context.strokeStyle = "#c084fc";
    context.fillStyle = "#22d3ee";
    for (const person of latestObjects) {
      const points = new Map(person.keypoints.map((point) => [point.id, point]));
      for (const [start, end] of window.IS_SKELETON_LINKS) {
        const first = pixelOf(points.get(start));
        const second = pixelOf(points.get(end));
        if (!first || !second) continue;
        context.beginPath();
        context.moveTo(...first);
        context.lineTo(...second);
        context.stroke();
      }
      for (const point of person.keypoints) {
        const pixel = pixelOf(point);
        context.beginPath();
        context.arc(pixel[0], pixel[1], Math.max(3, canvas.width / 250), 0, 7);
        context.fill();
      }
    }
  }

  function stopOverlay() {
    overlayOn = false;
    streamController?.abort();
    streamController = undefined;
    latestObjects = [];
    canvas.hidden = true;
    context.clearRect(0, 0, canvas.width, canvas.height);
    overlay.setAttribute("aria-pressed", "false");
    overlay.textContent = "Sobrepor 3D";
  }

  async function readAnnotations(source, signal) {
    const response = await fetch(source, { signal });
    if (!response.ok) throw Error(`HTTP ${response.status}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (overlayOn && !signal.aborted) {
      const part = await reader.read();
      if (part.done) break;
      buffer += decoder.decode(part.value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const value = JSON.parse(line);
        latestObjects = value.objects || [];
        drawOverlay();
        showNote(`${latestObjects.length} objeto(s) 3D · ${topicInput.value.trim()}`);
      }
    }
    if (!signal.aborted) {
      stopOverlay();
      showNote("Fluxo 3D encerrado");
    }
  }

  function startOverlay() {
    const annotationTopic = topicInput.value.trim();
    if (!annotationTopic || annotationTopic.length > 255 || /[/#*]/.test(annotationTopic)) {
      showNote("Informe um tópico 3D concreto, sem /, * ou #");
      return;
    }
    stopOverlay();
    overlayOn = true;
    canvas.hidden = false;
    overlay.setAttribute("aria-pressed", "true");
    overlay.textContent = "Ocultar 3D";
    const controller = new AbortController();
    streamController = controller;
    const source = `/projection/${cameraId}/${encodeURIComponent(annotationTopic)}`;
    showNote("Aguardando anotações 3D");
    readAnnotations(source, controller.signal).catch((error) => {
      if (controller.signal.aborted) return;
      stopOverlay();
      showNote(`Falha nas anotações 3D: ${error.message}`);
    });
  }

  try {
    const response = await fetch("/static/world3d-scene.json");
    if (!response.ok) throw Error(`HTTP ${response.status}`);
    const scene = await response.json();
    camera = scene.cameras.find((item) => item.id === Number(cameraId));
    if (!camera) return;
    toolbar.hidden = false;
    undistort.hidden = false;
    overlay.hidden = false;
    topicLabel.hidden = false;
    undistort.setAttribute("aria-pressed", "false");
    overlay.setAttribute("aria-pressed", "false");
    const requestedTopic = new URLSearchParams(location.search).get("annotations");
    if (requestedTopic) topicInput.value = requestedTopic;
    showNote(`Calibração da câmera ${cameraId} · ROI aplicado ao corrigir`);
  } catch (error) {
    showNote(`Calibração indisponível: ${error.message}`);
    return;
  }

  undistort.onclick = () => {
    corrected = !corrected;
    undistort.setAttribute("aria-pressed", String(corrected));
    undistort.textContent = corrected ? "Imagem original" : "Sem distorção";
    image.src = `/stream/${encodeURIComponent(topic)}${corrected ? "?undistort=1" : ""}`;
    drawOverlay();
  };
  overlay.onclick = () => {
    if (overlayOn) {
      stopOverlay();
      showNote(`Calibração da câmera ${cameraId}`);
    } else {
      startOverlay();
    }
  };
  topicInput.onchange = () => {
    if (overlayOn) startOverlay();
  };
  image.addEventListener("load", drawOverlay);
  window.addEventListener("pagehide", stopOverlay, { once: true });
}
