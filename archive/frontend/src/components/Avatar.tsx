/** Avatar — colored letter chip. */
import { Author } from "../api/client";

interface Props {
  author?: { avatar_letter?: string | null; avatar_color?: string | null; name?: string };
  size?: "sm" | "md" | "lg" | "xl";
}

export function Avatar({ author, size }: Props) {
  // Cap the letter at a single character to avoid layout breakage when a
  // 2-letter `avatar_letter` slips through (and to keep visual rhythm
  // consistent — circle chips look weird with two letters at the small
  // sizes).
  const raw = author?.avatar_letter || author?.name?.[0] || "?";
  const letter = raw.toUpperCase().slice(0, 1);
  const color = author?.avatar_color || "blue";
  const sizeClass = size ? ` ta-avatar-${size}` : "";
  const label = author?.name ? `${author.name}'s avatar` : "User avatar";
  return (
    <span
      className={`ta-avatar ta-avatar-${color}${sizeClass}`}
      role="img"
      aria-label={label}
      title={author?.name}
    >
      {letter}
    </span>
  );
}

/** Helper: render avatar from an Author object directly. */
export function AvatarFor({ author, size }: { author: Author; size?: Props["size"] }) {
  return <Avatar author={author} size={size} />;
}
