/* البحث الصوتي — one voice layer for the whole platform.
 *
 * Injected into every `/tools/*` page by `_serve()`, in one place, so a page
 * cannot be built without it and cannot be forgotten later. `tests/test_voice.py`
 * asserts that every served page carries it.
 *
 * ── Why one floating mic instead of a mic per field ──────────────────────────
 * The obvious build is a small microphone inside every text box. Doing that
 * means wrapping each field in a positioned element, and the fields on this
 * platform live inside flex rows, grids and sticky bars with their own sizing
 * (`flex:1` on the hub's search, a `max-height` textarea in the chat composer).
 * Wrapping them re-flows layouts that already work, on pages this script has
 * never seen. So: one button, and it dictates into whatever field has focus —
 * or, if nothing does, into the page's own search box, which it focuses first.
 * Nothing on the page moves.
 *
 * ── Why the browser's recogniser and not a vendor ────────────────────────────
 * The Web Speech API costs no key, no credential and no per-minute bill, and it
 * keeps the platform's rule that the browser never holds a secret. On a browser
 * that lacks it this file renders nothing at all — a mic that does nothing when
 * pressed is worse than no mic.
 *
 * ── The part that makes it *search* and not just dictation ───────────────────
 * After writing into a field, an `input` event is dispatched. The hub filters as
 * you type, the ideas board filters as you type; without that event they would
 * sit there showing stale results beside text they never saw. Pressing the mic
 * on a `search` field also submits on stop, because saying something into a
 * search box and then having to reach for the keyboard defeats the point.
 */
