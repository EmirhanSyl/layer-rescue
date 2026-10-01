# Releasing

Releases are built by GitHub Actions from a version tag. `main` is protected, so the version bump goes through a pull request.

1. On a branch, update `src/layer_rescue/_version.py`.
2. In `CHANGELOG.md`, rename **Unreleased** to `## [X.Y.Z] - YYYY-MM-DD`, add a new empty **Unreleased** section and update the links at the bottom.
3. Open a pull request, wait for CI and merge it.
4. Tag the merged commit and push the tag:

   ```bash
   git checkout main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

5. The [Release workflow](../.github/workflows/release.yml) checks that the tag matches the version, runs the tests on Windows, builds the Windows installer, the wheel and the sdist, and publishes a GitHub Release with those files, `SHA256SUMS.txt` and the changelog section as notes. When that is done, a second job runs the tests on an Apple Silicon Mac, builds `LayerRescue.app` and adds `LayerRescue-X.Y.Z-macos-arm64.zip` to the same release. (`SHA256SUMS.txt` is written before the macOS job, so it doesn't list the zip.)

If the workflow fails, fix the problem, delete the tag (`git push --delete origin vX.Y.Z` and `git tag -d vX.Y.Z`) and tag again.

## Building locally

Build output goes to `dist/` and `release/`, both ignored by git.

**Windows** (Python 3.10+, [Inno Setup 6](https://jrsoftware.org/isinfo.php)):

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

**macOS** (Python 3.10+ with Tkinter, Xcode command line tools):

```bash
python3 -m pip install pyinstaller
bash packaging/macos/build.sh
```

The macOS app is ad-hoc signed only. Developer ID signing and notarization are not set up yet; they need a `Developer ID Application` certificate and an app-specific password or API key stored as repository secrets.

## PyPI (optional)

1. On PyPI, add a trusted publisher: owner `EmirhanSyl`, repository `layer-rescue`, workflow `release.yml`, environment `pypi`.
2. In the GitHub repository settings, create an environment named `pypi` and a repository variable `PUBLISH_TO_PYPI` with the value `true`.

The next tag will also upload the wheel and sdist to PyPI.
