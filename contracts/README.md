# td_contracts

Canonical wire models, enums, and request/response specifications for the SafeSpace video threat detection system.

- Source of truth for API and Inference Worker.
- Pydantic v2 models with `extra="forbid"` on inbound payloads.
- Generates `openapi.json`, TypeScript definitions, and Dart models.
