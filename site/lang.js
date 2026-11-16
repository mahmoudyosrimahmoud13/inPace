// Which language the website speaks. English and Arabic are written into each page; the rest are
// small files in i18n/, fetched only when someone picks that language. A page with no file for a
// language simply stays English, which is better than a half-translated page.
(function () {
  var SPEAKS = ["en", "ar", "es", "fr", "de", "pt", "id", "tr", "vi", "ru", "hi", "th", "ja", "zh"];
  var picker = document.getElementById("lang");
  if (picker) {
    picker.innerHTML = "<option value=\"en\">English</option><option value=\"ar\">\u0627\u0644\u0639\u0631\u0628\u064a\u0629</option><option value=\"es\">Espa\u00f1ol</option><option value=\"fr\">Fran\u00e7ais</option><option value=\"de\">Deutsch</option><option value=\"pt\">Portugu\u00eas</option><option value=\"id\">Bahasa Indonesia</option><option value=\"tr\">T\u00fcrk\u00e7e</option><option value=\"vi\">Ti\u1ebfng Vi\u1ec7t</option><option value=\"ru\">\u0420\u0443\u0441\u0441\u043a\u0438\u0439</option><option value=\"hi\">\u0939\u093f\u0928\u094d\u0926\u0940</option><option value=\"th\">\u0e44\u0e17\u0e22</option><option value=\"ja\">\u65e5\u672c\u8a9e</option><option value=\"zh\">\u7b80\u4f53\u4e2d\u6587</option>";
    picker.value = document.documentElement.lang;
    picker.addEventListener("change", function () {
      var next = picker.value;
      document.documentElement.lang = next;
      document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
      try { localStorage.setItem("inpace-site-lang", next); } catch (e) {}
      translate(next);
    });
  }
  var ENGLISH = null;
  function translate(code) {
    var spans = [].slice.call(document.querySelectorAll("span.en"));
    if (!ENGLISH) ENGLISH = spans.map(function (s) { return s.innerHTML; });
    var note = document.querySelector("[data-not-translated]");
    if (note) note.hidden = true;
    if (code === "en" || code === "ar") {
      spans.forEach(function (s, i) { s.innerHTML = ENGLISH[i]; });
      return;
    }
    fetch("i18n/" + code + ".json").then(function (r) { return r.ok ? r.json() : null; }).then(function (t) {
      if (!t) { if (note) note.hidden = false; return; }
      var missed = 0;
      spans.forEach(function (s, i) {
        var key = ENGLISH[i].replace(/\s+/g, " ").trim();
        if (t[key]) s.innerHTML = t[key]; else missed++;
      });
      var title = document.title.replace(/\s+/g, " ").trim();
      if (t[title]) document.title = t[title];
      if (note && missed > spans.length / 2) note.hidden = false;
    }).catch(function () { if (note) note.hidden = false; });
  }
  window.inpaceTranslate = translate;
  translate(document.documentElement.lang);
})();
