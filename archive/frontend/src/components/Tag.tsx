/** Tag — small chip for doctype, beat, civ. */

export function DocTypeTag({ doctype }: { doctype: string }) {
  return (
    <span className={`ta-doctype ta-doctype-${doctype}`}>
      {doctype}
    </span>
  );
}

export function BeatTag({ beat }: { beat: string }) {
  return (
    <a href={`#/beat/${beat}`} className={`ta-tag ta-tag-beat-${beat}`}>
      {beat}
    </a>
  );
}

export function CivTag({ slug, name }: { slug: string; name?: string }) {
  return (
    <a href={`#/civ/${slug}`} className="ta-tag ta-tag-civ">
      ⸢ {name || slug}
    </a>
  );
}
