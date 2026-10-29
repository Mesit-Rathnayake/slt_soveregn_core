# Progress Note: AWS CloudFront, KnowledgeBase API & Conversational Chat Agent
**Date:** 29 October 2026  
**Author:** Mesith Rathnayake (Intern AI Engineer)  
**Status:** Completed AWS CloudFront Edge Gateway, SLTMobitel KB API Integration & Conversational Chat Agent (Ollama Removed)

## Summary of Completed Work
- **Pivoted from Costly IBM Sovereign Core Key to AWS Stack:** Replaced bare-metal IBM Sovereign Core dependencies with a serverless **AWS CloudFormation + Amazon CloudFront + AWS API Gateway + Amazon Bedrock** architecture (`infra-config-templates/aws-cloudformation-stack.yaml.example`).
- **Implemented Amazon CloudFront Edge Gateway (`cloudfront_gateway.py`):** Added edge TTL caching (`Hit from cloudfront` / `Miss from cloudfront`), South Asia (`MAA50-P1`) edge metadata, custom origin header injection (`x-auth-secret`), and security response headers (`Strict-Transport-Security`, `X-Frame-Options`, `X-Content-Type-Options`) in CloudFormation.
- **Integrated SLTMobitel KnowledgeBase HTTP API (`aws_kb_client.py`):** Connected to `POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve` with `x-auth-secret`, full KB document discovery (`discover_knowledge_base_contents()`), automatic trilingual CSV/JSON scraper cleanup (`clean_raw_kb_text()`), and English keyword reranking.
- **Removed Test-Only Ollama Dependency (`llm_gateway.py` & `rag_engine.py`):** Removed local Ollama dependencies and standardized on **AWS Bedrock (`boto3`)**, **Google Gemini**, and fast deterministic grounded synthesis.
- **Built Conversational Chat Agent with Guardrails (`orchestrator.py`, `guardrails_evals.py`, `app.py`):**
  - Redesigned UI into a clean, natural **Chat Agent** with starter prompts, follow-up chips, and honest out-of-scope abstention (*"I don't have enough knowledge in the current SLTMobitel KnowledgeBase to answer that specific question"*).
  - Added conversational greeting/capability handling, follow-up failure escalation (e.g., non-responsive router button troubleshooting), and prompt-injection/PII guardrails.
