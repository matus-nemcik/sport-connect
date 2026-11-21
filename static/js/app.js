// Small progressive enhancements; every page also works without JavaScript.
(function () {
  // Auto-submit selects (community / match pickers) and debounce the team search.
  document.querySelectorAll("form[data-autosubmit]").forEach(function (form) {
    form.querySelectorAll("select").forEach(function (s) {
      s.addEventListener("change", function () { form.submit(); });
    });
    var search = form.querySelector("input[type=search]");
    if (search) {
      var t;
      search.addEventListener("input", function () {
        clearTimeout(t);
        t = setTimeout(function () { form.submit(); }, 450);
      });
      // keep the caret at the end after the page reloads with results
      if (search.value) { search.focus(); var v = search.value; search.value = ""; search.value = v; }
    }
  });

  // +/- steppers for score inputs
  document.querySelectorAll(".stepper").forEach(function (st) {
    var input = st.querySelector("input");
    st.querySelectorAll("button[data-step]").forEach(function (b) {
      b.addEventListener("click", function () {
        var v = parseInt(input.value || "0", 10) + parseInt(b.dataset.step, 10);
        input.value = Math.max(0, Math.min(20, isNaN(v) ? 0 : v));
      });
    });
  });

  // Sticky toolbar: league headers stick right below it; add a shadow once scrolled.
  var toolbar = document.querySelector("[data-toolbar]");
  if (toolbar) {
    var setH = function () { document.documentElement.style.setProperty("--toolbar-h", toolbar.offsetHeight + "px"); };
    setH(); window.addEventListener("resize", setH);
    window.addEventListener("scroll", function () {
      toolbar.classList.toggle("scrolled", toolbar.getBoundingClientRect().top <= 0 && window.scrollY > 40);
    }, { passive: true });
  }

  // Confirmation for destructive forms
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) { if (!window.confirm(f.dataset.confirm)) e.preventDefault(); });
  });
})();
