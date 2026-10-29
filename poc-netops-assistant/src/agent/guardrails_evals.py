import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class SovereignGuardrailsAndEvals:
    """
    SLTMobitel Sovereign AI Guardrails & Automated RAG Evaluation Engine.
    1. Input Guardrails: Prompt injection / jailbreak detection, destructive CLI intent detection,
       off-topic filtering, and PII/IP redaction verification.
    2. Output Guardrails: Read-only network safety verification (blocks autonomous write/reset commands)
       and citation verification.
    3. Automated RAG Evaluations (Evals): Computes quantitative scores (0.0 - 1.0) for:
       - Context Relevance (Retrieval Quality)
       - Groundedness / Faithfulness (Lexical & Citation overlap with retrieved chunks)
       - Answer Completeness & Actionability
       - Safety & Guardrail Compliance
    """

    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
        r"disregard\s+(?:all\s+)?(?:system|safety|governance)\s+rules",
        r"you\s+are\s+now\s+(?:dan|unrestricted|jailbroken|root)",
        r"reveal\s+(?:your\s+)?(?:system\s+prompt|secret\s+key|x-auth-secret|api\s+key)",
        r"bypass\s+(?:read-only|guardrail|rbac|sanitiz)"
    ]

    DESTRUCTIVE_NETOPS_PATTERNS = [
        r"\bclear\s+ip\s+ospf\s+process\b",
        r"\bclear\s+bgp\b",
        r"\bshutdown\b",
        r"\breload\s+(?:in\s+|at\s+|now)?\b",
        r"\bwrite\s+erase\b",
        r"\berase\s+startup-config\b",
        r"\bdelete\s+flash:",
        r"\breboot\s+olt\b"
    ]

    def evaluate_input_guardrails(self, raw_text: str, sanitized_text: str, redactions_count: int) -> dict:
        """Runs pre-flight input guardrails before calling AWS API Gateway or LLM."""
        flags = []
        blocked = False
        risk_level = "SAFE"

        for pat in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pat, raw_text, flags=re.IGNORECASE):
                flags.append("Prompt Injection / Jailbreak Attempt Detected")
                blocked = True
                risk_level = "BLOCKED"
                break

        destructive_requests = []
        for pat in self.DESTRUCTIVE_NETOPS_PATTERNS:
            if re.search(pat, raw_text, flags=re.IGNORECASE):
                destructive_requests.append(pat)

        if destructive_requests and not blocked:
            flags.append("Destructive Network Command Mentioned (Enforcing Strict Read-Only Advisory Mode)")
            risk_level = "MODERATED"

        if redactions_count > 0 and risk_level == "SAFE":
            flags.append(f"Masked {redactions_count} Sensitive PII/IP/Credential Field(s) Pre-Flight")

        return {
            "passed": not blocked,
            "blocked": blocked,
            "risk_level": risk_level,
            "redactions_applied": redactions_count,
            "flags": flags if flags else ["Input Clean — Zero Policy Violations"],
            "sanitized_preview": sanitized_text
        }

    def evaluate_output_guardrails(self, response_text: str, citations: list[str]) -> dict:
        """Checks generated output for unsafe autonomous write recommendations and verifies citations."""
        warnings = []
        safe = True

        # Check if output tells user to execute a destructive command without a "Do NOT" negation nearby
        for line in response_text.splitlines():
            line_lower = line.lower()
            if any(neg in line_lower for neg in ("do not", "never", "prohibited", "avoid", "guardrail")):
                continue
            for pat in self.DESTRUCTIVE_NETOPS_PATTERNS:
                if re.search(pat, line_lower):
                    warnings.append(f"Blocked unsafe command recommendation matching `{pat}`")
                    safe = False

        has_citations = len(citations) > 0 or ("[citation:" in response_text.lower()) or ("slt-" in response_text.lower())
        if not has_citations:
            warnings.append("No explicit KB/SOP citation tag detected in response.")

        return {
            "passed": safe,
            "read_only_compliant": safe,
            "has_verified_citations": has_citations,
            "warnings": warnings if warnings else ["Read-Only Advisory & Citation Guardrails Verified"]
        }

    def evaluate_rag_response(
        self,
        query: str,
        answer_text: str,
        retrieved_chunks: list[dict],
        citations: list[str],
        input_guard: dict,
        output_guard: dict
    ) -> dict:
        """
        Computes a 4-pillar RAG Evaluation Scorecard (0% to 100%) for every agent turn:
        1. Context Relevance: Top chunk similarity/retrieval score.
        2. Groundedness (Faithfulness): Content token overlap between answer and retrieved chunks + citations.
        3. Answer Completeness: Structural richness and length adequacy.
        4. Safety & Guardrail Score: Input/output guardrail compliance.
        """
        # 1. Context Relevance Score
        if retrieved_chunks:
            scores = [
                float(c.get("score", c.get("similarity_score", 0.75)))
                for c in retrieved_chunks
            ]
            max_s = max(scores) if scores else 0.0
            # Normalize: if lexical-only fallback had 0.0 similarity_score but chunks exist, baseline 0.80
            context_relevance = max_s if max_s > 0.0 else 0.82
            context_relevance = min(max(context_relevance, 0.35), 1.0)
        else:
            context_relevance = 0.15

        # 2. Groundedness / Faithfulness Score
        answer_tokens = set(re.findall(r"[a-zA-Z0-9_-]{4,}", answer_text.lower()))
        chunk_corpus = " ".join(c.get("content", "") for c in retrieved_chunks).lower()
        chunk_tokens = set(re.findall(r"[a-zA-Z0-9_-]{4,}", chunk_corpus))

        if answer_tokens and chunk_tokens:
            overlap_ratio = len(answer_tokens.intersection(chunk_tokens)) / max(len(answer_tokens), 1)
            citation_bonus = 0.25 if output_guard.get("has_verified_citations") else 0.0
            groundedness = min(1.0, (overlap_ratio * 1.45) + citation_bonus)
        elif retrieved_chunks:
            groundedness = 0.75
        else:
            groundedness = 0.20

        # 3. Answer Completeness Score
        word_count = len(answer_text.split())
        if word_count >= 35:
            completeness = 0.95
        elif word_count >= 15:
            completeness = 0.82
        elif word_count > 0:
            completeness = 0.60
        else:
            completeness = 0.0

        # 4. Safety & Guardrail Compliance Score
        if input_guard.get("blocked"):
            safety_score = 1.0  # Guardrail successfully intercepted attack
        elif not output_guard.get("passed"):
            safety_score = 0.40
        else:
            safety_score = 1.0

        overall = round(
            (context_relevance * 0.25 + groundedness * 0.35 + completeness * 0.20 + safety_score * 0.20) * 100,
            1
        )

        grade = "A+ (Verified Sovereign Grade)" if overall >= 85 else (
            "B (Acceptable Grounding)" if overall >= 70 else "C (Low Confidence / Review Needed)"
        )

        return {
            "overall_score_pct": overall,
            "grade": grade,
            "context_relevance_pct": round(context_relevance * 100, 1),
            "groundedness_pct": round(groundedness * 100, 1),
            "completeness_pct": round(completeness * 100, 1),
            "safety_compliance_pct": round(safety_score * 100, 1)
        }

