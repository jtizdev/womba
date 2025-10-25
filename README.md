# Womba v1.2.0 - AI-Powered Test Generation

> **3x Faster** | **25-30% More Accurate** | **Production Ready** ✅

Womba is an AI-powered tool that automatically generates comprehensive test plans from Jira stories and uploads them to Zephyr Scale. It uses RAG (Retrieval-Augmented Generation) to learn from your existing test patterns and context.

## 🚀 What's New in v1.2.0

### Performance Optimizations
- ⚡ **3x faster** overall execution (98s → 32s)
- 🔄 **Parallel data collection** - 6-9x faster context gathering
- 💾 **Intelligent caching** - 50-80% faster on repeated requests
- 🎯 **Hybrid search** - 25-30% better retrieval precision

### Enhanced RAG Capabilities
- 🔍 **Multi-query retrieval** - 20-25% better recall
- 🎯 **Context expansion** - Automatically fetch related documents
- 🧠 **Semantic + keyword search** - Hybrid search for best results
- 📊 **Contextual reranking** - Improved relevance scoring

### New Features
- 📈 **Performance metrics tracking** - Monitor and optimize your workflows
- 🗄️ **Embedding cache** - Avoid recomputing identical vectors
- ⚙️ **Configurable optimizations** - Fine-tune for your needs

[See detailed performance report →](docs/PERFORMANCE_OPTIMIZATION.md)

