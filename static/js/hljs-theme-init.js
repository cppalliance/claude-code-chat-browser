/* Initial hljs stylesheet for light mode — must match HLJS_THEME_SHEETS.light
   in static/js/shared/theme.js (runtime swaps use applyHljsTheme). */
(function () {
  var t = document.documentElement.getAttribute('data-theme') || 'dark';
  if (t !== 'light') return;
  var link = document.getElementById('hljs-theme');
  if (!link) return;
  link.integrity = 'sha512-0aPQyyeZrWj9sCA46UlmWgKOP0mUipLQ6OZXu8l4IcAmD2u31EPEy9VcIMvl7SoAaKe8bLXZhYoMaE/in+gcgA==';
  link.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';
})();
