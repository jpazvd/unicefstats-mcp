# Related Work: Tool-Augmented LLM Evaluation, Hallucination, and RAG Metrics

This bibliography covers papers relevant to benchmarking MCP-augmented LLM systems for data extraction, particularly the finding that MCP improves EQA 6.7x (0.147 to 0.990) but increases T2 hallucination from 11% to 37%.

## Tool Hallucination

1. **Yin et al. (2025)** "The Reasoning Trap: How Enhancing LLM Reasoning Amplifies Tool Hallucination." arXiv:2510.22977. Establishes causal relationship: enhanced reasoning proportionally increases tool hallucination. Directly parallels our MCP finding.

2. **Fatahi Bayat et al. (2025)** "From Proof to Program: Characterizing Tool-Induced Reasoning Hallucinations in LLMs." arXiv:2511.10899. Tool access creates over-reliance and fabricated reasoning chains. Analogous to our T2 pattern.

3. **Xu et al. (2025)** "Reducing Tool Hallucination via Reliability Alignment." arXiv:2412.04141. Proposes reliability alignment for tool selection/usage hallucination. Relevant to T2 mitigation.

## MCP Evaluation

4. **Song et al. (2025)** "Help or Hurdle? Rethinking MCP-Augmented LLMs." arXiv:2508.12566. MCPGauge: first MCP evaluation framework. Validates that MCP is not uniformly beneficial. Most directly relevant paper.

5. **Wang et al. (2025)** "MCP-Bench: Benchmarking Tool-Using LLM Agents with Complex Real-World Tasks via MCP Servers." arXiv:2508.20453. 28 live MCP servers, 250 tools, 20 LLMs. Methodological precedent.

6. **Zong et al. (2025)** "MCP-SafetyBench." arXiv:2512.15163. 20 MCP attack types. Safety failures as a hallucination mechanism.

7. **(2026)** "MCP Tool Descriptions Are Smelly!" arXiv:2602.14878. 97.1% of MCP tools have description quality issues. Confounding variable in our benchmark.

## Anti-Hallucination Techniques

8. **(2026)** "Tool Receipts, Not Zero-Knowledge Proofs." arXiv:2603.10060. NabaOS: HMAC-signed tool execution receipts. Detects 94.2% of fabricated tool references.

9. **Lin et al. (2025)** "LLM-based Agents Suffer from Hallucinations: A Survey of Taxonomy, Methods, and Directions." arXiv:2509.18970. Taxonomy: our T2 maps to Execution + Communication hallucination.

10. **Zhuo et al. (2025)** "Identifying and Mitigating API Misuse in LLMs." arXiv:2503.22821. Hallucination is the most frequent API misuse pattern.

## RAG Evaluation Metrics

11. **Es et al. (2024)** "RAGAs: Automated Evaluation of RAG." EACL 2024. Component-wise evaluation (faithfulness, relevancy, precision, recall). Our EQA parallels this decomposition.

12. **(2024)** "Assessing Information Extraction Quality with MINEA." arXiv:2404.04068. Closest methodological parallel to EQA metric.

13. **Yu et al. (2024)** "Evaluation of Retrieval-Augmented Generation: A Survey." arXiv:2405.07437. Positions EQA within the broader RAG evaluation landscape.

14. **(2025)** "Hallucination Mitigation in RAG Systems: A Review." Mathematics 13(5):856. Span-level verification applicable to T2 reduction.

15. **(2025)** "Benchmarking Table Extraction: Multimodal LLMs vs Traditional OCR." xLLM 2025. Claude-3.5-sonnet at 96.2% table extraction accuracy.

## Mapping to Our Findings

| Our Finding | Supporting Literature |
|---|---|
| MCP improves EQA 6.7x (0.147→0.990) | Song et al. (MCPGauge) — MCP can help but not uniformly |
| T2 hallucination rises 11% to 37% with tools | Yin et al. (Reasoning Trap) — capability gains increase hallucination |
| Tool errors trigger fabrication | Fatahi Bayat et al. — tool access creates over-reliance |
| EQA = ER x YA x VA metric | Es et al. (RAGAS) — component-wise evaluation |
| Anti-hallucination needed | NabaOS tool receipts; Xu et al. reliability alignment |
