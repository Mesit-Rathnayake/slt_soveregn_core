---
name: slt-kb-anti-hallucination
description: >-
  Audits and verifies the SLTMobitel Sovereign AI Platform for KnowledgeBase
  grounding, anti-hallucination compliance, multi-turn session topic isolation,
  and API security guardrails. Use this skill whenever modifying retrieval,
  fallback synthesis, orchestrator routing, or LLM prompts.
---

# SLTMobitel KnowledgeBase Grounding & Anti-Hallucination Skill

This skill enforces strict grounding against the verified SLTMobitel AWS KnowledgeBase catalog and SOPs, ensuring zero hallucinated facts, zero substring routing bugs, and clean multi-turn session transitions.

## Reference Catalog

All customer-facing facts, prices, USSD codes, LED indicators, and troubleshooting steps must match the verified KnowledgeBase catalog:
* [SLTMobitel Full KnowledgeBase Catalog](../../../docs/04-knowledgebase-full-catalog.md)

## Anti-Hallucination & Flow Checklist

1. **Strict Grounding Gate (`grounded(*anchors)`):**
   Every deterministic synthesis rule in [`rag_engine.py`](../../../poc-netops-assistant/src/retrieval/rag_engine.py) must check both `asks(*terms)` on the current turn and `grounded(*anchors)` on the retrieved chunks so a template never fires on unrelated chunks.
2. **No Invented Hardware Details:**
   Customer router troubleshooting must only reference LEDs and steps documented in the SLTMobitel KnowledgeBase (`WLAN`, `GPON` solid green, `Phone` LED, MySLT App quota check, Wi-Fi password change, cable check, and `1212` / `1717` fault reporting).
3. **Word-Boundary Matching (`_has_any_term`):**
   Never use raw substring `in` checks for short tokens (`led`, `sim`, `peo`, `idd`, `vas`, `low`), which falsely match inside words like `knowledge`, `simple`, `people`, `middle`, or `follow`.
4. **Out-of-Domain Trivia Abstention (`OUT_OF_DOMAIN_PATTERNS`):**
   Queries sharing ambiguous English words with KB chunks (e.g., *"speed of light"*, *"price of gold"*, *"python code"*) must abstain (`has_enough_knowledge = False`).
5. **Credential & SSRF Protection:**
   * `SLTMobitelCloudKBClient.retrieve()` must never forward the configured `x-auth-secret` to an untrusted `endpoint_override` host.
   * `lambda_handler()` must never accept credential or endpoint overrides from untrusted HTTP request bodies.

## Verification Procedure

1. Run the automated anti-hallucination and flow audit script:
   ```powershell
   python .agents/skills/slt-kb-anti-hallucination/scripts/verify_grounding.py
   ```
   See [verify_grounding.py](./scripts/verify_grounding.py).
2. Run the full unit test suite:
   ```powershell
   python -m pytest poc-netops-assistant/tests/ -v
   ```

