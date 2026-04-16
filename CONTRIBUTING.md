# Contributing to PatentBench

Thank you for your interest in contributing to PatentBench. This document provides guidelines for contributing test cases, evaluation rubrics, model adapters, and improvements to the benchmark framework.

## How to Contribute

### Contributing Test Cases

Test cases are the foundation of PatentBench. We welcome contributions of high-quality, expert-curated test cases across all five domains.

#### Requirements for Test Cases

1. **Real provenance**: Test cases must derive from actual USPTO proceedings. Include the application number and Office Action date.
2. **Expert validation**: Test cases must be reviewed by a licensed patent attorney or registered patent agent.
3. **Complete metadata**: Include all required fields (see `data/README.md` for the schema).
4. **Poison pills**: Include at least one fabricated MPEP citation and one fabricated case law citation for anti-hallucination testing.
5. **Reference answer**: Provide a comprehensive reference answer that a Senior Associate or above would produce.

#### Process

1. Fork the repository
2. Create test cases in JSONL format in the appropriate `data/` subdirectory
3. Validate your test cases: `python -m patentbench.data_loader --validate your_file.jsonl`
4. Submit a pull request with:
   - The test case file
   - A description of the technology area and difficulty tier
   - Confirmation of expert review

### Contributing Evaluation Rubrics

Rubrics define the scoring criteria for LLM-as-Judge evaluation.

#### Requirements

1. Follow the rubric JSON schema in `data/rubrics/README.md`
2. Include detailed criteria for each score level (1-5)
3. Weight dimensions appropriately for the task type
4. Validate against at least 10 sample outputs

### Contributing Model Adapters

Model adapters connect new AI systems to the benchmark framework. For a complete guide — including how to integrate commercial tools (SOLV, PatSnap, etc.), CSV round-trip for no-API systems, and browser automation — see **[INTEGRATION.md](INTEGRATION.md)**.

#### Requirements

1. Extend `BaseModelAdapter` from `patentbench/models/base.py`
2. Implement `generate()` and `is_available()` methods
3. Handle authentication via environment variables or constructor parameters
4. Include error handling and timeout logic
5. Add the adapter to `patentbench/models/__init__.py`
6. Add tests in `tests/`

#### Example

```python
from patentbench.models.base import BaseModelAdapter, GenerationConfig

class MyModelAdapter(BaseModelAdapter):
    def __init__(self, model_name: str = "my-model", api_key: str | None = None):
        super().__init__(model_name=model_name)
        self.api_key = api_key or os.environ.get("MY_API_KEY", "")

    def generate(self, prompt: str, config: GenerationConfig | None = None) -> str:
        # Your API call here
        ...

    def is_available(self) -> bool:
        return bool(self.api_key)
```

## Development Setup

```bash
git clone https://github.com/rhahn28/patentbench.git
cd patentbench
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest -v
pytest --cov=patentbench
```

## Code Style

- Python 3.10+ with type hints on all function signatures
- Use `ruff` for linting: `ruff check .`
- Use `mypy` for type checking: `mypy patentbench/`
- Dataclasses and enums over plain dicts/strings where appropriate
- Docstrings on all public classes and functions

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass and linting is clean
4. Update documentation if applicable
5. Submit PR with a clear description of changes

## Reporting Issues

Please use GitHub Issues for:
- Bug reports (include reproduction steps)
- Feature requests
- Test case quality concerns
- Documentation improvements

## Code of Conduct

Be respectful, constructive, and collaborative. We are building critical infrastructure for the patent profession and AI research community.

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.

Copyright 2026 Salt Holdings LLC.
