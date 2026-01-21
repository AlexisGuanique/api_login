(() => {
  // Tooltip con delay al cerrar para poder mover el mouse al panel y scrollear.
  const CLOSE_DELAY_MS = 200;

  document.querySelectorAll(".tooltip").forEach((el) => {
    let t = null;
    const panel = el.querySelector(".tooltip__panel");
    const trigger = el.querySelector(".tooltip__trigger");

    function updatePosition() {
      if (!panel || !trigger) return;
      const rect = trigger.getBoundingClientRect();
      // Posicionar arriba del trigger, centrado horizontalmente
      panel.style.bottom = `${window.innerHeight - rect.top + 8}px`;
      panel.style.left = `${rect.left + rect.width / 2}px`;
    }

    function open() {
      if (t) clearTimeout(t);
      t = null;
      updatePosition();
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
    
    // Actualizar posición si scrollea o redimensiona
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
  });
})();