(function () {
  "use strict";

  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  // No recogniser, or the page brought its own (the expert chat's composer mic).
  if (!SR || document.querySelector("[data-voice-local]")) return;

  var LANGS = [
    { code: "ar-EG", label: "عربي" },
    { code: "en-US", label: "EN" }
  ];
  var lang = LANGS[0].code;

  /* ---- which fields may be dictated into --------------------------------- */
  var TEXTY = "text search url email tel";

  function eligible(el) {
    if (!el || el.disabled || el.readOnly) return false;
    if (el.closest("[data-no-voice]")) return false;
    var tag = el.tagName;
    if (tag === "TEXTAREA") return true;
    if (tag !== "INPUT") return false;
    var t = (el.getAttribute("type") || "text").toLowerCase();
    // Never a password field: dictating a secret aloud is not a feature, and
    // the value would also land in the interim-results display.
    return TEXTY.indexOf(t) !== -1;
  }

  function visible(el) {
    var r = el.getBoundingClientRect();
    return r.width > 40 && r.height > 10;
  }

  /** The field to write into: whatever is focused, else the page's search box. */
  function target() {
    var a = document.activeElement;
    if (eligible(a) && visible(a)) return a;
    var all = [].slice.call(document.querySelectorAll("input, textarea"))
      .filter(function (el) { return eligible(el) && visible(el); });
    if (!all.length) return null;
    // A search field first — that is what "voice search" means on a page that
    // has one. Otherwise the first field a person would type in anyway.
    var search = all.filter(function (el) {
      return (el.getAttribute("type") || "") === "search" ||
             el.id === "q" || /بحث|دوّر|search/i.test(el.placeholder || "");
    });
    return search[0] || all[0];
  }

  /* ---- UI ---------------------------------------------------------------- */
  var css = document.createElement("style");
  css.textContent =
    "#sgv{position:fixed;inset-block-end:18px;inset-inline-start:18px;z-index:2147483000;" +
    "display:flex;align-items:center;gap:8px;font-family:'Segoe UI',system-ui,Tahoma,sans-serif;direction:rtl}" +
    "#sgv-btn{width:46px;height:46px;border-radius:50%;border:0;cursor:pointer;font-size:19px;" +
    "background:#0b121c;color:#7ee3e3;box-shadow:0 3px 14px rgba(0,0,0,.34);display:grid;place-items:center;" +
    "transition:transform .12s}" +
    "#sgv-btn:hover{transform:scale(1.06)}" +
    "#sgv-btn:focus-visible{outline:2px solid #2bc4c4;outline-offset:3px}" +
    "#sgv-btn.on{background:#e0483a;color:#fff;animation:sgvp 1.1s infinite}" +
    "@keyframes sgvp{50%{opacity:.55}}" +
    "#sgv-lang{background:#0b121c;color:#9fb4b4;border:0;border-radius:999px;padding:5px 11px;" +
    "font:inherit;font-size:11px;font-weight:700;cursor:pointer;box-shadow:0 2px 9px rgba(0,0,0,.28)}" +
    "#sgv-say{max-width:min(60vw,420px);background:#0b121c;color:#eaf2f2;border-radius:11px;" +
    "padding:7px 13px;font-size:12.5px;line-height:1.6;box-shadow:0 3px 14px rgba(0,0,0,.3);" +
    "white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
    "#sgv-say.hide{display:none}" +
    "#sgv-say b{color:#7ee3e3;font-weight:700}" +
    "@media print{#sgv{display:none}}";
  document.head.appendChild(css);

  var bar = document.createElement("div");
  bar.id = "sgv";
  bar.innerHTML =
    '<button id="sgv-btn" type="button" aria-label="بحث صوتي" ' +
    'title="بحث صوتي — Ctrl+M">🎙</button>' +
    '<button id="sgv-lang" type="button" title="لغة التعرّف">عربي</button>' +
    '<div id="sgv-say" class="hide" role="status" aria-live="polite"></div>';
  (document.body || document.documentElement).appendChild(bar);

  var btn = bar.querySelector("#sgv-btn");
  var langBtn = bar.querySelector("#sgv-lang");
  var say = bar.querySelector("#sgv-say");
  var hideTimer = null;

  function tell(html, sticky) {
    say.innerHTML = html;
    say.classList.remove("hide");
    clearTimeout(hideTimer);
    if (!sticky) hideTimer = setTimeout(function () { say.classList.add("hide"); }, 3800);
  }

  function fieldName(el) {
    if (!el) return "";
    var lab = el.getAttribute("aria-label") || el.placeholder || "";
    if (!lab && el.id) {
      var l = document.querySelector('label[for="' + el.id + '"]');
      if (l) lab = l.textContent;
    }
    lab = (lab || el.name || "الحقل").trim();
    return lab.length > 34 ? lab.slice(0, 34) + "…" : lab;
  }

  /* ---- recognition ------------------------------------------------------- */
  var rec = null, on = false, field = null, base = "";

  function write(text, done) {
    if (!field) return;
    var sep = base && !/\s$/.test(base) ? " " : "";
    field.value = base + sep + text;
    // The event is the whole point: the hub and the ideas board filter on
    // `input`, so without it they would show results for text they never saw.
    field.dispatchEvent(new Event("input", { bubbles: true }));
    if (done) field.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function stop() { if (rec) { try { rec.stop(); } catch (e) { /* already stopped */ } } }

  function start() {
    field = target();
    if (!field) { tell("مافيش حقل في الصفحة دي أكتب فيه."); return; }
    field.focus();
    base = field.value || "";

    rec = new SR();
    rec.lang = lang;
    rec.interimResults = true;
    rec.continuous = false;

    rec.onstart = function () {
      on = true;
      btn.classList.add("on");
      btn.setAttribute("aria-label", "بيسمع — دوس تاني للإيقاف");
      tell("بيسمع… بيكتب في <b>" + fieldName(field) + "</b>", true);
    };
    rec.onresult = function (e) {
      var s = "";
      for (var i = 0; i < e.results.length; i++) s += e.results[i][0].transcript;
      var final = e.results[e.results.length - 1].isFinal;
      write(s, final);
      tell((final ? "" : "… ") + s.slice(-90), !final);
    };
    rec.onerror = function (e) {
      // Name the failure. "الميكروفون مش شغال" for a denied permission sends
      // the user to fix the wrong thing.
      var why = {
        "not-allowed": "المتصفح رافض يدّي إذن الميكروفون — من قفل العنوان، اسمح بالمايك.",
        "service-not-allowed": "خدمة التعرّف مرفوضة في المتصفح ده.",
        "no-speech": "ماسمعتش حاجة.",
        "audio-capture": "مافيش ميكروفون متوصّل.",
        "network": "التعرّف محتاج نت والاتصال وقع."
      }[e.error] || ("الصوت وقف: " + e.error);
      tell(why);
    };
    rec.onend = function () {
      on = false;
      btn.classList.remove("on");
      btn.setAttribute("aria-label", "بحث صوتي");
      // Said into a search box, run the search — otherwise the person has to
      // reach for the keyboard, which is the thing they were avoiding.
      if (field && (field.getAttribute("type") || "") === "search") {
        field.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter", bubbles: true }));
        if (field.form) field.form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      }
    };

    try { rec.start(); } catch (e) { on = false; btn.classList.remove("on"); }
  }

  btn.addEventListener("click", function () { on ? stop() : start(); });

  langBtn.addEventListener("click", function () {
    var i = LANGS.findIndex(function (l) { return l.code === lang; });
    var next = LANGS[(i + 1) % LANGS.length];
    lang = next.code;
    langBtn.textContent = next.label;
    bar.dir = /^ar/.test(lang) ? "rtl" : "ltr";
    if (on) { stop(); setTimeout(start, 220); }
  });

  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "m" || e.key === "M")) {
      e.preventDefault();
      on ? stop() : start();
    } else if (e.key === "Escape" && on) {
      stop();
    }
  });

  // Announce itself once, quietly, so people know the platform can hear them.
  setTimeout(function () {
    tell("بحث صوتي شغّال — دوس المايك أو <b>Ctrl+M</b>");
  }, 900);
})();
