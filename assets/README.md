# Assets Directory

This directory contains assets for the VTMB Playlist Maker application.

## Icon Files

Place your application icon files here for building the executable:

### Windows
- **File:** `icon.ico`
- **Format:** ICO (Windows Icon)
- **Recommended size:** 256x256 pixels
- **Creation:**
  - Use an online converter (png2ico.com)
  - Or ImageMagick: `convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico`

### macOS
- **File:** `icon.icns`
- **Format:** ICNS (Apple Icon Image)
- **Recommended size:** 512x512 pixels at 2x (1024x1024)
- **Creation:**
  - Use Icon Composer (Xcode)
  - Or online converter
  - Or command line: `iconutil -c icns icon.iconset`

### Linux
- Linux executables don't require icon files
- Desktop integration uses separate `.desktop` files

## Creating Icons

### From PNG Image

1. **Start with a high-resolution PNG** (at least 512x512, preferably 1024x1024)
2. **Design recommendations:**
   - Simple, clear design
   - Works at small sizes (16x16, 32x32)
   - High contrast
   - Avoid fine details
   - Consider dark/light themes

3. **Convert to platform formats:**

**Windows (.ico):**
```bash
# Using ImageMagick
convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico

# Or use online: https://icoconvert.com/
```

**macOS (.icns):**
```bash
# Create iconset directory
mkdir icon.iconset

# Generate required sizes
sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png

# Convert to icns
iconutil -c icns icon.iconset
mv icon.icns assets/
```

## Icon Ideas for VTMB Playlist Maker

Consider these themes:
- **Musical notes** with vampire/gothic aesthetic
- **Playlist icon** with fangs or blood drops
- **Vampire symbol** (ankh, bat) with music elements
- **Bloodlines logo** style adapted for music
- **Dark theme** with red/purple accents

## Resources

### Free Icon Tools
- [GIMP](https://www.gimp.org/) - Free image editor
- [Inkscape](https://inkscape.org/) - Vector graphics
- [ImageMagick](https://imagemagick.org/) - Command-line image processing

### Online Converters
- [ICO Convert](https://icoconvert.com/) - PNG to ICO
- [CloudConvert](https://cloudconvert.com/) - Multi-format converter
- [AnyConv](https://anyconv.com/) - Icon converters

### Icon Design
- [Figma](https://www.figma.com/) - Free design tool
- [Canva](https://www.canva.com/) - Easy icon creation
- [IconArchive](https://www.iconarchive.com/) - Free icon sets (check licenses)

## Notes

- Icons are **optional** for building - the executable will use a default icon if none is provided
- Icons should be **square** (same width and height)
- Use **transparent backgrounds** for best results
- Test your icon at **small sizes** (16x16, 32x32) to ensure it's readable
- Keep the design **simple and recognizable**

## Current Status

- [ ] Windows icon (icon.ico) - Not provided
- [ ] macOS icon (icon.icns) - Not provided
- [ ] Sample PNG (icon.png) - Not provided

*Place your icon files in this directory before building.*
