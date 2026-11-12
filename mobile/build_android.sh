#!/usr/bin/env bash
# Build the inPace Android app (APK). Used by GitHub Actions, and works on your own computer too
# (needs Flutter, Java 17 and the Android SDK; run: bash mobile/build_android.sh).
set -euo pipefail
cd "$(dirname "$0")"

export SERIOUS_PYTHON_VERSION="${SERIOUS_PYTHON_VERSION:-3.12}"
export SERIOUS_PYTHON_SITE_PACKAGES="$PWD/build/site-packages"
export SERIOUS_PYTHON_APP="$PWD/build/app"

echo "== 1. Make the Android project (only adds what's missing)"
flutter create --org org.inpace --project-name inpace_mobile --platforms=android .
python3 tools/prepare_android.py

echo "== 2. Put inPace (the Python app) inside"
rm -rf app/src/inpace
cp -r ../inpace app/src/inpace
find app/src -name "__pycache__" -type d -prune -exec rm -rf {} +

echo "== 3. Flutter packages and the app icon"
flutter pub get
dart run flutter_launcher_icons

echo "== 4. Python and its libraries for Android"
dart run serious_python:main package app/src -p Android -r -r -r app/src/requirements.txt

echo "== 5. The APKs"
flutter build apk --release --split-per-abi

mkdir -p out
for f in build/app/outputs/flutter-apk/app-*-release.apk; do
  abi=$(basename "$f" | sed -e 's/app-//' -e 's/-release.apk//')
  cp "$f" "out/inPace-android-$abi.apk"
done
echo "Done. Your APKs are in mobile/out:"
ls -la out
