// Progressive enhancement only: every page is fully readable without JavaScript.
(() => {
  // Mobile navigation drawer.
  const toggle = document.querySelector("[data-nav-toggle]");
  const setNav = (open) => {
    document.body.classList.toggle("nav-open", open);
    toggle?.setAttribute("aria-expanded", String(open));
  };
  toggle?.addEventListener("click", () => setNav(!document.body.classList.contains("nav-open")));
  document.querySelector("[data-nav-close]")?.addEventListener("click", () => setNav(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setNav(false); });

  // Auto Analysis: collapsed to key idea / methodology / results, "Full analysis" expands.
  const analysisToggle = document.querySelector("[data-analysis-toggle]");
  const analysis = document.getElementById("analysis-body");
  if (analysisToggle && analysis && analysis.querySelector(".is-secondary")) {
    const label = analysisToggle.querySelector("[data-toggle-label]");
    const setOpen = (open) => {
      analysis.classList.toggle("is-collapsed", !open);
      analysisToggle.setAttribute("aria-expanded", String(open));
      label.textContent = open ? "Collapse" : "Full analysis";
    };
    setOpen(false);
    analysisToggle.hidden = false;
    analysisToggle.addEventListener("click", () => setOpen(analysis.classList.contains("is-collapsed")));
  }

  // Research Feed filters.
  const form = document.querySelector("[data-feed-filters]");
  const list = document.querySelector("[data-feed-list]");
  if (form && list) {
    const rows = [...list.children];
    const count = document.querySelector("[data-feed-count]");
    const sorters = {
      week: null, // server order
      score: (a, b) => Number(b.dataset.score) - Number(a.dataset.score),
      date: (a, b) => (b.dataset.date || "").localeCompare(a.dataset.date || ""),
    };
    const apply = () => {
      const q = form.q.value.trim().toLowerCase();
      const topic = form.topic.value;
      const kind = form.kind.value;
      const top = form.top.checked;
      let shown = 0;
      for (const row of rows) {
        const visible = (!q || row.dataset.text.includes(q))
          && (!topic || row.dataset.topic === topic)
          && (!kind || row.dataset.kind === kind)
          && (!top || row.dataset.top === "yes");
        row.hidden = !visible;
        if (visible) shown += 1;
      }
      const sorter = sorters[form.sort.value];
      list.append(...(sorter ? [...rows].sort(sorter) : rows));
      count.textContent = `${shown} of ${rows.length} items`;
    };
    form.addEventListener("input", apply);
    form.addEventListener("change", apply);
  }
})();
