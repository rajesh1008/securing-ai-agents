# CI workflow (to be enabled)

`tests.yml` is a GitHub Actions workflow that runs the test suite on Python 3.11 and 3.12 with no API key, so nothing calls a model. To enable it, move it to `.github/workflows/tests.yml`. (It was kept here because the tool that published this repository was not allowed to create workflow files.)
