#!/bin/bash
# Build script for Guitar Practice Studio macOS app
# Run from project root: ./build_app.sh

set -e

echo "🎸 Building Guitar Practice Studio..."

# Install dev dependencies (includes PyInstaller)
echo "Installing dependencies..."
uv sync --extra dev

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build dist

# Run PyInstaller through uv
echo "Running PyInstaller..."
uv run pyinstaller guitar_practice_studio.spec

# Check if build succeeded
if [ -d "dist/Guitar Practice Studio.app" ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    echo "App location: dist/Guitar Practice Studio.app"
    echo ""
    echo "To test: open 'dist/Guitar Practice Studio.app'"
    echo ""
    echo "To distribute:"
    echo "  1. Create a DMG: hdiutil create -volname 'Guitar Practice Studio' -srcfolder 'dist/Guitar Practice Studio.app' -ov -format UDZO GuitarPracticeStudio.dmg"
    echo "  2. Or zip it: cd dist && zip -r 'Guitar Practice Studio.zip' 'Guitar Practice Studio.app'"
    echo ""
    
    # Show size
    SIZE=$(du -sh "dist/Guitar Practice Studio.app" | cut -f1)
    echo "App size: $SIZE"
else
    echo "❌ Build failed!"
    exit 1
fi
