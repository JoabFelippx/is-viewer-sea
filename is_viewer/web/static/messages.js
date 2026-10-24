const main = document.querySelector("main");
const historyLimit = Number(main.dataset.history);

function showMessage(line) {
  if (!line.trim()) return;
  const item = document.createElement("article");
  const content = document.createElement("pre");
  try {
    content.textContent = JSON.stringify(JSON.parse(line), null, 2);
  } catch {
    content.textContent = line;
  }
  item.append(content);
  main.prepend(item);
  while (main.children.length > historyLimit) main.lastChild.remove();
}

async function readMessages() {
  const response = await fetch(main.dataset.source);
  if (!response.ok) throw Error("HTTP " + response.status);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  // Um bloco da rede pode conter várias linhas ou apenas parte de uma linha.
  for (;;) {
    const part = await reader.read();
    if (part.done) break;
    buffer += decoder.decode(part.value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) showMessage(line);
  }
}

readMessages().catch((error) => {
  main.textContent = "error: " + error.message;
});
