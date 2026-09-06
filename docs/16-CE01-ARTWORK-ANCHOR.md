# CE01 — GOLDEN JOURNAL — ARTWORK ANCHOR

Status: **CANDIDATE SELECTED / RUNTIME VERIFICATION REQUIRED**

Phase: `CE01 / PR-E — Walking Skeleton`

Purpose:

Use one real MOTGU Artwork as the first-party anchor for the Golden Journal before Draft. This prevents the article from becoming a generic art-price explainer.

## Selected Artwork candidate

- title: `Tranh đường tàu phố cổ Hà Nội`
- slug: `tranh-duong-tau-pho-co-ha-noi`
- artist: `Hoa Lê`
- artist slug: `hoa-le`
- year in Golden Content importer: `2025`
- material in Golden Content importer: `Sơn dầu trên toan`
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

## Canonical ownership rule

Source: `thiendzung/MotguOS/docs/01-product-data-contract.md`.

- Artwork is a WooCommerce Product.
- WooCommerce owns price, stock, shipping and other commerce state.
- Current price/stock must not be copied into editorial memory.
- Product title/slug/content/media and public Artwork facts remain in WordPress/WooCommerce/ACF according to the approved ownership table.
- Public Artwork URL should use `/artwork/{slug}/`.

## Required runtime verification before T01.40 Draft

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

`ARTWORK_ANCHOR_SELECTED / RUNTIME FACT LOCK PENDING`

T01.40 Draft remains blocked until the runtime verification above is complete.
