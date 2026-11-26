## ADDED Requirements

### Requirement: Content-based format detection
The converter SHALL detect the input format from the data content and SHALL ignore file names and extensions. It SHALL accept SVG, PNG, JPEG, BMP, WebP, ICO and ICNS. For ICO input it SHALL consider all frames and use the largest. For ICNS input it SHALL use the largest frame. Unknown or undecodable data SHALL be rejected with an error.

#### Scenario: PNG with a misleading hint
- **WHEN** PNG data is loaded with the hint "photo.svg"
- **THEN** it is decoded as a PNG raster image

#### Scenario: Multi-frame ICO
- **WHEN** an ICO containing 16x16 and 48x48 frames is loaded
- **THEN** the resulting image is 48x48

#### Scenario: Garbage input
- **WHEN** random bytes are loaded
- **THEN** loading fails with a conversion error

### Requirement: SVG input is hardened
The converter SHALL reject SVG data larger than 2 MB. It SHALL reject SVG data containing a DOCTYPE or ENTITY declaration, a script element, a foreignObject element, or an event-handler attribute. It SHALL reject any `href` or `xlink:href` that is neither a local fragment reference nor an embedded `data:image/png` or `data:image/jpeg` base64 URI. It SHALL never fetch external resources. SVG SHALL be rendered as vector at each requested size, honouring the viewBox, and `currentColor` SHALL render as black.

#### Scenario: Entity declaration
- **WHEN** an SVG with an `<!ENTITY` declaration is loaded
- **THEN** it is rejected

#### Scenario: Script element
- **WHEN** an SVG containing a `<script>` element is loaded
- **THEN** it is rejected

#### Scenario: External reference
- **WHEN** an SVG image element has an `href` of `http://example.com/a.png`
- **THEN** it is rejected

#### Scenario: Oversize SVG
- **WHEN** SVG data larger than 2 MB is loaded
- **THEN** it is rejected

#### Scenario: Vector rendering
- **WHEN** a valid SVG is converted
- **THEN** each icon size is rendered from the vector, not scaled from a raster

### Requirement: Raster decompression-bomb protection
The converter SHALL reject raster images whose declared dimensions exceed 4096x4096 pixels, and raster data larger than 20 MB. Dimensions SHALL be checked before pixels are decoded.

#### Scenario: Oversized dimensions
- **WHEN** a PNG declaring 10000x10000 pixels is loaded
- **THEN** it is rejected without decoding its pixels

### Requirement: Smart adaptation
The converter SHALL trim fully transparent margins, centre the content in a square canvas preserving aspect ratio with a small inner padding, and ensure the result has visible content. It SHALL classify an image as a glyph when it is monochrome or has very low colour variance, and SHALL report that classification. Full-colour images SHALL NOT be classified as glyphs. For sizes of 24 pixels and below it SHALL render from vector when available, otherwise downscale with high quality.

#### Scenario: Transparent margins trimmed
- **WHEN** a small shape is drawn in the middle of a large transparent canvas and adapted
- **THEN** the shape fills most of the square result

#### Scenario: Non-square input
- **WHEN** a 100x50 image is adapted
- **THEN** the result is square and the content keeps its aspect ratio

#### Scenario: Glyph detection
- **WHEN** a single-colour SVG is converted
- **THEN** the result reports it is a glyph
- **WHEN** a multi-coloured photo-like image is converted
- **THEN** the result reports it is not a glyph

#### Scenario: Empty image
- **WHEN** a fully transparent image is converted
- **THEN** conversion fails with an error

### Requirement: Windows-compatible ICO output
The converter SHALL produce ICO data containing the sizes 16, 20, 24, 32, 40, 48, 64, 96, 128 and 256, ordered by size. The 256 entry SHALL be PNG-compressed. Smaller entries SHALL be 32-bit BGRA DIB images with a 1-bit AND mask. Directory offsets and byte counts SHALL be correct so that standard readers decode every entry.

#### Scenario: Every size is readable
- **WHEN** an ICO is produced from any valid input
- **THEN** each of the ten sizes can be decoded at its exact dimensions

#### Scenario: Entry encodings
- **WHEN** the ICO directory is inspected
- **THEN** the 256 entry starts with the PNG signature and every other entry has a BITMAPINFOHEADER with doubled height

### Requirement: Optional folder-base composition
When composition is requested, the converter SHALL render the glyph for each size onto the tinted folder base. The result SHALL differ from the plain conversion.

#### Scenario: Composed output differs
- **WHEN** the same glyph is converted with and without composition
- **THEN** the produced ICO data differs and the composed 256 image contains folder-colour pixels

### Requirement: Materializer for non-system entries
The converter SHALL provide an icon materializer that, for non-resource entries, converts source-supplied bytes into an ICO payload. For resource entries it SHALL return a resource payload referencing the entry in place, unless composition is requested, in which case it SHALL compose from pixels supplied by a render provider and return an ICO payload.

#### Scenario: File entry
- **WHEN** a file entry is materialized
- **THEN** the payload is an ICO payload

#### Scenario: Resource entry as-is
- **WHEN** a resource entry is materialized without composition
- **THEN** the payload is a resource payload with the entry location and resource id

#### Scenario: Resource entry composed
- **WHEN** a resource entry is materialized with composition
- **THEN** the payload is an ICO payload
