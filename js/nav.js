/*
 * Site header navigation (shared by every page).
 *
 * - Mobile menu: #mobileBtn toggles .nav-open on #navLinks. All mobile
 *   styling lives in css/styles.css, so nothing inline survives a
 *   breakpoint change.
 * - Dropdowns: each .nav-dropdown has a <button class="dd-btn">
 *   that toggles .open at every width. Desktop hover still works via CSS.
 *   The Locations hub stays a normal link; its arrow is a separate button.
 * - Escape closes the open dropdown (or the mobile menu) and returns focus.
 * - Listeners are attached once; the breakpoint is read when needed.
 */
(function () {
  "use strict";

  var BREAKPOINT = "(min-width: 1024px)";
  var header = document.getElementById("header");
  var btn = document.getElementById("mobileBtn");
  var nav = document.getElementById("navLinks");
  if (!header || !nav) return;

  var mq = window.matchMedia ? window.matchMedia(BREAKPOINT) : null;
  function isDesktop() { return mq ? mq.matches : window.innerWidth >= 1024; }

  var dropdowns = Array.prototype.slice.call(nav.querySelectorAll(".nav-dropdown"));

  // Wire ARIA relationships for each disclosure button.
  dropdowns.forEach(function (dd, i) {
    var toggle = dd.querySelector("button.dd-btn");
    var menu = dd.querySelector(".dropdown-menu");
    if (!toggle || !menu) return;
    if (!menu.id) menu.id = "nav-dd-" + (i + 1);
    toggle.setAttribute("aria-controls", menu.id);
    toggle.setAttribute("aria-expanded", "false");
  });

  function setDropdown(dd, open) {
    dd.classList.toggle("open", open);
    var toggle = dd.querySelector("button.dd-btn");
    if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
  }
  function closeDropdowns(except) {
    dropdowns.forEach(function (d) { if (d !== except) setDropdown(d, false); });
  }
  function setMenu(open) {
    nav.classList.toggle("nav-open", open);
    if (btn) {
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    }
    if (!open) closeDropdowns();
  }

  // Sticky header shadow.
  window.addEventListener("scroll", function () {
    header.classList.toggle("scrolled", window.scrollY > 20);
  }, { passive: true });

  if (btn) {
    btn.addEventListener("click", function () {
      setMenu(!nav.classList.contains("nav-open"));
    });
  }

  dropdowns.forEach(function (dd) {
    var toggle = dd.querySelector("button.dd-btn");
    if (!toggle) return;
    toggle.addEventListener("click", function () {
      var open = !dd.classList.contains("open");
      closeDropdowns(dd);
      setDropdown(dd, open);
    });
  });

  // Following a link closes the mobile menu.
  nav.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a") : null;
    if (link && !isDesktop()) setMenu(false);
  });

  // Click or tap outside closes any open dropdown.
  document.addEventListener("click", function (e) {
    if (!nav.contains(e.target)) closeDropdowns();
  });

  // Desktop: leaving a dropdown with the keyboard closes it.
  nav.addEventListener("focusout", function (e) {
    if (!isDesktop()) return;
    dropdowns.forEach(function (dd) {
      if (dd.classList.contains("open") && !dd.contains(e.relatedTarget)) setDropdown(dd, false);
    });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" && e.key !== "Esc") return;
    var openDd = dropdowns.filter(function (d) { return d.classList.contains("open"); })[0];
    if (openDd) {
      setDropdown(openDd, false);
      var t = openDd.querySelector("button.dd-btn");
      if (t) t.focus();
      return;
    }
    if (nav.classList.contains("nav-open")) {
      setMenu(false);
      if (btn) btn.focus();
    }
  });

  // Crossing the breakpoint in either direction resets to a closed state.
  function onBreakpointChange() { setMenu(false); }
  if (mq) {
    if (mq.addEventListener) mq.addEventListener("change", onBreakpointChange);
    else if (mq.addListener) mq.addListener(onBreakpointChange);
  }

  setMenu(false);
})();
