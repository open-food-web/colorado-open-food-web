(function () {
  "use strict";
  var REPO = "https://github.com/open-food-web/colorado-open-food-web";
  var TYPES = [
    { id: "farm", label: "Farms & ranches" }, { id: "maker", label: "Food makers" },
    { id: "restaurant", label: "Restaurants" }, { id: "retail", label: "Shops & grocers" },
    { id: "distributor", label: "Distributors" }, { id: "market", label: "Markets" }
  ];
  var color = function (t) { return getComputedStyle(document.querySelector(".net")).getPropertyValue("--" + t).trim() || "#888"; };
  var el = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var safeUrl = function (u) { return /^https?:\/\//i.test(u || "") ? u : ""; };

  function build(web) {
    var nodes = web.nodes.map(function (n) { return Object.assign({}, n); });
    var links = web.edges.map(function (e) { return { source: e.s, target: e.t, src: e.src, ok: e.ok }; });
    var buys = {}, sells = {}, deg = {};
    links.forEach(function (l) {
      (buys[l.target] = buys[l.target] || []).push({ id: l.source, src: l.src, ok: l.ok });
      (sells[l.source] = sells[l.source] || []).push({ id: l.target, src: l.src, ok: l.ok });
      deg[l.source] = (deg[l.source] || 0) + 1; deg[l.target] = (deg[l.target] || 0) + 1;
    });
    nodes.forEach(function (n) { n.deg = deg[n.id] || 0; });
    var visible = {}; TYPES.forEach(function (t) { visible[t.id] = true; });
    var selected = null;

    var svg = d3.select("#graph"), stage = el("graph").parentNode;
    var W = stage.clientWidth, H = stage.clientHeight;
    var root = svg.append("g");
    svg.call(d3.zoom().scaleExtent([.3, 6]).on("zoom", function (ev) { root.attr("transform", ev.transform); }));
    var linkSel = root.append("g").selectAll("line").data(links).join("line").attr("class", function (d) { return "link" + (d.ok ? "" : " soft"); });
    var nodeSel = root.append("g").selectAll("circle").data(nodes).join("circle")
      .attr("class", "node").attr("r", function (d) { return 4 + Math.sqrt(d.deg) * 2.2; })
      .attr("fill", function (d) { return color(d.type); }).attr("tabindex", 0).attr("role", "button")
      .attr("aria-label", function (d) { return d.name + ", " + d.city; });
    var labSel = root.append("g").selectAll("text").data(nodes).join("text").attr("class", "lab").attr("dy", -9).attr("text-anchor", "middle")
      .text(function (d) { return d.name; }).style("display", function (d) { return d.deg >= 9 ? null : "none"; });

    var sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(function (d) { return d.id; }).distance(34).strength(.5))
      .force("charge", d3.forceManyBody().strength(-70))
      .force("collide", d3.forceCollide().radius(function (d) { return 6 + Math.sqrt(d.deg) * 2.2; }))
      .force("x", d3.forceX(W / 2).strength(.04)).force("y", d3.forceY(H / 2).strength(.06))
      .on("tick", function () {
        linkSel.attr("x1", function (d) { return d.source.x; }).attr("y1", function (d) { return d.source.y; }).attr("x2", function (d) { return d.target.x; }).attr("y2", function (d) { return d.target.y; });
        nodeSel.attr("cx", function (d) { return d.x; }).attr("cy", function (d) { return d.y; });
        labSel.attr("x", function (d) { return d.x; }).attr("y", function (d) { return d.y; });
      });
    nodeSel.call(d3.drag().on("start", function (ev, d) { if (!ev.active) sim.alphaTarget(.25).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", function (ev, d) { d.fx = ev.x; d.fy = ev.y; })
      .on("end", function (ev, d) { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
    el("hint").textContent = "Scroll to zoom · drag to move · click a dot";

    function neighbours(id) {
      var s = {}; s[id] = 1;
      (buys[id] || []).forEach(function (x) { s[x.id] = 1; }); (sells[id] || []).forEach(function (x) { s[x.id] = 1; });
      return s;
    }
    function paint(focusId) {
      var near = focusId == null ? null : neighbours(focusId);
      nodeSel.classed("dim", function (d) { return !visible[d.type] || (near && !near[d.id]); })
        .style("pointer-events", function (d) { return visible[d.type] ? null : "none"; }).classed("sel", function (d) { return d.id === selected; });
      linkSel.classed("dim", function (d) { return !visible[d.source.type] || !visible[d.target.type] || (near && !(d.source.id === focusId || d.target.id === focusId)); })
        .classed("hot", function (d) { return near && (d.source.id === focusId || d.target.id === focusId); });
      labSel.classed("dim", function (d) { return !visible[d.type] || (near && !near[d.id]); })
        .style("display", function (d) { return d.deg >= 9 || (near && near[d.id]) ? null : "none"; });
    }
    function link(list, empty) {
      if (!list || !list.length) return "<p class='empty'>" + empty + "</p>";
      return "<ul>" + list.map(function (x) {
        var n = nodes[x.id], u = safeUrl(x.src);
        return '<li><button data-id="' + n.id + '">' + esc(n.name) + "</button>" +
          (u ? '<a class="src" href="' + esc(u) + '" rel="noopener" aria-label="Source for ' + esc(n.name) + '">source ↗</a>' : "") +
          (x.ok ? "" : '<span class="src"> · not yet confirmed</span>') + "</li>";
      }).join("") + "</ul>";
    }
    function select(id) {
      selected = id; var n = nodes[id], t = TYPES.filter(function (x) { return x.id === n.type; })[0];
      var flag = REPO + "/issues/new?template=correction.yml&title=" + encodeURIComponent("Correction: " + n.name) + "&record=" + encodeURIComponent(n.name + (n.city ? " (" + n.city + ")" : ""));
      el("detail").innerHTML =
        "<h3>" + esc(n.name) + '</h3><p class="meta"><i style="background:' + color(n.type) + '"></i>' + esc(t ? t.label : n.type) + (n.city ? " · " + esc(n.city) : "") + "</p>" +
        "<h4>Buys from</h4>" + link(buys[id], "No suppliers recorded yet.") +
        "<h4>Supplies</h4>" + link(sells[id], "No customers recorded yet.") +
        '<div class="actions">' + (safeUrl(n.site) ? '<a class="btn" href="' + esc(n.site) + '" rel="noopener">Website ↗</a>' : "") +
        '<a class="btn" href="' + esc(flag) + '" rel="noopener">Flag a change</a></div>';
      Array.prototype.forEach.call(el("detail").querySelectorAll("button[data-id]"), function (b) { b.onclick = function () { select(+b.dataset.id); }; });
      paint(id);
    }
    nodeSel.on("mouseover", function (ev, d) { if (selected == null) paint(d.id); })
      .on("mouseout", function () { if (selected == null) paint(null); })
      .on("click", function (ev, d) { select(d.id); }).on("keydown", function (ev, d) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(d.id); } });
    svg.on("click", function (ev) { if (ev.target === el("graph")) { selected = null; el("detail").innerHTML = '<p class="empty">Select a business to see who it buys from and who it supplies.</p>'; paint(null); } });

    el("chips").innerHTML = TYPES.map(function (t) {
      var c = nodes.filter(function (n) { return n.type === t.id; }).length;
      return '<button class="chip" type="button" aria-pressed="true" data-t="' + t.id + '"><i style="background:' + color(t.id) + '"></i>' + esc(t.label) + "<span>" + c + "</span></button>";
    }).join("");
    Array.prototype.forEach.call(el("chips").querySelectorAll(".chip"), function (b) {
      b.onclick = function () { visible[b.dataset.t] = !visible[b.dataset.t]; b.setAttribute("aria-pressed", visible[b.dataset.t]); paint(selected); };
    });

    var q = el("q"), res = el("results");
    q.addEventListener("input", function () {
      var v = q.value.trim().toLowerCase(); res.innerHTML = "";
      if (v.length < 2) return;
      nodes.filter(function (n) { return n.name.toLowerCase().indexOf(v) > -1 || (n.city || "").toLowerCase().indexOf(v) > -1; }).slice(0, 8).forEach(function (n) {
        var li = document.createElement("li"), b = document.createElement("button");
        b.type = "button"; b.setAttribute("role", "option"); b.innerHTML = esc(n.name) + " <small>" + esc(n.city) + "</small>";
        b.onclick = function () { select(n.id); res.innerHTML = ""; q.value = n.name; };
        li.appendChild(b); res.appendChild(li);
      });
    });
  }

  fetch("data/web.json").then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (web) {
      el("net-count").textContent = web.nodes.length.toLocaleString() + " businesses and " + web.edges.length.toLocaleString() + " sourced connections.";
      build(web);
    })
    .catch(function () { el("hint").textContent = "The network data could not be loaded. Try again later."; });
})();
