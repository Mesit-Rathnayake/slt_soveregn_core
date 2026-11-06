# Progress Note: AWS CloudFront, KnowledgeBase API & Conversational Chat Assistant
**Date:** 2 November 2026  
**Author:** Mesith Rathnayake (Intern AI Engineer)  
**Status:** Deployed on Streamlit Community Cloud | AWS CloudFront + KnowledgeBase API + Bedrock Stack Complete

## Summary of Completed Work
- **Pivoted from Costly IBM Sovereign Core Key to AWS Stack:** Replaced bare-metal IBM Sovereign Core dependencies with a serverless **AWS CloudFormation + Amazon CloudFront + AWS API Gateway + Amazon Bedrock** architecture (`infra-config-templates/aws-cloudformation-stack.yaml.example`).
- **Implemented Amazon CloudFront Edge Gateway (`cloudfront_gateway.py`):** Added edge TTL caching (`Hit from cloudfront` / `Miss from cloudfront`), South Asia (`MAA50-P1`) edge metadata, origin custom header injection, and security response headers (`Strict-Transport-Security`, `X-Frame-Options`, `X-Content-Type-Options`) in CloudFormation.
- **Integrated SLTMobitel KnowledgeBase HTTP API (`aws_kb_client.py`):** Connected to `POST /prod/retrieve` with custom header authentication (`SLT_KB_AUTH_SECRET`), full KB document discovery (`discover_knowledge_base_contents()`), automatic trilingual CSV/JSON scraper cleanup (`clean_raw_kb_text()`), and English keyword reranking.
- **Removed Test-Only Ollama Dependency (`llm_gateway.py` & `rag_engine.py`):** Removed local Ollama dependencies and standardized on **AWS Bedrock (`boto3`)**, **Google Gemini**, and deterministic grounded synthesis.
- **Implemented Model Context Protocol (MCP) Server (`src/mcp/slt_mcp_server.py`):** Added an MCP `2024-11-05` JSON-RPC 2.0 server (`SLTMCPToolServer`) exposing 4 MCP tools (`slt_sanitize_pii`, `slt_query_cloud_kb`, `slt_diagnose_netops_incident`, `slt_cloudfront_cache_status`) and SOP resources (`slt://manuals/...`), wired directly into `SLTMobitelUnifiedAgent` (`orchestrator.py`).
- **Developed AWS Lambda Serverless Handler (`src/api/lambda_function.py`):**
  - Created standard `lambda_handler(event, context)` supporting API Gateway HTTP/REST APIs, Lambda Function URLs, and direct SDK invocations.
  - Implemented `/chat` REST endpoint, `/mcp` JSON-RPC 2.0 endpoint, `/health` diagnostics check, and CORS preflight (`OPTIONS`).
  - Added CloudFormation stack definitions (`SLTUnifiedAgentLambdaFunction`, API Gateway integrations and routes in `aws-cloudformation-stack.yaml.example`).
  - Authored comprehensive unit tests in `tests/test_lambda.py` (13/13 tests passing across `test_lambda.py` and `test_mvp.py`).
- **Implemented Voice Agent & Call Center IVR Adapter (`src/voice/voice_agent.py`):**
  - Added spoken script normalization (pronouncing USSD codes like `#1456#`, `#888#`, `#170#` and stripping markdown/citations for voice callers), W3C `<speak>` SSML generation, Amazon Polly Neural TTS integration, Amazon Connect `/voice` Lambda handling, and interactive browser speech synthesis (`🔊 Listen (Voice Agent)`) in the Streamlit UI.
- **Built Clean Conversational Chat UI & Cloud Deployment (`app.py`, `orchestrator.py`, `guardrails_evals.py`):**
  - Built a clean **Conversational Chat UI** with clickable starter question buttons, dynamic follow-up suggestions, natural greeting/smalltalk handling, follow-up hardware fault escalation, and honest out-of-scope abstention (*"I don't have enough knowledge in the current SLTMobitel KnowledgeBase to answer that specific question"*).
  - Secured all API endpoints, custom headers, and cloud credentials so they are never exposed in the UI or GitHub repository, loading them strictly from `.env` (local) or **Streamlit Cloud Secrets (`st.secrets`)**.
