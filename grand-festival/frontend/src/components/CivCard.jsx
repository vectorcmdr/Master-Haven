import DiscordLink from './DiscordLink.jsx'

export default function CivCard({ civ }) {
  // Every participating civilization is a host in its own way — the public
  // roster shows them all as Host. (Admin still shows the real status for management.)
  return (
    <div className="civ-card">
      {civ.logo_url && (
        <img className="civ-logo" src={civ.logo_url} alt={`${civ.name} emblem`} loading="lazy" />
      )}
      <div className="badge host">★ Host</div>
      <h3>{civ.name}</h3>
      <div className="role">{civ.role}</div>
      <p>{civ.description}</p>
      {civ.discord_link && (
        <div className="civ-discord">
          <DiscordLink url={civ.discord_link} />
        </div>
      )}
    </div>
  )
}
