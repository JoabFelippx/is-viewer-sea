// Cada cartão tem controles, preferências e consulta de posição independentes.
for (const card of document.querySelectorAll(".camera")) setupCamera(card);

function setupCamera(card) {
  const cameraId = card.dataset.topic.split(".")[1];
  const api = `/api/cameras/${cameraId}`;
  const status = card.querySelector(".status");
  const controls = card.querySelector(".ptz");
  const toolbar = card.querySelector(".camera-toolbar");
  const toggle = card.querySelector(".ptz-toggle");
  const home = card.querySelector(".ptz-home");
  const stepButtons = [...controls.querySelectorAll("[data-pan], [data-zoom]")];
  const stepDegrees = card.querySelector(".step-degrees");
  const invertPan = card.querySelector(".invert-pan");
  const invertTilt = card.querySelector(".invert-tilt");
  const positionStatus = card.querySelector(".position-status");
  const positions = [...card.querySelectorAll("[data-position]")];
  const settingsKey = `is-viewer.ptz.${card.dataset.topic}`;
  let capabilities = {};
  let moving = false;
  let polling = false;
  let timer;
  const controller = new AbortController();
  setupCameraVision(card, cameraId);

  try {
    const saved = JSON.parse(localStorage.getItem(settingsKey) || "{}");
    if (saved.step) stepDegrees.value = saved.step;
    invertPan.checked = !!saved.invertPan;
    invertTilt.checked = !!saved.invertTilt;
  } catch {
    // Preferências inválidas não impedem a visualização.
  }
  for (const input of [stepDegrees, invertPan, invertTilt]) {
    input.onchange = () =>
      localStorage.setItem(
        settingsKey,
        JSON.stringify({
          step: Number(stepDegrees.value),
          invertPan: invertPan.checked,
          invertTilt: invertTilt.checked,
        }),
      );
  }

  function updateButtons() {
    for (const button of stepButtons)
      button.disabled = moving || !capabilities.ptz_step;
    home.disabled = moving || !capabilities.ptz_absolute;
    home.title = capabilities.ptz_absolute
      ? "Ir para a posição absoluta (0, 0, 0)"
      : "Esta câmera não oferece PTZ absoluto";
  }
  updateButtons();

  async function readPosition() {
    if (polling || moving || controls.hidden || document.hidden) return;
    polling = true;
    try {
      const position = await fetch(`${api}/ptz`, {
        signal: controller.signal,
      }).then(readResponse);
      for (const output of positions) {
        const value = position[output.dataset.position];
        output.textContent =
          typeof value === "number" && Number.isFinite(value)
            ? value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })
            : "—";
      }
      positionStatus.textContent = `Leitura às ${new Date().toLocaleTimeString("pt-BR")}`;
    } catch (error) {
      // Não apresentar a última leitura como se ainda fosse atual.
      for (const output of positions) output.textContent = "—";
      positionStatus.textContent = "Posição indisponível: " + error.message;
    } finally {
      polling = false;
    }
  }

  fetch(`${api}/capabilities`, { signal: controller.signal })
    .then(readResponse)
    .then((value) => {
      capabilities = value;
      toggle.hidden = !(value.state === "available" && value.ptz);
      if (!toggle.hidden) toolbar.hidden = false;
      updateButtons();
    })
    .catch(() => {
      status.textContent = "controle indisponível";
      status.hidden = false;
    });

  toggle.onclick = () => {
    controls.hidden = !controls.hidden;
    toggle.textContent = controls.hidden ? "PTZ" : "Fechar";
    clearInterval(timer);
    if (!controls.hidden) {
      readPosition();
      timer = setInterval(readPosition, 1500);
    }
  };

  async function sendCommand(path, payload) {
    if (moving) return;
    moving = true;
    status.hidden = true;
    updateButtons();
    try {
      await fetch(api + path, {
        method: "POST",
        signal: controller.signal,
        headers: { "content-type": "application/json" },
        body: payload === undefined ? undefined : JSON.stringify(payload),
      }).then(readResponse);
    } catch (error) {
      status.textContent = "erro PTZ: " + error.message;
      status.hidden = false;
    } finally {
      moving = false;
      updateButtons();
      // A leitura vem da câmera; não zeramos o indicador ao solicitar HOME.
      readPosition();
    }
  }

  home.onclick = () => sendCommand("/ptz/home");
  for (const button of stepButtons) {
    button.onclick = () =>
      sendCommand("/ptz", {
        pan: Number(button.dataset.pan || 0) * (invertPan.checked ? -1 : 1),
        tilt: Number(button.dataset.tilt || 0) * (invertTilt.checked ? -1 : 1),
        zoom: Number(button.dataset.zoom || 0),
        step_degrees: Number(stepDegrees.value),
      });
  }
  document.addEventListener("visibilitychange", readPosition);
  window.addEventListener(
    "pagehide",
    () => {
      clearInterval(timer);
      controller.abort();
      document.removeEventListener("visibilitychange", readPosition);
    },
    { once: true },
  );
}

async function readResponse(response) {
  const body = await response.json();
  if (!response.ok) throw Error(body.detail || response.status);
  return body;
}
