// Small Discord link pill. Renders nothing unless given a real http(s) URL.
export default function DiscordLink({ url, label = 'Discord' }) {
  const v = (url || '').trim()
  if (!/^https?:\/\//i.test(v)) return null
  return (
    <a className="discord-link" href={v} target="_blank" rel="noopener noreferrer">
      <span aria-hidden="true">💬</span> {label}
    </a>
  )
}
