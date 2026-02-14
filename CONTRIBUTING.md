# Contributing to Mapsurvey

Thank you for your interest in contributing! Here's how to get started.

## Getting Started

```bash
# Fork the repo, then clone your fork
git clone https://github.com/<your-fork>/mapsurvey.git
cd mapsurvey

# Start dev environment
./run_dev.sh --clean

# Run tests to make sure everything works
./run_tests.sh survey -v2
```

## Development Workflow

1. Create a branch from `master`: `git checkout -b feature/my-feature`
2. Make your changes
3. Run tests: `./run_tests.sh survey -v2`
4. Commit and push to your fork
5. Open a pull request

## Code Style

- Follow existing code patterns and conventions
- Use Django conventions for models, views, templates
- Write test docstrings in GIVEN/WHEN/THEN pattern
- Keep changes focused — one feature or fix per PR

## Testing

Tests require a running PostGIS container:

```bash
docker compose up -d db
./run_tests.sh survey -v2
```

Tests use a separate `test_mapsurvey` database created automatically by Django.

## Reporting Bugs

Open an issue using the **Bug report** template. Include:
- Steps to reproduce
- Expected vs actual behavior
- Screenshots if applicable
- Environment details (self-hosted or cloud, browser, OS)

## Feature Requests

Open an issue using the **Feature request** template. Describe the problem you're solving and your proposed approach.

## License

By contributing, you agree that your contributions will be licensed under the [AGPLv3](LICENSE).
