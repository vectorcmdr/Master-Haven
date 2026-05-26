/** StoryCard — newsroom card, links to /story/{id}.
 *
 * The card itself is clickable (navigates to the story page), but the
 * inner BeatTag and CivTag children are real anchors that go elsewhere.
 * Nested <a> inside <a> is invalid HTML, so the outer element is a
 * <div> with an onClick navigation handler and a tabIndex/role pair
 * for keyboard accessibility; inner anchors call stopPropagation so a
 * tag click doesn't also trigger the story navigation.
 */
import { StorySummary } from "../api/client";
import { Avatar } from "./Avatar";
import { BeatTag, CivTag, DocTypeTag } from "./Tag";

interface Props {
  story: StorySummary;
  hero?: boolean;
}

export function StoryCard({ story, hero }: Props) {
  const href = `#/story/${story.id}`;
  return (
    <div
      className={hero ? "ta-hero-story" : "ta-story-card"}
      role="link"
      tabIndex={0}
      onClick={(e) => {
        // Don't trigger when the user clicked an inner link.
        if ((e.target as HTMLElement).closest("a")) return;
        window.location.hash = href;
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          window.location.hash = href;
        }
      }}
      style={{ cursor: "pointer" }}
    >
      <div className="ta-story-tags" onClick={(e) => e.stopPropagation()}>
        <DocTypeTag doctype={story.doctype} />
        {story.beat && <BeatTag beat={story.beat} />}
        {story.civs.map((c) => <CivTag key={c} slug={c} />)}
      </div>
      {hero ? (
        <a href={href} className="ta-hero-headline-link" style={{ color: "inherit", textDecoration: "none" }}>
          <h2 className="ta-hero-headline">{story.headline}</h2>
        </a>
      ) : (
        <a href={href} className="ta-story-headline-link" style={{ color: "inherit", textDecoration: "none" }}>
          <h3 className="ta-story-headline">{story.headline}</h3>
        </a>
      )}
      {story.deck && (
        <p className={hero ? "ta-hero-deck" : "ta-story-deck"}>{story.deck}</p>
      )}
      <div className="ta-byline-row">
        {hero && <Avatar author={story.author} size="md" />}
        <span>
          By <a
            href={`#/profile/${story.author.slug}`}
            onClick={(e) => e.stopPropagation()}
            style={{ color: "inherit", fontWeight: 700 }}
          >{story.author.name}</a>
          {story.read_minutes ? ` · ${story.read_minutes} min` : ""}
        </span>
      </div>
    </div>
  );
}
