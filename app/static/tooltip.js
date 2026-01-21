(() => {
  // Tooltip con delay al cerrar para poder mover el mouse al panel y scrollear.
  const CLOSE_DELAY_MS = 200;

  document.querySelectorAll(".tooltip").forEach((el) => {
    let t = null;

    function open() {
      if (t) clearTimeout(t);
      t = null;
      el.classList.add("tooltip--open");
    }

    function closeWithDelay() {
      if (t) clearTimeout(t);
      t = setTimeout(() => {
        el.classList.remove("tooltip--open");
        t = null;
      }, CLOSE_DELAY_MS);
    }

    el.addEventListener("mouseenter", open);
    el.addEventListener("mouseleave", closeWithDelay);
    el.addEventListener("focusin", open);
    el.addEventListener("focusout", closeWithDelay);
  });
})();


