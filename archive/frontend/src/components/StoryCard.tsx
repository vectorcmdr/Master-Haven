/** StoryCard — newsroom card, links to /story/{id}. */
import { StorySummary } from "../api/client";
import { Avatar } from "./Avatar";
import { BeatTag, CivTag, DocTypeTag } from "./Tag";

interface Props {
  story: StorySummary;
  hero?: boolean;
}

export function StoryCard({ story, hero }: Props) {
  const inner = (
    <>
      <div className="ta-story-tags">
        <DocTypeTag doctype={story.doctype} />
        {story.beat && <BeatTag beat={story.beat} />}
        {story.civs.map((c) => <CivTag key={c} slug={c} />)}
      </div>
      {hero ? (
        <h2 className="ta-hero-headline">{story.headline}</h2>
      ) : (
        <h3 className="ta-story-headline">{story.headline}</h3>
      )}
      {story.deck && (
        <p className={hero ? "ta-hero-deck" : "ta-story-deck"}>{story.deck}</p>
      )}
      <div className="ta-byline-row">
        {hero && <Avatar author={story.author} size="md" />}
        <span>
          By <b>{story.author.name}</b>
          {story.read_minutes ? ` · ${story.read_minutes} min` : ""}
        </span>
      </div>
    </>
  );
  return (
    <a href={`#/story/${story.id}`} className={hero ? "ta-hero-story" : "ta-story-card"}>
      {inner}
    </a>
  );
}
