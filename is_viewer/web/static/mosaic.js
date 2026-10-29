const grid = document.querySelector("main");
const image = document.querySelector("#mosaic-image");
const cells = [...grid.querySelectorAll(".mosaic-cell")];
const topics = cells.map(() => "");
let resizeTimer;

function openMosaic() {
  if (!topics.some(Boolean)) {
    image.removeAttribute("src");
    return;
  }
  const scale = Math.min(1, 1600 / innerWidth, 900 / innerHeight);
  const params = new URLSearchParams({
    width: Math.max(160, Math.round(innerWidth * scale)),
    height: Math.max(120, Math.round(innerHeight * scale)),
  });
  for (const topic of topics) params.append("topic", topic);
  const url = `/mosaic-stream/${grid.dataset.rows}x${grid.dataset.columns}?${params}`;
  if (image.getAttribute("src") !== url) image.src = url;
}

cells.forEach((cell, index) => {
  const form = cell.querySelector("form");
  const input = cell.querySelector("input");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const topic = input.value.trim();
    if (topic.length > 255 || /[/#*]/.test(topic)) {
      input.setCustomValidity("Informe um tópico concreto, sem /, # ou *.");
      input.reportValidity();
      return;
    }
    topics[index] = topic;
    cell.classList.toggle("loaded", Boolean(topic));
    openMosaic();
  });
  input.addEventListener("input", () => input.setCustomValidity(""));
});

addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(openMosaic, 300);
});
