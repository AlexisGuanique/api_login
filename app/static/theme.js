(() => {
  const KEY = "theme";
  const root = document.documentElement;
  const btn = document.getElementById("themeToggle");

  function getCurrent() {
    const attr = root.getAttribute("data-theme");
    if (attr === "light" || attr === "dark") return attr;
    // default: dark
    return "dark";
  }

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(KEY, theme);
    } catch (e) {}
  }

  if (btn) {
    btn.addEventListener("click", () => {
      const next = getCurrent() === "dark" ? "light" : "dark";
      apply(next);
    });
  }
})();


