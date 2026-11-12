// Превью в Chromium: движка нет, cohtml.js внутри index.js сам включает мок-режим.
(function () {
  window.__errors = [];
  window.addEventListener('error', (e) => window.__errors.push(String(e.message) + ' @' + (e.filename||'') + ':' + (e.lineno||'')));
  window.addEventListener('unhandledrejection', (e) => window.__errors.push('rej: ' + String(e.reason && (e.reason.stack || e.reason)).slice(0,400)));
  let _eng;
  Object.defineProperty(window, 'engine', { configurable: true, get() { return _eng; }, set(v) {
    _eng = v;
    if (v && !v.registerBindingAttribute) v.registerBindingAttribute = function () {};
  } });
  window.GameSettings = new Proxy({}, { get: () => () => null });
})();
