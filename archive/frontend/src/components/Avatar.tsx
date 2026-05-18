/** Avatar — colored letter chip. */
import { Author } from "../api/client";

interface Props {
  author?: { avatar_letter?: string | null; avatar_color?: string | null; name?: string };
  size?: "sm" | "md" | "lg" | "xl";
}

export function Avatar({ author, size }: Props) {
  const letter = (author?.avatar_letter || author?.name?.[0] || "?").toUpperCase().slice(0, 2);
  const color = author?.avatar_color || "blue";
  const sizeClass = size ? ` ta-avatar-${size}` : "";
  return <span className={`ta-avatar ta-avatar-${color}${sizeClass}`}>{letter}</span>;
}

/** Helper: render avatar from an Author object directly. */
export function AvatarFor({ author, size }: { author: Author; size?: Props["size"] }) {
  return <Avatar author={author} size={size} />;
}
