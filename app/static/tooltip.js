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
      // Posicionar debajo del trigger, centrado horizontalmente
      const x = rect.left + rect.width / 2;
      const y = rect.bottom + 8;
      
      // Calcular espacio disponible debajo
      const spaceBelow = window.innerHeight - y;
      const minSpace = 32; // espacio mínimo que queremos dejar
      const defaultMaxHeight = 240; // altura máxima por defecto
      
      // Si no hay suficiente espacio, ajustar max-height dinámicamente
      if (spaceBelow < defaultMaxHeight + minSpace) {
        // Ajustar altura para que quepa, dejando un margen mínimo
        const adjustedHeight = Math.max(120, spaceBelow - minSpace);
        panel.style.maxHeight = `${adjustedHeight}px`;
      } else {
        // Restaurar altura por defecto si hay espacio
        panel.style.maxHeight = `${defaultMaxHeight}px`;
      }
      
      panel.style.left = `${x}px`;
      panel.style.top = `${y}px`;
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


