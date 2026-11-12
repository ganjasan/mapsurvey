/*
 * Filter chips over the market guide table (change market-guide-filters, #651).
 *
 * Progressive enhancement only: the server renders every row, and a crawler or an assistant
 * that runs no JavaScript reads the whole table. This script shows the (hidden) filter bar and
 * hides rows that do not match. Within a group chips are alternatives (OR); across groups, and
 * inside a group with data-mode="all", every chosen chip must match (AND).
 *
 * State is kept in the hash as #tools?category=ppgis,field&has=draws_shapes, written with
 * replaceState, so a filtered view is a shareable link but never a new URL for search engines.
 * A link with data-guide-filter="backing=public,nonprofit" applies that filter.
 */
(function () {
  "use strict";

  var bar = document.getElementById("guide-filters");
  var table = document.querySelector("table.guide-table");
  if (!bar || !table) return;

  var HASH_PREFIX = "#tools?";
  var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr[data-category]"));
  var groups = Array.prototype.slice.call(bar.querySelectorAll(".guide-filters__group"));
  var countEl = document.getElementById("guide-filters-count");
  var clearBtn = document.getElementById("guide-filters-clear");
  var emptyRow = document.getElementById("guide-table-empty");
  var total = rows.length;
  // Phone layout: the chip groups fold behind one button (CSS shows it under 720px only).
  var toggle = document.getElementById("guide-filters-toggle");
  var toggleN = toggle && toggle.querySelector(".guide-filters__toggle-n");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = !bar.classList.contains("is-open");
      bar.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  function chipsOf(group) {
    return Array.prototype.slice.call(group.querySelectorAll(".guide-chip"));
  }

  function selection() {
    var state = {};
    groups.forEach(function (group) {
      var values = chipsOf(group)
        .filter(function (chip) { return chip.getAttribute("aria-pressed") === "true"; })
        .map(function (chip) { return chip.dataset.value; });
      if (values.length) state[group.dataset.param] = values;
    });
    return state;
  }

  function rowMatches(row, state) {
    return groups.every(function (group) {
      var param = group.dataset.param;
      var wanted = state[param];
      if (!wanted) return true;
      var have = (row.dataset[param] || "").split(" ");
      var test = function (value) { return have.indexOf(value) !== -1; };
      return group.dataset.mode === "all" ? wanted.every(test) : wanted.some(test);
    });
  }

  function apply(writeHash) {
    var state = selection();
    var shown = 0;
    rows.forEach(function (row) {
      var match = rowMatches(row, state);
      row.hidden = !match;
      if (match) shown += 1;
    });
    var active = Object.keys(state).length > 0;
    countEl.textContent = active
      ? shown + " of " + total + " tools match"
      : total + " tools";
    clearBtn.hidden = !active;
    if (emptyRow) emptyRow.hidden = shown !== 0;
    if (toggleN) {
      var chosen = Object.keys(state).reduce(function (n, k) { return n + state[k].length; }, 0);
      toggleN.textContent = chosen ? "(" + chosen + ")" : "";
    }
    if (writeHash) writeState(state);
  }

  function writeState(state) {
    var parts = Object.keys(state).map(function (param) {
      return param + "=" + state[param].map(encodeURIComponent).join(",");
    });
    var url = window.location.pathname + window.location.search + (parts.length ? HASH_PREFIX + parts.join("&") : "");
    try { window.history.replaceState(null, "", url); } catch (e) { /* file:// or sandboxed frame */ }
  }

  function readState(text) {
    var state = {};
    text.split("&").forEach(function (pair) {
      var eq = pair.indexOf("=");
      if (eq < 1) return;
      state[pair.slice(0, eq)] = pair.slice(eq + 1).split(",").map(decodeURIComponent);
    });
    return state;
  }

  function setState(state) {
    groups.forEach(function (group) {
      var wanted = state[group.dataset.param] || [];
      chipsOf(group).forEach(function (chip) {
        chip.setAttribute("aria-pressed", wanted.indexOf(chip.dataset.value) !== -1 ? "true" : "false");
      });
    });
  }

  groups.forEach(function (group) {
    chipsOf(group).forEach(function (chip) {
      chip.addEventListener("click", function () {
        var on = chip.getAttribute("aria-pressed") === "true";
        chip.setAttribute("aria-pressed", on ? "false" : "true");
        apply(true);
      });
    });
  });

  clearBtn.addEventListener("click", function () {
    setState({});
    apply(true);
  });

  document.querySelectorAll("[data-guide-filter]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      setState(readState(link.dataset.guideFilter));
      apply(true);
      document.getElementById("table").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  // A link to a row the filters hide (#row-decidim from the verdict) would land on nothing.
  window.addEventListener("hashchange", function () {
    if (window.location.hash.indexOf(HASH_PREFIX) === 0) {
      setState(readState(window.location.hash.slice(HASH_PREFIX.length)));
      apply(false);
      return;
    }
    var target = window.location.hash.indexOf("#row-") === 0 && document.getElementById(window.location.hash.slice(1));
    if (target && target.hidden) {
      setState({});
      apply(false);
      target.scrollIntoView({ block: "center" });
    }
  });

  bar.hidden = false;
  if (window.location.hash.indexOf(HASH_PREFIX) === 0) {
    setState(readState(window.location.hash.slice(HASH_PREFIX.length)));
    apply(false);
    document.getElementById("table").scrollIntoView({ block: "start" });
  } else {
    apply(false);
  }
})();
