for (const cell of document.querySelectorAll(".mosaic-cell")) {
  const form = cell.querySelector("form"),
    input = cell.querySelector("input"),
    image = cell.querySelector("img");
  form.onsubmit = (event) => {
    event.preventDefault();
    const topic = input.value.trim();
    if (topic) {
      image.src = "/stream/" + encodeURIComponent(topic);
      cell.classList.add("loaded");
    }
  };
}
