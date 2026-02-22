# Paper Reference

**Codified Context: Infrastructure for AI Agents in a Complex Codebase**

Aris Vasilopoulos

*Independent Researcher*

## Abstract

LLM-based agentic coding assistants lack persistent memory: they lose coherence across sessions, forget project conventions, and repeat known mistakes. Recent studies characterize how developers configure agents through manifest files, but an open challenge remains how to *scale* such configurations for large, multi-agent projects. This paper presents a three-component *codified context infrastructure* developed during construction of a 108,000-line C# distributed system: (1) a hot-memory constitution encoding conventions, retrieval hooks, and orchestration protocols; (2) 19 specialized domain-expert agents; and (3) a cold-memory knowledge base of 34 on-demand specification documents. Quantitative metrics on infrastructure growth and interaction patterns across 283 development sessions are reported alongside four observational case studies illustrating how codified context propagates across sessions to prevent failures and maintain consistency. The framework is published as an open-source companion repository.

**Keywords:** AI-assisted software development, multi-agent systems, context infrastructure, software architecture, agentic software engineering, context engineering

## Links

- **arXiv:** *(forthcoming)*
- **Zenodo:** *(DOI forthcoming)*
- **Companion Repository:** [github.com/arisvas4/codified-context-infrastructure](https://github.com/arisvas4/codified-context-infrastructure)

## Citation

```bibtex
@article{vasilopoulos2026codified,
  title={Codified Context: Infrastructure for AI Agents in a Complex Codebase},
  author={Vasilopoulos, Aris},
  journal={arXiv preprint},
  year={2026}
}
```

## Key Findings

| Metric | Value |
|--------|-------|
| Knowledge-to-code ratio | ~24% (1 line of documentation per 4 lines of code) |
| Context infrastructure | ~26,000 lines across constitution + 34 specs + 19 agents |
| Agent amplification | 2,801 prompts -> 1,197 agent invocations -> 16,522 agent turns |
