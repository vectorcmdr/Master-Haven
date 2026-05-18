/** Profile — person detail (works for archive_user and person rows). */
import { useEffect, useState } from "react";
import { api, ApiError, PersonDetail } from "../api/client";
import { Avatar } from "../components/Avatar";

export function Profile({ slug }: { slug: string }) {
  const [person, setPerson] = useState<PersonDetail | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setPerson(null);
    setNotFound(false);
    api<PersonDetail>(`/people/${slug}`)
      .then(setPerson)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
      });
  }, [slug]);

  if (notFound) return <div className="ta-empty">Person not found.</div>;
  if (!person) return <div className="ta-loading">Loading profile…</div>;

  return (
    <>
      <div className="ta-profile-hero">
        <Avatar author={{ avatar_letter: person.name[0], avatar_color: "teal", name: person.name }} size="xl" />
        <h1 className="ta-profile-name">{person.name}</h1>
        <div className="ta-profile-meta">
          {person.role_in_civ || "—"}{person.civ_slug ? ` · ${person.civ_slug}` : ""}
        </div>
      </div>
      <div className="ta-profile-body">
        {person.bio && (
          <p style={{ fontFamily: "Georgia, serif", fontSize: 15, lineHeight: 1.65 }}>
            {person.bio}
          </p>
        )}
        {!person.bio && (
          <p style={{ color: "var(--ta-text-faint)", fontSize: 13 }}>No bio yet.</p>
        )}
      </div>
    </>
  );
}
