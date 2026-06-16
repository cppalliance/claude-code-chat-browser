/* Apply saved theme before first paint (avoids dark flash in light mode).
   hljs URLs/integrity must match HLJS_THEME_SHEETS in static/js/shared/theme.js */
(function () {
  var t = localStorage.getItem('theme');
  if (t !== 'light' && t !== 'dark') t = 'dark';
  document.documentElement.setAttribute('data-theme', t);
})();
