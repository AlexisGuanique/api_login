(() => {
  const root = document.documentElement;
  const btn = document.getElementById("sidebarToggle");
  const overlay = document.getElementById("sidebarOverlay");

  function open() {
    root.setAttribute("data-sidebar", "open");
    if (overlay) overlay.setAttribute("aria-hidden", "false");
  }

  function close() {
    root.setAttribute("data-sidebar", "closed");
    if (overlay) overlay.setAttribute("aria-hidden", "true");
  }

  function isOpen() {
    return root.getAttribute("data-sidebar") === "open";
  }

  if (btn) {
    btn.addEventListener("click", () => {
      isOpen() ? close() : open();
    });
  }

  if (overlay) {
    overlay.addEventListener("click", close);
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });

  // Estado inicial (mobile cerrado)
  if (!root.getAttribute("data-sidebar")) {
    close();
  }
})();


