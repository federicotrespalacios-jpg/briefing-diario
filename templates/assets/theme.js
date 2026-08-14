// Toggle de tema manual, superpuesto a prefers-color-scheme.
// Guarda la preferencia en localStorage; si no hay preferencia guardada,
// se respeta el tema del sistema (ver styles.css, sin data-theme aplicado).
(function () {
  var STORAGE_KEY = "briefing-theme";

  function aplicar(tema) {
    if (tema === "light" || tema === "dark") {
      document.documentElement.setAttribute("data-theme", tema);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }

  var guardado = localStorage.getItem(STORAGE_KEY);
  if (guardado) aplicar(guardado);

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var actual = document.documentElement.getAttribute("data-theme");
      var prefiereDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      var efectivo = actual || (prefiereDark ? "dark" : "light");
      var siguiente = efectivo === "dark" ? "light" : "dark";
      aplicar(siguiente);
      localStorage.setItem(STORAGE_KEY, siguiente);
    });
  });
})();
