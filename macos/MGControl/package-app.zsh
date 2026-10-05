#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_PATH="$REPO_ROOT/MG Control.app"
PACKAGE_DIR="$SCRIPT_DIR"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mgcontrol-app.XXXXXX")"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

SWIFT_BIN="$(/usr/bin/xcrun --find swift)"

cd "$PACKAGE_DIR"
"$SWIFT_BIN" build -c release
BIN_DIR="$("$SWIFT_BIN" build -c release --show-bin-path)"
MG_BIN="$BIN_DIR/MGControl"

if [[ ! -x "$MG_BIN" ]]; then
  echo "Không tìm thấy executable MGControl sau khi build." >&2
  exit 2
fi

rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Resources"
cp "$MG_BIN" "$APP_PATH/Contents/MacOS/MGControl"
chmod 755 "$APP_PATH/Contents/MacOS/MGControl"

cat > "$APP_PATH/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>vi</string>
  <key>CFBundleDisplayName</key>
  <string>MG Control</string>
  <key>CFBundleExecutable</key>
  <string>MGControl</string>
  <key>CFBundleIconFile</key>
  <string>MGControl.icns</string>
  <key>CFBundleIdentifier</key>
  <string>com.motgu.contentengine.mgcontrol</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>MG Control</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
  </dict>
</dict>
</plist>
PLIST

cat > "$TMP_DIR/make_icon.swift" <<'SWIFT'
import AppKit
import Foundation

let output = CommandLine.arguments[1]
let size = NSSize(width: 1024, height: 1024)
let image = NSImage(size: size)

image.lockFocus()
NSColor.clear.setFill()
NSRect(origin: .zero, size: size).fill()

let tile = NSRect(x: 96, y: 96, width: 832, height: 832)
NSColor(calibratedWhite: 0.10, alpha: 1.0).setFill()
NSBezierPath(roundedRect: tile, xRadius: 190, yRadius: 190).fill()

let paragraph = NSMutableParagraphStyle()
paragraph.alignment = .center

let attributes: [NSAttributedString.Key: Any] = [
    .font: NSFont.systemFont(ofSize: 330, weight: .bold),
    .foregroundColor: NSColor.white,
    .paragraphStyle: paragraph,
]

"MG".draw(
    in: NSRect(x: 0, y: 326, width: 1024, height: 390),
    withAttributes: attributes
)
image.unlockFocus()

guard
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let png = bitmap.representation(using: .png, properties: [:])
else {
    fputs("Không thể tạo icon PNG.\n", stderr)
    exit(2)
}

try png.write(to: URL(fileURLWithPath: output))
SWIFT

"$SWIFT_BIN" "$TMP_DIR/make_icon.swift" "$TMP_DIR/icon-1024.png"

ICONSET="$TMP_DIR/MGControl.iconset"
mkdir -p "$ICONSET"

make_png() {
  local px="$1"
  local name="$2"
  /usr/bin/sips -z "$px" "$px" "$TMP_DIR/icon-1024.png" --out "$ICONSET/$name" >/dev/null
}

make_png 16 icon_16x16.png
make_png 32 icon_16x16@2x.png
make_png 32 icon_32x32.png
make_png 64 icon_32x32@2x.png
make_png 128 icon_128x128.png
make_png 256 icon_128x128@2x.png
make_png 256 icon_256x256.png
make_png 512 icon_256x256@2x.png
make_png 512 icon_512x512.png
cp "$TMP_DIR/icon-1024.png" "$ICONSET/icon_512x512@2x.png"

/usr/bin/iconutil -c icns "$ICONSET" -o "$APP_PATH/Contents/Resources/MGControl.icns"
/usr/bin/codesign --force --deep --sign - "$APP_PATH" >/dev/null
/usr/bin/touch "$APP_PATH"

echo "Đã tạo: $APP_PATH"
