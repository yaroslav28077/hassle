// Тестовая сцена HUD для превью (вызывается из браузера: __scene({...})).
window.__scene = function (opts) {
  opts = opts || {};
  const H = window.getInterface("Hud");
  if (!H) return "no hud";
  const d = H.$data;
  d.server = 16; d.bonus = opts.bonus || 2;
  Object.assign(d.info, { show: true, showBars: true, isShowValues: true, health: 62, armour: opts.armour ?? 40, hunger: 57,
    money: 6043000, wanted: opts.wanted ?? 2, online: 482, id: 141, weapon: opts.weapon ?? 0, ammoInClip: 50, totalAmmo: 200, breath: 100 });
  if (d.radar) Object.assign(d.radar, { show: true, greenZone: opts.greenZone ?? true, fishingZone: false });
  if (d.radar && d.radar.immortality && opts.immortality) Object.assign(d.radar.immortality, { show: true, progress: 60 });
  if (opts.car !== false && d.speedometer) {
    Object.assign(d.speedometer, { show: true, fuel: opts.fuel ?? 59, maxFuel: 100, mileage: 4998 });
    Object.assign(d.speedometer.params, { engine: opts.engine ?? true, key: true, lights: true, rem: true, doors: true, wash: opts.wash ?? 0.5 });
  }
  d.isShowRadar = true;
  return "ok";
};
