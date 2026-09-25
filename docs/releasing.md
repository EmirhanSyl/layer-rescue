# Releasing

Releases are built by GitHub Actions from a version tag.

1. Update `src/layer_rescue/_version.py`.
2. In `CHANGELOG.md`, rename **Unreleased** to `## [X.Y.Z] - YYYY-MM-DD`, add a new empty **Unreleased** section and update the links at the bottom.
3. Commit, then tag and push:

   ```bash
   git commit -am "Release X.Y.Z"
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```

4. The [Release workflow](../.github/workflows/release.yml) checks that the tag matches the version, runs the tests, builds the wheel, sdist and Windows installer, and publishes a GitHub Release with those files, `SHA256SUMS.txt` and the changelog section as notes.

If the workflow fails, fix the problem, delete the tag (`git push --delete origin vX.Y.Z` and `git tag -d vX.Y.Z`) and tag again.

## Building the installer locally

Requires Windows, Python 3.10+, PyInstaller and [Inno Setup 6](https://jrsoftware.org/isinfo.php).

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

The installer is written to `release\`, which is ignored by git.

## PyPI (optional)

1. On PyPI, add a trusted publisher: owner `EmirhanSyl`, repository `layer-rescue`, workflow `release.yml`, environment `pypi`.
2. In the GitHub repository settings, create an environment named `pypi` and a repository variable `PUBLISH_TO_PYPI` with the value `true`.

The next tag will also upload the wheel and sdist to PyPI.
