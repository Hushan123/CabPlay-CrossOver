#!/bin/bash
# Build an unsigned IPA for signing with the user's own iPad credentials.
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
app="$scratch/Payload/CabPlayPad.app"
mkdir -p "$app" "$root/outputs" "$scratch/module-cache"
sdk="$(xcrun --sdk iphoneos --show-sdk-path)"

xcrun --sdk iphoneos swiftc -sdk "$sdk" -target arm64-apple-ios16.0 \
  -module-cache-path "$scratch/module-cache" -parse-as-library -O \
  "$root/work/ipad/CabPlayPad.swift" "$root/work/ipad/USBDisplay.swift" \
  -o "$app/CabPlayPad"
cp "$root/work/ipad/Info.plist" "$app/Info.plist"
/usr/bin/plutil -lint "$app/Info.plist"
(cd "$scratch" && /usr/bin/zip -qr CabPlayPad-unsigned.ipa Payload)
mv "$scratch/CabPlayPad-unsigned.ipa" "$root/outputs/CabPlayPad-unsigned.ipa"
printf '已生成 %s\n' "$root/outputs/CabPlayPad-unsigned.ipa"
