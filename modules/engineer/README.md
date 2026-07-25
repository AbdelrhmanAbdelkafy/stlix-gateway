# Module — Engineer's Smart Assistant (مساعد المهندس)

Preliminary engineering for Hard Steel's sanitary stainless fabrication (SS 304 /
316 / 316L). Arabic, RTL, offline-capable.

Served at **`/tools/engineer`**.

## What it does

| Tab | |
|---|---|
| 🛢️ خزانات وأوعية | tank/vessel volume, ASME-style shell thickness (S · E · CA), head geometry, plate weight, BOM |
| 🔩 مواسير صحية | sanitary piping sizing off a tube table |
| ⚙️ ليزر وتشكيل | laser cutting & forming |
| 🌡️ مبادلات وخامات | heat exchangers and material properties |
| 🧪 محاكاة وحصر | simulation and BOQ |

A project (name, job no., prepared by, rev.) is saved to `localStorage` and can be
exported as a file. Nothing leaves the browser.

## Status: standalone, not yet gateway-wired

The page holds no credentials and makes no network calls — which is why it can be
served as-is. It is a **calculator**, not yet a connected module: its BOM is
produced and copied by hand rather than checked against, or written to, Nama.

That gap is recorded on the board as the `needs` of **PD2**, and the pieces to
close it already exist:

- the BOM's item names could resolve against the live Nama item master through
  `/api/v1/nama/lists/InvItem`, and be duplicate-checked with
  `/api/v1/nama/invitem/exists` — the same path `name-builder` already uses;
- creating the items for real is a **write**, so it belongs behind the Layer 5
  audited workflow, not a direct call.

Until then it is honest to treat this as an offline tool that happens to live
inside the platform.

## Convention

Like every module here it is served through `app/routers/tools.py::_serve`, which
substitutes `__GATEWAY_API_KEY__`. The placeholder is absent today; add it when
the module starts calling the gateway, and the key arrives server-side rather
than being embedded in the file.
