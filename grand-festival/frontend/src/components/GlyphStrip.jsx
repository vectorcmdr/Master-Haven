// Renders a portal address (hex) as NMS glyph images + the hex code.
// Glyph art lives in public/glyphs/{0-F}.webp (transparent, mint-on-clear).

const GLYPH_NAMES = {
  '0': 'Sunset', '1': 'Bird', '2': 'Face', '3': 'Diplo',
  '4': 'Eclipse', '5': 'Balloon', '6': 'Boat', '7': 'Bug',
  '8': 'Dragonfly', '9': 'Galaxy', 'A': 'Voxel', 'B': 'Fish',
  'C': 'Tent', 'D': 'Rocket', 'E': 'Tree', 'F': 'Atlas',
}
const HEX = /^[0-9a-fA-F]+$/

export default function GlyphStrip({ code, size = 'md', showHex = true }) {
  const raw = (code || '').trim().toUpperCase()
  // Not a portal address — just show whatever text it is.
  if (!raw || !HEX.test(raw)) return <span className="glyph-hex">{code}</span>

  return (
    <span className={`glyph-strip glyph-${size}`}>
      <span className="glyph-row">
        {raw.split('').map((d, i) => (
          <span className="glyph-chip" key={i} title={`${GLYPH_NAMES[d] || d} (${d})`}>
            <img src={`/glyphs/${d}.webp`} alt={GLYPH_NAMES[d] || d} loading="lazy" />
          </span>
        ))}
      </span>
      {showHex && <span className="glyph-hex">{raw}</span>}
    </span>
  )
}
