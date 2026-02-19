# Paper Reference

**Codified Context as Infrastructure: A Layered Architecture for Agentic Software Engineering**

Aris Vasilopoulos

*Independent Researcher*

## Abstract

LLM-based agentic coding assistants lose coherence across sessions, forget project conventions, and repeat known mistakes. While recent studies characterize how developers configure agents through manifest files, little work examines how to *scale* such configuration for large, multi-agent projects. We present a three-layer *codified context infrastructure* developed during the construction of a 108,000-line C# distributed system: (1) a hot-memory constitution with conventions and orchestration protocols, (2) a cold-memory knowledge base of 34 specifications with integrated retrieval, and (3) 19 specialized domain-expert agents. The architecture was developed iteratively, with all code and knowledge artifacts AI-generated under human architectural direction. We report quantitative metrics on infrastructure growth and interaction patterns, present four observational case studies demonstrating how codified context propagates across sessions to prevent failures and enable architectural consistency, and offer practical guidelines. The framework is published as an open-source companion repository.

**Keywords:** AI-assisted software development, multi-agent systems, context infrastructure, software architecture, agentic software engineering, context engineering

## Links

- **arXiv:** *(forthcoming)*
- **Zenodo:** *(DOI forthcoming)*
- **Companion Repository:** [github.com/arisvas4/codified-context-infrastructure](https://github.com/arisvas4/codified-context-infrastructure)

## Citation

```bibtex
@article{vasilopoulos2026codified,
  title={Codified Context as Infrastructure: A Layered Architecture for Agentic Software Engineering},
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
| Prompt brevity | 52% of human prompts were <=20 words |
| Agent amplification | 2,801 prompts -> 1,197 agent invocations -> 16,522 agent turns |
| Development cost | ~$693 across 283 sessions (~$2.45/session) |
