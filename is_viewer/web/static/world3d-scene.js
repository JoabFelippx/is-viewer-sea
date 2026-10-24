// Dados estáticos em metros, no mesmo referencial Z-up das anotações.
class WorldScene {
  constructor() {
    this.cameras = [];
    this.polygons = [];
    this.showMap = false;
  }

  async load() {
    const response = await fetch("/static/world3d-scene.json");
    if (!response.ok)
      throw Error("Não foi possível carregar mapa e calibrações");
    const scene = await response.json();
    this.cameras = scene.cameras;
    this.polygons = scene.map.polygons;
  }

  visibleCameras() {
    return this.cameras.filter((camera) => this.showMap || !camera.map_only);
  }

  bounds() {
    const points = this.visibleCameras().map((camera) => camera.position);
    points.push([-5, -5, 0], [5, 5, 3]);
    if (this.showMap) points.push(...this.polygons.flat());
    return {
      min: [0, 1, 2].map((axis) =>
        Math.min(...points.map((point) => point[axis])),
      ),
      max: [0, 1, 2].map((axis) =>
        Math.max(...points.map((point) => point[axis])),
      ),
    };
  }

  draw(view, { line, label, marker }) {
    if (this.showMap) {
      for (const polygon of this.polygons) {
        for (let index = 0; index < polygon.length; index++) {
          line(
            polygon[index],
            polygon[(index + 1) % polygon.length],
            "#64748b",
            1.5,
            view,
          );
        }
      }
    }
    for (const camera of this.visibleCameras()) {
      const color = camera.map_only ? "#c2410c" : "#0369a1";
      const position = camera.position;
      const tip = position.map(
        (value, axis) => value + camera.forward[axis] * 0.8,
      );
      line([position[0], position[1], 0], position, "#94a3b8", 1, view);
      line(position, tip, color, 3, view);
      marker(position, color, view);
      label(position, `Câmera ${camera.id}`, color, view, 9, -9);
    }
  }
}
