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

  // Reactions (like / dislike) are sent in the background, so the page is not
  // reloaded and an unsaved tip in the form above is not lost.
  document.querySelectorAll("form.reactions").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.fetch || !e.submitter) return;  // old browsers: normal form submit
      e.preventDefault();
      var data = new FormData(form);
      data.append("value", e.submitter.value);
      var buttons = form.querySelectorAll(".react-btn");
      buttons.forEach(function (b) { b.disabled = true; });
      fetch(form.action, { method: "POST", body: data, headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (res) {
          var like = form.querySelector(".like"), dislike = form.querySelector(".dislike");
          like.querySelector("[data-count]").textContent = res.likes;
          dislike.querySelector("[data-count]").textContent = res.dislikes;
          like.setAttribute("aria-pressed", res.mine === 1 ? "true" : "false");
          dislike.setAttribute("aria-pressed", res.mine === -1 ? "true" : "false");
        })
        .catch(function () { form.submit(); })
        .finally(function () { buttons.forEach(function (b) { b.disabled = false; }); });
    });
  });

  // Unsaved tip survives page reloads (e.g. switching the community) until it is saved.
  document.querySelectorAll("form[data-draft]").forEach(function (form) {
    var key = "draft-" + form.dataset.draft;
    var fields = form.querySelectorAll("input[name=home_score], input[name=away_score], input[name=comment]");
    var store;
    try { store = window.sessionStorage; store.getItem("x"); } catch (err) { return; }
    try {
      var saved = JSON.parse(store.getItem(key) || "null");
      if (saved) fields.forEach(function (f) { if (saved[f.name] !== undefined && saved[f.name] !== "") f.value = saved[f.name]; });
    } catch (err) { /* ignore broken draft */ }
    var remember = function () {
      var d = {};
      fields.forEach(function (f) { d[f.name] = f.value; });
      try { store.setItem(key, JSON.stringify(d)); } catch (err) { /* storage full or blocked */ }
    };
    form.addEventListener("input", remember);
    form.addEventListener("click", function (e) { if (e.target.closest("[data-step]")) remember(); });
    form.addEventListener("submit", function () { try { store.removeItem(key); } catch (err) {} });
  });

  // Confirmation for destructive forms
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) { if (!window.confirm(f.dataset.confirm)) e.preventDefault(); });
  });
})();
