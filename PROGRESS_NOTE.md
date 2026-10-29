# Progress Note: Strategic Pivot to AWS Hybrid Cloud & SLTMobitel KnowledgeBase API
**Date:** 29 October 2026  
**Author:** Mesith Rathnayake (Intern AI Engineer)  
**Status:** Completed AWS Hybrid Cloud Re-Architecture (CloudFormation / CloudFront / API Gateway + Bedrock & Ollama)

## Summary of Completed Work
- **Pivoted from Costly IBM Sovereign Core Key:** Replaced bare-metal IBM Sovereign Core dependencies with a serverless **AWS CloudFormation + Amazon CloudFront + AWS API Gateway + Amazon Bedrock** hybrid architecture (`infra-config-templates/aws-cloudformation-stack.yaml.example`).
- **Integrated SLTMobitel KnowledgeBase Access HTTP API:** Built `SLTMobitelCloudKBClient` (`src/retrieval/aws_kb_client.py`) connecting to `POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve` with `x-auth-secret` header authentication (`d215af7a649fe83938414634e789b39cb3ed4ad0a1077c2d`) and `top_k` (1–5) chunk normalization.
- **Added AWS Bedrock Multi-Model Support:** Extended `SovereignLLMGateway` (`src/agent/llm_gateway.py`) with `generate_with_bedrock()` (`boto3` Converse/InvokeModel API for Claude 3 Haiku/Sonnet, Amazon Titan, and Meta Llama 3) alongside Local Ollama (`granite3.1-dense:2b`) and Google Gemini.
- **Upgraded Streamlit Workbench to 4 Tabs:** Added **Tab 1: SLTMobitel KnowledgeBase Assistant (AWS API)** alongside **Tab 2: NetOps Incident Triage & Handover**, **Tab 3: Local NetOps SOP Vector Search**, and **Tab 4: Governance & Audit Trail (RBAC)**.
- **Updated Documentation & Automated Tests:** Updated Phase 1–3 architecture docs (`docs/`) and expanded `tests/test_mvp.py` to test AWS KB API request/response handling, Bedrock/Ollama gateway routing, and PII sanitization.