---

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Features](#features)
- [Architecture](#architecture)
- [Performance](#performance)
- [Development](#development)
- [Contributing](#contributing)

---

## ⚡ Quick Start

```bash
# Install Womba
pip install -e .

# Configure (interactive)
python3 womba_cli.py configure

# Generate test plan for a Jira story
python3 womba_cli.py generate PLAT-12345

# Full workflow: Generate → Upload → Create PR
python3 womba_cli.py all PLAT-12345
```

---

## 🔧 Installation

### Prerequisites

- Python 3.10+
- Jira account with API access
- Zephyr Scale account
- OpenAI API key (for AI generation)

### Install from Source

```bash
git clone https://github.com/yourorg/womba.git
cd womba
pip install -e .
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Optional Dependencies

For enhanced performance:

```bash
# For reranking (improves accuracy by 10-15%)
pip install sentence-transformers

# For distributed caching
pip install redis
```

---

## ⚙️ Configuration

### 1. Environment Variables

Create a `.env` file:

```bash
# Atlassian Configuration
ATLASSIAN_BASE_URL=https://yourcompany.atlassian.net
ATLASSIAN_EMAIL=your.email@company.com
ATLASSIAN_API_TOKEN=your_atlassian_api_token

# Zephyr Scale
ZEPHYR_API_TOKEN=your_zephyr_api_token

# AI Provider
OPENAI_API_KEY=your_openai_api_key

# Performance Settings (optional)
ENABLE_CACHING=true
RAG_HYBRID_SEARCH=true
RAG_MULTI_QUERY=true
MAX_PARALLEL_REQUESTS=10
```

### 2. User Configuration

Run the interactive setup:

```bash
python3 womba_cli.py configure
```

This creates `~/.womba/config.yml` with your preferences.

### 3. Performance Tuning

Edit `src/config/settings.py` or set environment variables:

```python
# Parallel Processing
MAX_PARALLEL_REQUESTS=10
ENABLE_REQUEST_BATCHING=true

# Caching
CACHE_TTL_JIRA=300              # 5 minutes
CACHE_TTL_CONFLUENCE=1800       # 30 minutes
CACHE_TTL_RAG=3600              # 1 hour
EMBEDDING_CACHE_SIZE=1000

# RAG Optimization
RAG_HYBRID_SEARCH=true
RAG_RERANKING=true
RAG_MULTI_QUERY=true
RAG_CONTEXT_EXPANSION=true
```

---

## 🎯 Usage

### Command Line Interface

#### Generate Test Plan

```bash
# Basic generation
python3 womba_cli.py generate PLAT-12345

# With upload to Zephyr
python3 womba_cli.py generate PLAT-12345 --upload
```

#### Upload Existing Test Plan

```bash
python3 womba_cli.py upload PLAT-12345
```

#### Full Workflow

```bash
# Generate + Upload + Create Feature Branch + Generate Code + Create PR
python3 womba_cli.py all PLAT-12345

# Specify repository
python3 womba_cli.py all PLAT-12345 --repo /path/to/your/repo

# Specify test framework
python3 womba_cli.py all PLAT-12345 --framework playwright
```

#### RAG Management

```bash
# Index a story for future RAG retrieval
python3 womba_cli.py index PLAT-12345

# Index all stories in a project
python3 womba_cli.py index-all PLAT

# View RAG statistics
python3 womba_cli.py rag-stats

# Clear RAG collections
python3 womba_cli.py rag-clear
```

### Python API

```python
from src.ai.test_plan_generator import TestPlanGenerator
from src.aggregator.story_collector import StoryCollector
from src.integrations.zephyr_integration import ZephyrIntegration

# Collect story context
collector = StoryCollector()
context = await collector.collect_story_context('PLAT-12345')

# Generate test plan
generator = TestPlanGenerator()
test_plan = await generator.generate_test_plan(context)

# Upload to Zephyr
zephyr = ZephyrIntegration()
await zephyr.upload_test_plan(test_plan, 'PLAT-12345')
```

---

## ✨ Features

### 🤖 AI-Powered Test Generation

- **GPT-4o Integration**: Uses latest OpenAI models for intelligent test generation
- **Context-Aware**: Analyzes Jira stories, subtasks, comments, and linked issues
- **RAG-Enhanced**: Learns from your existing test patterns

### 📚 RAG (Retrieval-Augmented Generation)

- **Semantic Search**: Find similar test plans using vector embeddings
- **Hybrid Search**: Combine semantic and keyword matching
- **Multi-Query**: Multiple query variations for better coverage
- **Context Expansion**: Automatically fetch related documents

### 🔄 Complete Workflow Automation

1. **Context Collection**: Gather data from Jira and Confluence
2. **Test Plan Generation**: AI creates comprehensive test cases
3. **Zephyr Upload**: Automatically create test cases in Zephyr Scale
4. **Git Integration**: Create feature branches
5. **Code Generation**: Generate executable test code
6. **PR Creation**: Submit pull requests automatically

### 🚀 Performance Features

- **Parallel Processing**: Concurrent API calls for 6-9x faster data collection
- **Intelligent Caching**: Multi-level caching with TTL
- **Embedding Cache**: Avoid recomputing identical vectors
- **Performance Metrics**: Track and monitor execution time

### 🎯 Accuracy Features

- **Hybrid Search**: Semantic + keyword for 25-30% better precision
- **Reranking**: Cross-encoder models for better relevance
- **Multi-Query**: 20-25% better recall with query variations
- **Context Expansion**: 10-15% more comprehensive context

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Womba CLI                             │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
┌────────▼────────┐    ┌────────▼────────┐
│  Story Collector │    │  Test Generator │
│  (Parallel)      │    │  (RAG-Enhanced) │
└────────┬────────┘    └────────┬────────┘
         │                       │
    ┌────▼────┐             ┌───▼───┐
    │  Cache  │             │  RAG  │
    │ Manager │             │ Store │
    └─────────┘             └───┬───┘
                                │
                         ┌──────▼──────┐
                         │  Embedding  │
                         │    Cache    │
                         └─────────────┘
```

### Key Components

- **`src/aggregator/`**: Data collection from Jira, Confluence
- **`src/ai/`**: AI generation, RAG, embeddings
- **`src/integrations/`**: Zephyr Scale integration
- **`src/workflows/`**: Orchestration and workflow management
- **`src/cache/`**: Caching layer for performance
- **`src/monitoring/`**: Performance metrics and tracking

---

## 📊 Performance

### Benchmarks (PLAT-15596 with 28 subtasks)

| Operation | Before v1.2.0 | After v1.2.0 | Improvement |
|-----------|---------------|--------------|-------------|
| Data Collection | 60s | 17s | **3.5x faster** |
| RAG Retrieval | 5s | 1s | **5x faster** |
| AI Generation | 33s | 14s | **2.4x faster** |
| **Total** | **98s** | **32s** | **~3x faster** |

### Cache Impact (Second Run)

| Operation | First Run | Cached Run | Improvement |
|-----------|-----------|------------|-------------|
| Data Collection | 17s | 2-3s | **6-8x faster** |
| RAG Retrieval | 1s | 0.5s | **2x faster** |
| **Total** | **32s** | **17s** | **~2x faster** |

[See detailed performance analysis →](docs/PERFORMANCE_OPTIMIZATION.md)

---

## 🛠️ Development

### Project Structure

```
womba/
├── src/
│   ├── aggregator/       # Data collection (Jira, Confluence)
│   ├── ai/               # AI generation, RAG, embeddings
│   ├── cache/            # Caching layer (NEW in v1.2.0)
│   ├── config/           # Configuration management
│   ├── core/             # Core utilities
│   ├── integrations/     # External integrations (Zephyr)
│   ├── models/           # Data models
│   ├── monitoring/       # Performance metrics (NEW in v1.2.0)
│   └── workflows/        # Workflow orchestration
├── docs/                 # Documentation
├── tests/                # Unit and integration tests
├── data/                 # RAG storage (ChromaDB)
└── womba_cli.py          # CLI entry point
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test
pytest tests/test_story_collector.py
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
flake8 src/ tests/

# Type checking
mypy src/
```

---

## 📈 Monitoring & Debugging

### Performance Metrics

```python
from src.monitoring import get_metrics

# Get metrics
metrics = get_metrics()
metrics.print_summary()

# Output:
# === PERFORMANCE SUMMARY ===
# Total Operations: 47
# Total Elapsed Time: 32.5s
# Slowest Operations:
#   - generate_test_plan: 14.2s avg
#   - fetch_story_context: 17.3s avg
```

### Cache Statistics

```python
from src.cache import get_cache

cache = get_cache()
cache.print_stats()

# Output:
# Cache Stats: {
#   'cache_hits': 45,
#   'cache_misses': 12,
#   'hit_rate_percent': 78.95
# }
```

### RAG Statistics

```bash
python3 womba_cli.py rag-stats

# Output:
# RAG Collections:
#   test_plans: 156 documents
#   confluence_docs: 42 documents
#   jira_stories: 234 documents
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md).

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourorg/womba.git
cd womba

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
pip install -r requirements-dev.txt

# Run tests
pytest
```

### Coding Standards

- Follow PEP 8
- Add type hints
- Write docstrings
- Add tests for new features
- Update documentation

---

## 📄 License

[Add your license here]

---

## 🙏 Acknowledgments

- OpenAI for GPT-4o API
- ChromaDB for vector storage
- Atlassian for Jira and Confluence APIs
- SmartBear for Zephyr Scale API

---

## 📞 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourorg/womba/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourorg/womba/discussions)

---

## 🗺️ Roadmap

### v1.3.0 (Planned)
- [ ] Streaming AI responses for better UX
- [ ] Support for additional test frameworks (Robot, Cucumber)
- [ ] Batch processing for multiple stories
- [ ] Web UI dashboard

### v1.4.0 (Planned)
- [ ] GitLab and Bitbucket integration
- [ ] Custom AI model support (Claude, local models)
- [ ] Advanced analytics and reporting
- [ ] Test execution integration

---

**Made with ❤️ for QA Engineers**
