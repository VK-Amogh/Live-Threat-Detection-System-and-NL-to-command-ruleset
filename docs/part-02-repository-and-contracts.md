# Part 2 — Repository and Contracts

Status: Implemented · Depends on: Part 1, `decision-log.md` · Feeds: Parts 3–10

## 1. Objective
Freeze repository tree, service boundaries, HTTP & WebSocket contracts, and error conventions.

## 2. Implemented Boundaries
- `contracts/src/td_contracts`: Single source of wire models and enums with `extra="forbid"` on inbound payloads.
- `contracts/generated/`: OpenAPI spec (`openapi.json`) and JSON schemas.
- `apps/dashboard/src/api/generated/schema.ts`: TypeScript types generated via `openapi-typescript`.
- `apps/mobile/lib/data/generated/models.dart`: Dart client models.
- `contracts/examples/`: 12 golden JSON fixtures validated against pytest contract suite.
