# CE01 — Artwork Runtime Fact Lock

Date: `2026-09-06`

Purpose: lock the selected first-party Artwork before Golden Journal Draft.

## Scope and controls

- Branch: `ce01-golden-journal`;
- canonical lookup: title `Tranh đường tàu phố cổ Hà Nội`, slug `tranh-duong-tau-pho-co-ha-noi`;
- source of truth: local WordPress/WooCommerce runtime;
- read-only verification only;
- Research API calls: `0`;
- no WordPress data writes;
- no code changes;
- no Golden Journal Draft written.

## Runtime evidence

Read at `2026-09-06T02:58:34Z`.

- WordPress Product ID: `416`;
- MOTGU Artwork ID: `motgu_artwork_000105`;
- MOTGU Physical Work ID: `motgu_work_000144`;
- product: `simple`, `publish`;
- title/slug: `Tranh đường tàu phố cổ Hà Nội` / `tranh-duong-tau-pho-co-ha-noi`;
- Artist: `414` / `Hoa Lê` / `hoa-le`;
- material: `Sơn dầu trên toan`, runtime taxonomy `mg_material`;
- year: `2025`;
- dimensions: `60 × 80 cm`;
- regular/effective price: `2,500,000 VND` / `2,500,000 VND`;
- manage stock / quantity / status: `true` / `1` / `instock`;
- MOTGU sale status: `available`;
- physical location: `on-view`;
- featured image: `417`, with runtime URL and alt recorded in the JSON artifact;
- gallery images: `418`, `419`, `420`, `421`, with runtime URLs and alts recorded in the JSON artifact;
- provenance: empty at runtime;
- certificate note: `Tác phẩm đi kèm chứng nhận do MOTGU cung cấp, ghi nhận thông tin tác phẩm và nguồn gốc quản lý.`;
- canonical permalink: `https://motgu.test/artwork/tranh-duong-tau-pho-co-ha-noi/`.

Artifact: `artifacts/runtime/ce01-artwork-anchor-20260906T025834Z.json`.

## Seed comparison

- price: `UNCHANGED` — seed `2,500,000 VND`, runtime `2,500,000 VND`;
- stock: `UNCHANGED` — seed `1`, runtime `1`;
- dimensions: `UNCHANGED` — seed `60 × 80 cm`, runtime `60 × 80 cm`;
- physical location: `UNCHANGED` — seed `on-view`, runtime `on-view`.

## Team rule for Draft

Static identity, material, year, dimensions, approved media, route and present certificate note may be used from this lock. Empty provenance must not be filled by inference. Price, stock, sale status and physical location are dynamic and must be re-read at Draft/publish time. Do not turn runtime commerce facts into durable claims without a fresh read.

Status: `RUNTIME VERIFIED / FACT LOCKED FOR T01.40`.
