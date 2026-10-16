/* Colorado Open Food Web site: shared chrome, data loading and helpers.
   Data comes from data/food-web.json, the statewide app export (scripts/export_app.py, see docs/EXPORTS.md);
   the Pages workflow builds it. Do not edit data files by hand. */
(function(){
  "use strict";
  var ROOT = document.documentElement.getAttribute("data-root") || ".";

  // ---- settings you may need to change -------------------------------------------------------
  var CONFIG = {
    draft: true,                      // true shows the "beta" banner; set false at launch (and drop the noindex tags)
    repo: "https://github.com/open-food-web/colorado-open-food-web",
    supportedFormat: 1                // export format_version this site understands
  };

  // What a pin or card is: the business's own category. Colors come from site.css (--t-*).
  // Pickup points use the owner's color with a 📍 symbol, so they are never a separate "type" to filter by.
  var GROUPS = {
    farm:    { label:"Farms", single:"Farm",           emoji:"🥬", color:"var(--t-farm)",       hex:"#2f6b3c" },
    ranch:   { label:"Ranches", single:"Ranch",         emoji:"🐄", color:"var(--t-ranch)",      hex:"#8a5a3c" },
    orchard: { label:"Orchards", single:"Orchard",        emoji:"🍎", color:"var(--t-farm)",       hex:"#2f6b3c" },
    bakery:  { label:"Bakeries",    single:"Bakery",         emoji:"🥖", color:"var(--t-dining)",     hex:"#5b6b8c" },
    maker:   { label:"Food makers", single:"Food maker",     emoji:"🍞", color:"var(--t-dining)",     hex:"#5b6b8c" },
    winery:  { label:"Wineries", single:"Winery",        emoji:"🍷", color:"var(--t-dining)",     hex:"#5b6b8c" },
    market:  { label:"Farmers markets", single:"Farmers market", emoji:"🧺", color:"var(--t-market)",     hex:"#a8761d" },
    agritourism: { label:"Agritourism", single:"Agritourism",       emoji:"🐴", color:"var(--t-ranch)",      hex:"#8a5a3c" },
    education:   { label:"Agricultural education", single:"Agricultural education", emoji:"🎓", color:"var(--t-community)", hex:"#3f7f9c" },
    access:  { label:"Free food", single:"Free food",       emoji:"🥫", color:"var(--t-assistance)", hex:"#a94f28" },
    // Shops and grocers come from the Food Web's outlets (export "outlets"); the key is the outlet kind.
    apothecary:    { label:"Apothecaries", single:"Apothecary",   shop:true, emoji:"🌿", color:"var(--t-shop)", hex:"#7a4f8f" },
    farm_store:    { label:"Farm stores",  single:"Farm store",   shop:true, emoji:"🏪", color:"var(--t-shop)", hex:"#7a4f8f" },
    grocery:       { label:"Grocers",      single:"Grocer",       shop:true, emoji:"🛒", color:"var(--t-shop)", hex:"#7a4f8f" },
    garden_center: { label:"Garden centers", single:"Garden center", shop:true, emoji:"🪴", color:"var(--t-shop)", hex:"#7a4f8f" },
    other_retail:  { label:"Other shops",  single:"Shop",         shop:true, emoji:"🏪", color:"var(--t-shop)", hex:"#7a4f8f" }
  };
  var SHOPS_LABEL = "Shops & Grocers";
  // "Shops & Grocers · Apothecary" for a shop, the plain label for everything else.
  function catLabel(cat){ var g = GROUPS[cat] || GROUPS.farm; return g.shop ? SHOPS_LABEL + " · " + g.single : g.single; }
  var ROLE_LABEL = { home_base:"At the farm", farm_stand:"Farm stand", pickup:"Pickup point", csa_dropoff:"CSA pickup",
    market_site:"Market", access_site:"Free food", outlet_site:"Shop", store:"Sold here" };
  var MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

  var NAV = [ ["index.html","Map"], ["directory.html","Directory"], ["network.html","Supply network"], ["list-your-business.html","Add or fix a listing"], ["about.html","About"] ];

  function esc(s){
    return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
  }
  function url(path){ return ROOT + "/" + path; }
  // "Suggest an update" and "Remove this listing" open a pre-filled GitHub issue (a free GitHub account is the only sign-in).
  function suggestUrl(rec, what){
    var remove = /remove/i.test(what || "");
    return CONFIG.repo + "/issues/new?template=correction.yml&title=" + encodeURIComponent((remove ? "Remove: " : "Correction: ") + rec.name)
      + "&record=" + encodeURIComponent(rec.name + (rec.town ? " (" + rec.town + ")" : ""));
  }

  function header(){
    var here = document.body.getAttribute("data-page");
    var links = NAV.map(function(n){
      return '<a href="'+url(n[0])+'"'+(n[0] === here ? ' aria-current="page"' : "")+'>'+n[1]+'</a>';
    }).join("");
    return '<a class="skip" href="#main">Skip to content</a>'
      + (CONFIG.draft ? '<div class="draft" role="note"><strong>Beta</strong> — many Colorado listings have no confirmed place to pin yet, so the map is still sparse. <a href="'+url("about.html")+'">About this data</a></div>' : '')
      + '<header class="site-header"><div class="wrap">'
      + '<a class="brand" href="'+url("index.html")+'"><span class="name">Colorado Open Food Web</span></a>'
      + '<button class="menu-btn" aria-expanded="false" aria-controls="sitenav">Menu</button>'
      + '<nav class="nav" id="sitenav" aria-label="Main">'+links+'</nav>'
      + '</div></header>';
  }
  function footer(){
    return '<footer class="site-footer"><div class="wrap"><div class="cols">'
      + '<div><a class="brand" href="'+url("index.html")+'"><span class="name">Colorado Open Food Web</span></a>'
      + '<p style="margin-top:14px">An open dataset of Colorado’s food producers, markets, shops and their sales channels, built from public sources.</p></div>'
      + '<div><h3 style="color:#fff;font-size:1rem">Explore</h3><ul>'
      + NAV.map(function(n){ return '<li><a href="'+url(n[0])+'">'+n[1]+'</a></li>'; }).join("")
      + '</ul></div>'
      + '<div><h3 style="color:#fff;font-size:1rem">Open data</h3><ul>'
      + '<li><a href="'+CONFIG.repo+'" rel="noopener">GitHub repository</a></li>'
      + '<li><a href="'+CONFIG.repo+'/issues/new?template=correction.yml" rel="noopener">Report a correction</a></li>'
      + '<li><a href="'+CONFIG.repo+'/issues/new?template=new-listing.yml" rel="noopener">Add a missing listing</a></li>'
      + '</ul></div></div>'
      + '<p class="fine" id="attribution">Listings come from the <a href="'+CONFIG.repo+'" rel="noopener">Colorado Open Food Web</a>, an open dataset under '
      + '<a href="https://creativecommons.org/licenses/by/4.0/" rel="noopener">CC BY 4.0</a>, built from public web sources and checked against each business’s own website.</p>'
      + '</div></footer>';
  }
  function mountChrome(){
    var h = document.getElementById("site-header"), f = document.getElementById("site-footer");
    if(h) h.outerHTML = header();
    if(f){ f.hidden = false; f.outerHTML = footer(); }
    var btn = document.querySelector(".menu-btn"), nav = document.getElementById("sitenav");
    if(btn && nav) btn.addEventListener("click", function(){
      var open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // ---- data ------------------------------------------------------------------------------------
  var cache = {};
  function load(name){
    if(!cache[name]){
      cache[name] = fetch(url("data/"+name+".json")).then(function(r){
        if(!r.ok) throw new Error(name+".json: HTTP "+r.status);
        return r.json();
      });
    }
    return cache[name];
  }

  function placeTitle(l){
    return l.name || l.address || l.city || "Location";
  }
  function catOf(raw, group){
    if(group === "outlet") return GROUPS[raw.kind] && GROUPS[raw.kind].shop ? raw.kind : "other_retail";
    return group === "farm" ? (GROUPS[raw.kind] ? raw.kind : "farm") : group;
  }
  function makeRec(raw, group, photos, channelLabels, productLabels){
    var cat = catOf(raw, group), places = [];
    var locs = group === "farm" ? raw.locations : [raw.location];
    locs.forEach(function(l){
      if(!l) return;
      var role = group === "farm" ? l.role : (group === "market" ? "market_site" : (group === "outlet" ? "outlet_site" : "access_site"));
      places.push({ id:raw.id + ":" + l.id, rec:null, loc:l, role:role, kind:cat, pickup:(role === "pickup" || role === "csa_dropoff"),
        market:(role === "pickup" && /market/i.test(l.name || "")),   // a stand at a farmers market, not a pickup point
        title:placeTitle(l), hours:l.hours_text || (group === "farm" ? "" : raw.hours_text) || "", days:l.days || [],
        pin:!!l.pin && l.lat != null, unconfirmed:l.pin_basis === "unconfirmed", lat:l.lat, lng:l.lon });
    });
    // A farm that welcomes neither drop-in visits nor pickup at the farm is not somewhere to find them: keep the town, drop the place.
    var counties = [];
    locs.forEach(function(l){ if(l && l.county_fips && counties.indexOf(l.county_fips) === -1) counties.push(l.county_fips); });
    var homeCity = ((places.filter(function(p){ return p.role === "home_base"; })[0] || { loc:{} }).loc.city || "");
    if(group === "farm" && raw.farm_pickup !== true && raw.dropin_visits !== true && !(raw.visits && raw.visits.length) && (raw.dropin_visits === false || raw.farm_pickup === false))
      places = places.filter(function(p){ return p.role !== "home_base"; });
    var towns = [];
    places.forEach(function(p){ if(p.pin && p.loc.city && towns.indexOf(p.loc.city) === -1) towns.push(p.loc.city); });
    if(!towns.length) places.forEach(function(p){ if(p.loc.city && towns.indexOf(p.loc.city) === -1) towns.push(p.loc.city); });
    if(!towns.length && homeCity) towns.push(homeCity);
    var channels = (raw.sales_channels || []);
    var groups = raw.product_groups || [];
    var rec = { id:raw.id, slug:raw.slug, name:raw.name, group:group, cat:cat, raw:raw, productGroups:groups,
      productText:groups.map(function(g){ return productLabels[g] || g; }),
      visits:(group === "farm" ? (raw.visits || []) : []),
      canVisit:(group === "farm" ? (raw.visits || []).length > 0 : true),   // farms: only if there is a named way to visit
      dropin:(group === "farm" ? (raw.dropin_visits == null ? null : raw.dropin_visits) : true),
      farmPickup:(raw.farm_pickup == null ? null : raw.farm_pickup), visitNote:raw.visit_note || "", places:places, towns:towns, counties:counties,
      town:towns[0] || "", channels:channels, channelText:channels.map(function(c){ return channelLabels[c] || c; }),
      homeTown:homeCity,
      photo:photos[raw.slug] || null,
      hours:raw.hours_text || "", products:(raw.products || []).join(", "), categories:raw.categories || [] };
    places.forEach(function(p){ p.rec = rec; });
    rec.search = [raw.name, towns.join(" "), rec.products, rec.productText.join(" "), GROUPS[cat].label,
      places.map(function(p){ return [p.title, p.loc.address].join(" "); }).join(" ")].join(" ").toLowerCase();
    return rec;
  }
  // The whole site runs on this model: every producer, market and free-food site, each with its places.
  function loadModel(){
    if(!cache.model){
      cache.model = Promise.all([load("food-web")]).then(function(r){
        var d = r[0], photos = {}, descs = {};   // facts only: no copied photos or descriptions
        if(d.export.format_version !== CONFIG.supportedFormat)
          throw new Error("this site understands export format " + CONFIG.supportedFormat + ", but the data is format " + d.export.format_version);
        var labels = d.vocab.sales_channels, recs = [];
        var plabels = d.vocab.product_groups || {};
        d.producers.forEach(function(x){ recs.push(makeRec(x, "farm", photos, labels, plabels)); });
        d.markets.forEach(function(x){ recs.push(makeRec(x, "market", photos, labels, plabels)); });
        d.access_points.forEach(function(x){ recs.push(makeRec(x, "access", photos, labels, plabels)); });
        (d.outlets || []).forEach(function(x){ recs.push(makeRec(x, "outlet", photos, labels, plabels)); });   // shops and grocers; absent in older exports
        recs.forEach(function(x){ x.description = descs[x.slug] || descs[x.slug.replace(/-outlet$/, "")] || ""; });   // text each business submitted to the old site (data/descriptions.json)
        return { meta:d.export, vocab:d.vocab, recs:recs, bySlug:recs.reduce(function(o, x){ o[x.slug] = x; return o; }, {}) };
      });
    }
    return cache.model;
  }

  function thisMonth(){ return MONTHS[new Date().getMonth()]; }
  function typeStyle(k){ return GROUPS[k] || GROUPS.farm; }
  // off = [dx, dy] pixel nudge for pins that share one spot (see fanOut). unconfirmed = lighter pin.
  function pinIcon(kind, off, unconfirmed, pickup, market){
    var st = typeStyle(kind), dx = off ? off[0] : 0, dy = off ? off[1] : 0;
    return L.divIcon({ className:"", iconSize:[28,28], iconAnchor:[14-dx,28-dy], popupAnchor:[dx,dy-26],
      html:'<div class="pin'+(unconfirmed ? " unconfirmed" : "")+'" style="background:'+st.hex+'"><span>'+(market ? typeStyle("market").emoji : (pickup ? "📍" : st.emoji))+'</span></div>' });
  }
  // Basemap: OpenStreetMap's standard map. ?basemap=streets (Esri) is there to compare.
  var BASEMAPS = {
    streets: { url:"https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
      attribution:'Tiles &copy; <a href="https://www.esri.com/">Esri</a>, HERE, Garmin, USGS, &copy; OpenStreetMap', maxZoom:19 },
    osm: { url:"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom:19 }
  };
  function basemap(map){
    if (map.attributionControl) map.attributionControl.setPrefix(false);
    var b = BASEMAPS[new URLSearchParams(location.search).get("basemap")] || BASEMAPS.osm;
    return L.tileLayer(b.url, { maxZoom:b.maxZoom, attribution:b.attribution }).addTo(map);
  }
  // Places within ~30 m of each other (two pins at one address) would stack and hide each other;
  // give each a pixel offset in a small ring. list = [{id, lat, lng}]. Returns id -> [dx, dy].
  function fanOut(list){
    var groups = [], out = {}, NEAR = 30;
    list.forEach(function(p){
      var g = null;
      for(var j = 0; j < groups.length && !g; j++){
        var a = groups[j][0], dy = (p.lat - a.lat) * 111320, dx = (p.lng - a.lng) * 111320 * Math.cos(a.lat * Math.PI / 180);
        if(dx*dx + dy*dy <= NEAR*NEAR) g = groups[j];
      }
      if(g) g.push(p); else groups.push([p]);
    });
    groups.forEach(function(g){
      if(g.length < 2) return;
      g.forEach(function(p, i){
        var a = 2*Math.PI*i/g.length - Math.PI/2, r = 13 + 2*g.length;
        out[p.id] = [Math.round(r*Math.cos(a)), Math.round(r*Math.sin(a))];
      });
    });
    return out;
  }
  // No single county line on the statewide site; pages still call this.
  function countyOutline(){ return Promise.resolve(null); }
  function fmtDate(iso){
    if(!iso) return "";
    return new Date(iso + "T12:00:00").toLocaleDateString("en-US", { year:"numeric", month:"long", day:"numeric" });
  }
  function directions(p){
    if(p.lat != null) return "https://www.google.com/maps/dir/?api=1&destination="+p.lat+","+p.lng;
    return "https://www.google.com/maps/search/?api=1&query="+encodeURIComponent([p.title, p.loc && p.loc.city, "CO"].filter(Boolean).join(", "));
  }
  function recUrl(rec){ return url("provider.html?slug="+encodeURIComponent(rec.slug)); }
  function safeLink(u, label){
    if(!/^https?:\/\//i.test(u || "")) return esc(label || u || "");
    return '<a href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(label || u.replace(/^https?:\/\/(www\.)?/,"").replace(/\/$/,"").slice(0,48))+'</a>';
  }
  // Full photo on a listing page; a small square thumbnail on cards (cls "photo" with thumb true).
  function photoHtml(rec, cls, thumb){
    if(!rec.photo) return '<div class="'+cls+' ph" aria-hidden="true"><span>'+typeStyle(rec.cat).emoji+'</span></div>';
    if(thumb && rec.photo.thumb) return '<img class="'+cls+'" src="'+url(rec.photo.thumb)+'" alt="" loading="lazy" width="160" height="160">';
    return '<img class="'+cls+'" src="'+url(rec.photo.file)+'" alt="'+esc(rec.photo.alt)+'" loading="lazy" width="'+rec.photo.width+'" height="'+rec.photo.height+'">';
  }

  // Small flag for lists and popups. Only a confirmed yes is shown; a no or unknown says nothing (the producer page still says it).
  function visitBadge(r){
    if(r.group !== "farm") return "";
    if(r.visits && r.visits.length) return ' <span class="vflag yes">' + r.visits.map(function(v){ return esc(v.label); }).join(" · ") + '</span>';
    return "";
  }

  // "Visit the farm" for a farm, "Visit the shop" for an apothecary or store, and so on, by what kind of business it is.
  var VISIT_WORD = { bakery:"bakery", winery:"winery", apothecary:"shop", shop:"shop", store:"shop", grocer:"shop", market:"market" };
  function visitWord(r){ return VISIT_WORD[r && r.raw && r.raw.kind] || "farm"; }
  function placeLabel(p){ return p.market ? "Sells at the farmers market" : (p.pickup ? "Pickup point" : (p.role === "home_base" && p.rec ? "At the " + visitWord(p.rec) : (ROLE_LABEL[p.role] || ""))); }

  // The list a visitor was last browsing (directory or map results), so a listing page can step to the next one.
  var browse = {
    save: function(slugs){ try{ sessionStorage.setItem("cp-browse", JSON.stringify(slugs)); }catch(e){} },
    get: function(){ try{ return JSON.parse(sessionStorage.getItem("cp-browse") || "null"); }catch(e){ return null; } }
  };

  window.CP = { visitWord:visitWord, browse:browse, placeLabel:placeLabel, visitBadge:visitBadge, esc:esc, url:url, load:load, loadModel:loadModel, CONFIG:CONFIG, GROUPS:GROUPS, catLabel:catLabel, ROLE_LABEL:ROLE_LABEL, MONTHS:MONTHS,
    fanOut:fanOut, thisMonth:thisMonth, typeStyle:typeStyle, pinIcon:pinIcon, basemap:basemap, countyOutline:countyOutline,
    fmtDate:fmtDate, directions:directions, recUrl:recUrl, safeLink:safeLink, photoHtml:photoHtml, suggestUrl:suggestUrl };

  // Real height of the banner + header, so full-height layouts (the map) fit the screen exactly.
  function measureChrome(){
    var h = 0;
    [".draft", ".site-header"].forEach(function(sel){
      var el = document.querySelector(sel);
      if(el) h += el.getBoundingClientRect().height;
    });
    if(h) document.documentElement.style.setProperty("--chrome", Math.round(h) + "px");
  }
  function start(){ mountChrome(); measureChrome(); window.addEventListener("resize", measureChrome); }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
