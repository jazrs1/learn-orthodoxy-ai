"""Corpus ingestion (Phase 5, INGEST_PLAN.md).

One package for every source: extraction (`extract_en`, `extract_ar`, `web`), cleaning and
normalisation (`textnorm`), the exact v1 rebuild (`legacy`), embedding (`embed`) and the CLI
(`python -m ingestion ...`). PyMuPDF (AGPL) is imported only here, never by the API (ING-001).
"""
