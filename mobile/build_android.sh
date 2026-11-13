#!/usr/bin/env bash
# Build the inPace Android app (APK). Used by GitHub Actions, and works on your own computer too
# (needs Flutter, Java 21 and the Android SDK; run: bash mobile/build_android.sh).
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
# Made your own icon with IconKitchen? Put its "res" folder at mobile/icon/res and it's used instead.
if [ -d icon/res ]; then
  echo "Using the icon from mobile/icon/res"
  cp -r icon/res/. android/app/src/main/res/
else
  dart run flutter_launcher_icons
fi
# The splash screen: Tempo and the logo while the app starts.
dart run flutter_native_splash:create

echo "== 4. Python and its libraries for Android"
# Ship the code already compiled (.pyc). On a phone Python reads its libraries straight from a zip and can't save
# compiled copies, so without this it compiles every module again on every start (1 to 2 seconds on a
# mid-range phone). Only the options this version of the packager knows are used, so the build never breaks.
PACK_FLAGS=()
HELP=$(dart run serious_python:main package --help 2>&1 || true)
# Never --cleanup: it deletes the .py files (main.py too), and the app must keep working whatever the runner looks for.
for flag in --compile-app --compile-packages; do
  if grep -q -- "$flag" <<<"$HELP"; then PACK_FLAGS+=("$flag"); fi
done
echo "Packaging with: ${PACK_FLAGS[*]:-(no extra options)}"
dart run serious_python:main package app/src -p Android "${PACK_FLAGS[@]}" -r -r -r app/src/requirements.txt

echo "== 5. The APKs"
# Same version as inPace itself. The build number must grow with every release, or Android refuses the update.
VERSION=$(python3 -c "import re;print(re.search(r'\"(.+?)\"', open('../inpace/__init__.py').read()).group(1))")
BUILD_NUMBER=$(python3 -c "a,b,c=(int(x) for x in '$VERSION'.split('.')[:3]);print(a*10000+b*100+c)")
echo "Version $VERSION (build $BUILD_NUMBER)"
# 64-bit phones (arm64) cover nearly every Android phone from the last 7 years.
flutter build apk --release --target-platform android-arm64 --split-per-abi \
  --build-name "$VERSION" --build-number "$BUILD_NUMBER"

mkdir -p out
for f in build/app/outputs/flutter-apk/app-*-release.apk; do
  abi=$(basename "$f" | sed -e 's/app-//' -e 's/-release.apk//')
  cp "$f" "out/inPace-android-$abi.apk"
done
echo "Done. Your APKs are in mobile/out:"
ls -la out
