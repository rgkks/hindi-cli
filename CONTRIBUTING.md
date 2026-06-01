# Contributing to hindi-cli

Thank you for considering contributing to hindi-cli! We welcome contributions of all kinds: bug fixes, new features, documentation improvements, and more.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/hindi-cli.git`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the project: `./hindi-cli`

## Development Guidelines

### Code Style
- Follow PEP 8 conventions
- Use type hints for all function signatures
- Keep functions small and focused (max ~50 lines where possible)
- Use meaningful variable names

### Commit Messages
- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Keep the first line under 72 characters
- Reference issues and pull requests where appropriate

### Pull Request Process
1. Create a new branch from `main` for your changes
2. Make your changes, keeping code style consistent
3. Update documentation if needed
4. Test your changes manually (run a few searches, play a video, etc.)
5. Submit a pull request with a clear description of the changes

### Adding a Provider
1. Create a new file in `providers/` or add to an existing one
2. Subclass `Provider` or `ChannelProvider` from `providers/base.py`
3. Implement the `search()` method (and `latest()` if applicable)
4. Register your provider with `ProviderRegistry.register()`

## Reporting Issues
- Use the provided issue templates
- Include your OS, Python version, and relevant logs
- Describe the expected vs actual behavior
- Include steps to reproduce

## Code of Conduct
Please note that this project follows a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold its standards.
