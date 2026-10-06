/*
 * Scroll reveal, as progressive enhancement.
 *
 * .reveal content is visible by default. A tiny inline script in <head>
 * adds .js-reveal to <html> (only when IntersectionObserver exists and the
 * visitor has not asked for reduced motion), which is what hides .reveal
 * until it scrolls into view. That head script also removes .js-reveal
 * after 3s unless this file has marked the page .reveal-ready, so content
 * reappears if this script fails to load or throws.
 */
(function () {
  "use strict";
  var root = document.documentElement;
  if (!root.classList.contains("js-reveal")) return;

  try {
    var els = document.querySelectorAll(".reveal");
    var observer = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        // Tall blocks can never reach a 15% ratio, so also accept 15% of
        // the viewport height being on screen.
        var enough = entry.intersectionRatio >= 0.15 ||
          entry.intersectionRect.height >= window.innerHeight * 0.15;
        if (enough) {
          entry.target.classList.add("active");
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: [0, 0.05, 0.1, 0.15], rootMargin: "0px 0px -20px 0px" });
    Array.prototype.forEach.call(els, function (el) { observer.observe(el); });
    root.classList.add("reveal-ready");
  } catch (e) {
    root.classList.remove("js-reveal");
  }
})();
