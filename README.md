# Womba 🧪

AI-powered test generation from Jira stories

## What it Does

Womba automatically generates comprehensive test cases by:
1. Collecting context from Jira (story, subtasks, linked issues, comments)
2. Retrieving related Confluence documentation
## Quick Start

### Installation

```bash
pip install -r requirements-minimal.txt
```

### Configuration

Run interactive setup:

```bash
python3 womba_cli.py configure
```

You'll need:
- Atlassian URL, email, and API token
- (Optional) Automation repository path

### Usage

**Generate test plan only:**
```bash
python3 womba_cli.py generate PLAT-12345
```

**Generate and upload to Zephyr:**
```bash
python3 womba_cli.py generate PLAT-12345 --upload
```

**Full workflow (generate + upload + create branch + PR):**
```bash
python3 womba_cli.py all PLAT-12345
```

## Features

- **Smart Complexity Scoring**: Automatically determines test count based on story complexity
  - Simple stories (score < 5): 4-6 tests
  - Medium stories (5-12): 6-10 tests  
  - Complex stories (12+): 10-15 tests

- **Deep Context Analysis**: Uses all available context sources:
  - Subtasks (implementation details)
  - Linked issues (integration points)
  - Confluence docs (business requirements)
  - Comments (edge cases)

- **Clean Output**: Test titles are clear and specific (no generic prefixes)

## Configuration Files

- `~/.womba/config.yml` - Your credentials and preferences
- `.env` (optional) - Environment-specific overrides

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed setup instructions
- [API Reference](docs/API.md) - API server documentation
- [Automation](docs/AUTOMATION.md) - Code generation setup

## Requirements

- Python 3.9+
- Atlassian account with Jira and Confluence access

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT

## Maintainers

Maintained by [jtizdev](https://github.com/jtizdev)
