// Cada mensagem de um publicador representa um quadro completo de seus objetos.
// Sem identificador de origem, aproximamos mensagens pela posição dos objetos.
class AnnotationState {
  constructor(ttlMs = 3000, mode = "merge") {
    this.ttlMs = ttlMs;
    this.mode = mode;
    this.sources = new Map();
    this.nextAnonymous = 0;
  }

  static anchor(object) {
    const candidates = [
      ...(object.keypoints || []),
      ...(Array.isArray(object.region) ? object.region : object.region?.vertices || []),
    ];
    const points = candidates.map((item) => {
      if (Array.isArray(item.raw)) return { units: "pixels", xyz: item.raw };
      if (item.position) return {
        units: "world",
        xyz: [item.position.x ?? 0, item.position.y ?? 0, item.position.z ?? 0],
      };
      if (Number.isFinite(item.x) && Number.isFinite(item.y))
        return { units: "pixels", xyz: [item.x, item.y] };
      return null;
    }).filter(Boolean);
    if (!points.length) return null;
    const units = points[0].units;
    const compatible = points.filter((point) => point.units === units);
    return {
      units,
      xyz: compatible[0].xyz.map((_, axis) =>
        compatible.reduce((sum, point) => sum + Number(point.xyz[axis]), 0) / compatible.length,
      ),
    };
  }

  static distance(first, second) {
    if (first.label !== second.label) return Infinity;
    const a = AnnotationState.anchor(first);
    const b = AnnotationState.anchor(second);
    if (!a || !b) return !a && !b && first.id === second.id ? 0 : Infinity;
    if (a.units !== b.units) return Infinity;
    const distance = Math.hypot(...a.xyz.map((value, axis) => value - b.xyz[axis]));
    return distance < (a.units === "pixels" ? 150 : 1.5) ? distance : Infinity;
  }

  static overlap(current, previous) {
    const pairs = [];
    for (let i = 0; i < current.length; i++) {
      for (let j = 0; j < previous.length; j++) {
        const distance = AnnotationState.distance(current[i], previous[j]);
        if (Number.isFinite(distance)) pairs.push({ i, j, distance });
      }
    }
    pairs.sort((a, b) => a.distance - b.distance);
    const currentUsed = new Set();
    const previousUsed = new Set();
    let totalDistance = 0;
    for (const pair of pairs) {
      if (currentUsed.has(pair.i) || previousUsed.has(pair.j)) continue;
      currentUsed.add(pair.i);
      previousUsed.add(pair.j);
      totalDistance += pair.distance;
    }
    return { matched: currentUsed.size, distance: totalDistance };
  }

  updateAnonymous(objects, now) {
    if (!objects.length) return;
    let chosen;
    let bestMatched = 0;
    let bestDistance = Infinity;
    for (const [key, snapshot] of this.sources) {
      if (!key.startsWith("anonymous:")) continue;
      const overlap = AnnotationState.overlap(objects, snapshot.objects);
      const smallerBatch = Math.min(objects.length, snapshot.objects.length);
      // Metade do lote menor pode continuar visível mesmo se outros objetos
      // aparecerem ou desaparecerem entre quadros.
      if (overlap.matched < Math.ceil(smallerBatch / 2)) continue;
      if (overlap.matched > bestMatched || (
        overlap.matched === bestMatched && overlap.distance < bestDistance
      )) {
        chosen = key;
        bestMatched = overlap.matched;
        bestDistance = overlap.distance;
      }
    }
    if (!chosen) chosen = `anonymous:${this.nextAnonymous++}`;
    // Substituir o quadro remove de imediato objetos ausentes no novo lote.
    this.sources.set(chosen, { objects, receivedAt: now });
  }

  update(value, now = performance.now()) {
    const message = value.message || value;
    const objects = message.objects || [];
    if (this.mode === "snapshot") {
      this.sources.clear();
      this.sources.set("latest", { objects, receivedAt: now });
    } else if (value.publisher != null && value.publisher !== "") {
      this.sources.set(`publisher:${value.publisher}`, { objects, receivedAt: now });
    } else {
      this.updateAnonymous(objects, now);
    }
    return this.objects(now);
  }

  objects(now = performance.now()) {
    for (const [publisher, snapshot] of this.sources) {
      if (now - snapshot.receivedAt >= this.ttlMs) this.sources.delete(publisher);
    }
    return [...this.sources.values()].flatMap((snapshot) => snapshot.objects);
  }

  clear() {
    this.sources.clear();
  }
}

window.AnnotationState = AnnotationState;
