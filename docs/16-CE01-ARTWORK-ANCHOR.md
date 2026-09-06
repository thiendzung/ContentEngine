# CE01 — GOLDEN JOURNAL — ARTWORK ANCHOR

Status: **RUNTIME VERIFIED / FACT LOCKED FOR T01.40**

Phase: `CE01 / PR-E — Walking Skeleton`

Purpose:

Use one real MOTGU Artwork as the first-party anchor for the Golden Journal before Draft. This prevents the article from becoming a generic art-price explainer.

## Selected Artwork candidate

- title: `Tranh đường tàu phố cổ Hà Nội`
- slug: `tranh-duong-tau-pho-co-ha-noi`
- artist: `Hoa Lê`
- artist slug: `hoa-le`
- year: `2025`
- material: `Sơn dầu trên toan`
- canonical public route pattern: `/artwork/{product-slug}/`

## Why this Artwork

It is the canonical Golden Content Artwork already used to validate the MOTGU product/content model. It has:

- a real Artist relation;
- a known physical medium;
- physical dimensions in WooCommerce seed data;
- a featured Artwork image plus detail images;
- a direct relation to an existing MOTGU Journal in Golden Content;
- a Hanoi subject that fits the real visitor context without requiring invented artist intent.

## Repo-supported static/source facts

Source: `thiendzung/MotguOS/scripts/p04-golden-content.php` on `main`.

The importer defines:

- product title: `Tranh đường tàu phố cổ Hà Nội`;
- slug: `tranh-duong-tau-pho-co-ha-noi`;
- artist relation: Hoa Lê;
- year: 2025;
- material taxonomy: `Sơn dầu trên toan`;
- WooCommerce dimensions seed: `60 × 80 cm`;
- work-location seed: `on-view`;
- featured image plus train/street/texture/side detail images.

The importer also contains seed commerce state:

- regular price: `2,500,000 VND`;
- stock quantity: `1`;
- stock status: `instock`;
- post/product status: `publish`.

**These commerce values are historical seed/runtime setup facts only. They are NOT approved for the Draft until re-read from the current canonical WooCommerce runtime.**

## Runtime fact lock

Read at: `2026-09-06T02:58:34Z` from the local WordPress/WooCommerce runtime.

Artifact: `artifacts/runtime/ce01-artwork-anchor-20260906T025834Z.json`

Runtime identity and static facts:

- WordPress Product ID: `416`;
- MOTGU Artwork ID: `motgu_artwork_000105`;
- MOTGU Physical Work ID: `motgu_work_000144`;
- product type/status: `simple` / `publish`;
- title/slug: `Tranh đường tàu phố cổ Hà Nội` / `tranh-duong-tau-pho-co-ha-noi`;
- Artist: WordPress ID `414`, `Hoa Lê`, slug `hoa-le`;
- material taxonomy: `Sơn dầu trên toan` (`mg_material`);
- year: `2025`;
- dimensions: `60 × 80 cm`;
- featured image: attachment `417` plus its runtime URL and alt;
- gallery: attachments `418`, `419`, `420`, `421` plus runtime URLs and alts;
- provenance field: empty at runtime;
- certificate note: present at runtime;
- canonical permalink: `https://motgu.test/artwork/tranh-duong-tau-pho-co-ha-noi/`.

Runtime dynamic facts:

- regular price: `2,500,000 VND`;
- effective price: `2,500,000 VND`;
- manage stock: `true`;
- stock quantity: `1`;
- stock status: `instock`;
- MOTGU sale status: `available`;
- physical location: `on-view`.

The four dynamic commerce/location fields were compared with the historical importer seed and are all `UNCHANGED`. Price, stock, availability and physical location remain dynamic and must be re-read at Draft/publish time; they must not become durable editorial claims.

## Canonical ownership rule

Source: `thiendzung/MotguOS/docs/01-product-data-contract.md`.

- Artwork is a WooCommerce Product.
- WooCommerce owns price, stock, shipping and other commerce state.
- Current price/stock must not be copied into editorial memory.
- Product title/slug/content/media and public Artwork facts remain in WordPress/WooCommerce/ACF according to the approved ownership table.
- Public Artwork URL should use `/artwork/{slug}/`.

## Runtime verification evidence

Read the current product by exact slug:

`tranh-duong-tau-pho-co-ha-noi`

Verify and return:

1. WordPress product ID;
2. MOTGU Artwork ID if present;
3. MOTGU Physical Work ID if present;
4. product status;
5. title and slug;
6. Artist relation + Artist title/slug;
7. Material taxonomy;
8. year;
9. dimensions + unit;
10. current regular/current price;
11. manage_stock;
12. stock quantity;
13. stock status;
14. projected sale status if available;
15. physical location if available;
16. featured image ID + URL + alt;
17. gallery image IDs/URLs/alts;
18. provenance field;
19. certificate note field;
20. public Artwork permalink/route.

## Fact-use policy for Draft

### Stable enough after runtime verification

May be used if current runtime confirms:

- title;
- Artist;
- material;
- year;
- dimensions;
- approved images;
- public route;
- documented provenance/certificate facts if present.

### Dynamic

Must be treated as live facts and either:

- read again at Draft/publish time; or
- omitted from durable prose when not necessary.

Dynamic facts:

- price;
- stock;
- availability/sale status;
- physical location when operationally changeable;
- shipping quote/rules.

## Writer boundary

This Artwork is used to demonstrate **how a buyer reads verified facts around a work**.

It is NOT evidence for:

- why MOTGU priced this work at a specific amount;
- a universal art-pricing formula;
- investment/resale claims;
- invented artist intention;
- a claim that this Artwork is better because of price.

## Gate

Current:

`RUNTIME VERIFIED / FACT LOCKED FOR T01.40`

The verified static facts and approved images may be used in the Draft. Empty provenance must remain empty unless a later approved source supplies it. Price, stock, availability and physical location are live commerce/operational facts and require a fresh runtime read at Draft/publish time.
