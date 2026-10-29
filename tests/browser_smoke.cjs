// Executar com Playwright instalado e VIEWER_BASE_URL apontando para o viewer.
// Dados e comandos AMQP são interceptados; este teste nunca move câmeras reais.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const base = process.env.VIEWER_BASE_URL || 'http://127.0.0.1:3000';
    let homeCalls = 0;
    let failPosition = false;
    let position = { pan: 3576, tilt: 40, zoom: 10, units: 'camera_native' };
    await page.route('**/api/cameras/**', async route => {
      const path = new URL(route.request().url()).pathname;
      let data;
      let status = 200;
      if (path.endsWith('/capabilities')) {
        data = { state: 'available', ptz: true, ptz_step: true, ptz_absolute: true };
      } else if (path.endsWith('/home')) {
        assert.equal(route.request().method(), 'POST');
        homeCalls++;
        // Simula firmware limitando zoom a 10: a UI deve mostrar a leitura real.
        position = { pan: 0, tilt: 0, zoom: 10, units: 'camera_native' };
        data = { ok: true };
      } else if (failPosition) {
        data = { detail: 'offline' };
        status = 503;
      } else {
        data = position;
      }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    });
    await page.route('**/stream/**', route => route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="#203043"/><text x="30" y="50" fill="white">Câmera simulada para teste da interface</text></svg>',
    }));
    await page.route('**/skeleton3d-data/**', route => route.fulfill({
      contentType: 'text/plain',
      body: JSON.stringify({ message: { objects: [{ id: 1, keypoints: [
        { id: 7, position: { z: 1.6 } }, { id: 8, position: { x: 0.4, z: 1.6 } },
        { id: 13, position: { z: 0.8 } }, { id: 14, position: { x: 0.4, z: 0.8 } },
      ] }] } }) + '\n',
    }));

    await page.goto(base + '/camera/5');
    await page.locator('.ptz-toggle').click();
    await page.waitForFunction(() => document.querySelector('[data-position=pan]').textContent !== '—');
    assert.equal(await page.locator('[data-position=zoom]').textContent(), '10');
    await page.locator('.ptz-home').click();
    await page.waitForFunction(() => document.querySelector('[data-position=pan]').textContent === '0');
    assert.equal(homeCalls, 1);
    assert.equal(await page.locator('[data-position=zoom]').textContent(), '10');
    await page.screenshot({ path: '/tmp/is-viewer-ptz.png' });
    failPosition = true;
    await page.waitForFunction(() => document.querySelector('.position-status').textContent.includes('indisponível'));
    assert.equal(await page.locator('[data-position=pan]').textContent(), '—');

    await page.goto(base + '/Detector.World3D');
    await page.waitForFunction(() => scene.cameras.length === 7);
    const anonymousObjects = await page.evaluate(() => {
      const state = new window.AnnotationState();
      const chair = (id, x) => ({
        id, label: 'chair', keypoints: [{ position: { x, y: 0, z: 0 } }],
      });
      state.update({ message: { objects: [chair(1, 0), chair(2, 5)] } }, 0);
      // Outro serviço usa os mesmos IDs, mas ocupa outra região do mapa.
      state.update({ message: { objects: [chair(1, 10), chair(2, 15)] } }, 100);
      // O primeiro serviço troca IDs e deixa de publicar uma cadeira.
      const objects = state.update({ message: { objects: [chair(2, 0.1)] } }, 200);
      return objects.map(object => object.keypoints[0].position.x).sort((a, b) => a - b);
    });
    assert.deepEqual(anonymousObjects, [0.1, 10, 15]);
    assert.equal(await page.evaluate(() => scene.visibleCameras().length), 4);
    assert.equal(await page.evaluate(() => people[0].skeleton_3d[7][0]), 0);
    assert.equal(await page.locator('#world-topic').inputValue(), 'Detector.World3D');
    await page.screenshot({ path: '/tmp/is-viewer-world3d.png' });
    const before = await page.evaluate(() => ({ target: [...target], yaw, elevation }));
    await page.mouse.move(700, 500);
    await page.mouse.down({ button: 'middle' });
    await page.mouse.move(780, 550, { steps: 4 });
    await page.mouse.up({ button: 'middle' });
    const after = await page.evaluate(() => ({ target: [...target], yaw, elevation }));
    assert.notDeepEqual(after.target, before.target);
    assert.equal(after.yaw, before.yaw);
    assert.equal(after.elevation, before.elevation);
    await page.mouse.down({ button: 'left' });
    await page.mouse.move(820, 550, { steps: 4 });
    await page.mouse.up({ button: 'left' });
    assert.notEqual(await page.evaluate(() => yaw), before.yaw);
    const distanceBefore = await page.evaluate(() => distance);
    await page.mouse.wheel(0, 100);
    await page.waitForFunction(previous => distance > previous, distanceBefore);
    await page.locator('#show-map').check();
    assert.equal(await page.evaluate(() => scene.visibleCameras().length), 7);
    assert.equal(await page.evaluate(() => scene.polygons.length), 4);
    await page.screenshot({ path: '/tmp/is-viewer-map.png' });
    await page.locator('#show-map').uncheck();
    assert.equal(await page.evaluate(() => scene.visibleCameras().length), 4);
    await page.locator('#world-topic').fill('Tracker.Floor.2.World3D');
    await page.locator('#topic-form button').click();
    await page.waitForURL('**/world3d/Tracker.Floor.2.World3D');
    assert.deepEqual(errors, []);
    console.log('OK: HOME, leitura PTZ, erro de leitura, tópicos World3D, pan, órbita, zoom e mapa.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
