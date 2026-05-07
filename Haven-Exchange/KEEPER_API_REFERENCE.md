# Travelers Exchange — Keeper Bot API Reference

**Companion to:** `EXCHANGE_KEEPER_INTEGRATION_SPEC.md`
**Audience:** Stars (The_Keeper maintainer) — implementing Discord cogs against the Exchange API
**Scope:** Every endpoint your bot will call, with auth, request body, success response, and error cases. Sourced directly from the route handlers; verified against branch `keeper-integration-p0` (commit `3ce49e6`).

> Anything in this file is a working contract. If a field disappears or changes shape, treat it as a breaking change and ping Parker.

---

## Conventions

- **Base URL:** `https://travelers-exchange.online`
- **Format:** Request bodies are JSON unless explicitly marked `application/x-www-form-urlencoded`. Responses are always JSON.
- **Money:** All amounts are integers in TC (Travelers Coin). Display in national currency by computing `amount * gdp_multiplier / 100` (rounded as you prefer; the multiplier is stored as `int * 100`).
- **Wallets:** `TRV-<8-hex>` for users. `TRV-NATION-<8-hex>` for treasuries. `TRV-BANK-<8-hex>` for banks.
- **Errors:** FastAPI shape — `{"detail": "Human-readable message"}` with HTTP 4xx. Surface `detail` verbatim in Discord embeds; it's already user-friendly.

## Auth

Every Exchange API request from the bot uses both headers:

```
Authorization: Bearer <KEEPER_API_KEY>
X-Discord-User-Id: <discord_user_id>
```

- The bearer key is the plaintext token Parker hands you from `scripts/issue_bot_key.py`. Format: `tx_live_<32 hex>`.
- The `X-Discord-User-Id` header is required for any endpoint that needs a logged-in user (everything tagged **user**, **nation_leader**, **bank_op**, **world_mint** below). The server resolves it to the linked Exchange user via `users.discord_id`.
- For purely public endpoints (`public` tag), you can omit `X-Discord-User-Id`. The bearer alone is fine.
- For the `/discord-link/start` endpoint, only the bearer is required (no `X-Discord-User-Id` — the discord_id is in the body).
- **If a Discord user hasn't linked yet** and you call a `user`-tagged endpoint with their `X-Discord-User-Id`, the server returns **HTTP 303 to `/login`**. Treat that as "user not linked"; respond in Discord with "Run `/exchange link` first."

## Rate limits

- `600` mutating requests/minute/key
- `60` mutating requests/minute/discord_id
- `GET`/`HEAD`/`OPTIONS` are not throttled
- Overage returns `HTTP 429` with `{"detail": "..."}`. Treat as transient; back off and retry.

---

## 0. Linking (P0)

### `POST /api/auth/discord-link/start`

**Auth:** Bearer key only (no `X-Discord-User-Id`)
**Body:** `{"discord_id": "<discord_user_id>"}`
**Success:** `200`
```json
{"code": "511783", "expires_in": 600, "link_url": "https://travelers-exchange.online/settings#link-discord"}
```
**Errors:** `400` empty discord_id; `401` bad/missing bearer; `409` discord_id already linked.

DM the `code` and the `link_url` to the user.

### `POST /api/auth/discord-link/confirm`

This is **session-auth** — called from the website by the logged-in user, not by the bot. You don't implement this in Discord. It's listed here so you know what the user sees on the other side.
**Body:** `code=<6 digits>` (form-encoded)
**Success:** `200 {"success": true, "discord_id": "..."}`
**Errors:** `400` malformed; `404` code not found / used; `410` expired; `409` race-condition collision or user already linked.

### `DELETE /api/auth/discord-link`

Session-auth, also website-only. User unlinks themselves. Bot doesn't call this.

---

## 1. Wallet, Ledger, Transfers

### `GET /api/wallet`
**Auth:** user
**Returns:** caller's wallet
```json
{
  "address": "TRV-6fa948f9", "balance": 0, "display_name": "Eve",
  "nation": null, "created_at": "...", "last_active": "...",
  "transaction_count_lifetime": 0, "transaction_count_30d": 0,
  "volume_lifetime": 0, "volume_30d": 0
}
```

### `GET /api/wallet/search?q=<prefix>&limit=<1-20>`
**Auth:** public
Prefix search across users + treasuries. Default `limit=8`.

### `GET /api/wallet/{address}`
**Auth:** public
Returns either user-shape or treasury-shape:
- User: same fields as `/api/wallet` minus `created_at` (display_name, nation, balance, address, history fields)
- Treasury: `{"address","balance","display_name","type":"nation_treasury"}`

`404` if not found.

### `GET /api/wallet/{address}/transactions?page=&per_page=`
**Auth:** public
Paginated tx list. `per_page` capped at 100. Returns `{"transactions": [...], "page", "per_page", "total"}`.

### `GET /api/ledger?page=&per_page=`
**Auth:** public
Global ledger feed. `per_page` capped at 100.

### `GET /api/transactions/{tx_hash}`
**Auth:** public
Full record. Accepts the full hash, or `tx_<first12>` short form. `404` if not found.
Response: `{tx_hash, prev_hash, tx_type, from_address, to_address, amount, fee, memo, nonce, status, created_at}`.

### `POST /api/transactions/transfer`
**Auth:** user
**Body:** `{"to_address": "TRV-...", "amount": 100, "memo": "optional"}`
**Success:** `200 {"success": true, "tx_hash": "...", "amount": 100}`
**Errors:** `200 {"success": false, "error": "..."}` for insufficient balance, invalid address, etc. (Note: this endpoint returns 200 + success-flag rather than HTTP 4xx for business errors.)

---

## 2. Nations

### `POST /api/nations/apply`
**Auth:** user
**Body:** `{"name", "currency_name?", "currency_code?", "description?", "discord_invite?", "game?"}`
- `currency_code` must be 2–5 uppercase letters if provided. Must be unique.
**Success:** `200 {"success": true, "nation_id": int}`
**Errors:** `400` validation; `409` already lead a nation / name taken / currency code taken.

### `GET /api/nations`
**Auth:** public
Returns `{"nations": [...]}`. Each nation: `{id, name, member_count, currency_name, currency_code, gdp_score, gdp_multiplier, gdp_display}`.

### `POST /api/nations/{id}/join`
**Auth:** user
**Body:** none
**Success:** `200 {"success": true}`
**Errors:** `404` nation not found; `400` already in a nation / nation not approved.

### `POST /api/nations/{id}/leave`
**Auth:** user
**Body:** none
**Success:** `200 {"success": true}`
**Errors:** `400` not in this nation / leader can't leave.

### `GET /api/nations/{id}/members`
**Auth:** public
Returns `{"members": [{id, username, display_name, wallet_address, role}]}`.

### `POST /api/nations/{id}/distribute`
**Auth:** nation_leader
**Body:** `{"to_address", "amount", "memo?"}`
**Success:** `200 {"success": true, "tx_hash": "..."}`
**Errors:** `403` not the leader; `400` insufficient treasury balance.

### `POST /api/nations/{id}/distribute-bulk`
**Auth:** nation_leader
**Body:** `{"distributions": [{"to_address", "amount"}, ...], "memo?"}`
Atomic — either all transfers succeed or none.
**Errors:** `400` if total exceeds treasury balance.

### `GET /api/nations/{id}/demurrage`
**Auth:** user (caller must be in the nation)
Returns `{"demurrage_enabled": bool, "demurrage_rate_bps": int}`.

### `PUT /api/nations/{id}/demurrage`
**Auth:** nation_leader
**Body:** `{"demurrage_enabled?": bool, "demurrage_rate_bps?": int}` (1–1000 bps).
**Success:** `200` with updated values.

### `GET /api/nations/{id}/stimulus-proposals?status=`
**Auth:** nation_leader (their own nation) or world_mint
Returns proposals. Status filter: `pending|approved|rejected`.

### `POST /api/nations/{id}/stimulus-proposals/{proposal_id}/approve`
### `POST /api/nations/{id}/stimulus-proposals/{proposal_id}/reject`
**Auth:** nation_leader of the affected nation
Body for both: `{"reason?": str}`. `400` if not pending.

---

## 3. Banks & Loans

### `POST /api/banks`
**Auth:** nation_leader
**Body:** `{"name", "owner_user_id"}` — owner must be a member of the leader's nation.
**Success:** `200 {"success": true, "bank_id"}`
**Errors:** `400` non-member owner; `409` 4-bank cap reached.

### `GET /api/banks/nation/{nation_id}`
**Auth:** public
Returns `{"banks": [...]}`.

### `GET /api/banks/{bank_id}`
**Auth:** public

### `POST /api/banks/{bank_id}/deactivate`
**Auth:** nation_leader

### `GET /api/banks/{bank_id}/loans`
**Auth:** bank_op (the bank's owner) / nation_leader / world_mint

### `POST /api/banks/{bank_id}/loans`
**Auth:** bank_op
**Body:** `{"borrower_user_id", "amount", "memo?"}`
Borrower must be in the same nation, must not have an active loan, bank must have reserves ≥ amount.
**Success:** `200 {"success": true, "loan_id"}`

### `POST /api/banks/{bank_id}/loans/{loan_id}/forgive`
**Auth:** nation_leader

### `POST /api/nations/{nation_id}/loans`
**Auth:** nation_leader (treasury-as-lender)
**Body:** `{"borrower_user_id", "amount", "memo?"}`

### `GET /api/nations/{nation_id}/loans`
**Auth:** nation_leader / world_mint

### `POST /api/nations/{nation_id}/loans/{loan_id}/forgive`
**Auth:** nation_leader

### `GET /api/loans/mine`
**Auth:** user
Returns `{"loans": [...]}` with all of caller's loans (active + closed).

### `POST /api/loans/{loan_id}/pay`
**Auth:** user (must be the borrower)
**Body:** `{"amount": int}`
**Success:** `200` with the full burn-split breakdown:
```json
{
  "success": true,
  "tx_hash": "...",
  "interest_portion": 12,
  "principal_portion": 88,
  "during_payment_burn": 8,    // burn taken on the interest portion
  "close_burn": 0,             // additional burn if final payment
  "burn_amount": 8,            // total burned this payment
  "bank_amount": 92,           // what reached the bank/treasury
  "is_final_payment": false,
  "remaining_principal": 412,
  "remaining_interest": 28
}
```
**UX requirement:** show all of these in the Discord confirmation embed so members understand exactly where their TC went. The "burn" goes to `TRV-00000000` (the World Mint) and is permanently out of circulation.

---

## 4. Shops & Marketplace

### `POST /api/shops`
**Auth:** user (must be in an approved nation)
**Body:** `{"name", "description?", "shop_type": "general"|"resource_depot", "mining_setup?"}`
- `mining_setup` is **required** when `shop_type == "resource_depot"`.
- Shop starts `status="pending"` — needs NL or WM approval before listings can be added.
**Success:** `200 {"success": true, "shop_id", "status": "pending"}`

### `GET /api/shops?nation_id=&type=`
**Auth:** public
Filter by `nation_id` and/or `type` (=`shop_type`). Returns approved+active shops.

### `GET /api/shops/pending`
**Auth:** nation_leader (sees only own nation) / world_mint (sees all)
Returns `{"shops": [...]}`.

### `GET /api/shops/{id}`
**Auth:** public
Shop detail with embedded listings. Each listing includes `price` (TC) and `price_national` (converted).

### `POST /api/shops/{id}/listings`
**Auth:** shop_owner
**Body:** `{"title", "description?", "price", "category": "service"|"coordinates"|"item"|"other"}`
- `price` is in **national currency**. Server converts to TC using the nation's `gdp_multiplier`.
**Errors:** `403` not owner; `400` shop not approved.

### `POST /api/shops/{id}/listings/{listing_id}/buy`
**Auth:** user
**Body:** none
**Success:** `200 {"success": true, "tx_hash", "amount_tc"}`
Server transfers TC, marks listing unavailable, updates GDP.

### `PUT /api/shops/{id}/listings/{listing_id}`
**Auth:** shop_owner
**Body:** any of `{"title?", "description?", "price?", "category?", "is_available?"}`. Only fields you send are updated.

### `POST /api/shops/{id}/approve`
**Auth:** nation_leader (own nation, NOT own shop) or world_mint
**Body:** none
**Errors:** `403` you can't approve your own shop (V4 fix); `400` shop already approved.

### `POST /api/shops/{id}/reject`
**Auth:** nation_leader / world_mint (NOT own shop)
**Body:** `{"reason?": str}`

### `POST /api/shops/{id}/suspend`
**Auth:** nation_leader / world_mint (NOT own shop, except for WM)
**Body:** `{"reason?": str}`. Disables an approved shop.

---

## 5. Stock Market

### `GET /api/stocks?stock_type=&sort_by=`
**Auth:** public
`stock_type` filter: `nation`|`business`. `sort_by`: `ticker|price|change_24h|volume_24h`.

### `GET /api/stocks/portfolio`
**Auth:** user
Caller's holdings + total gain/loss.

### `GET /api/stocks/rankings`
**Auth:** public
Performance leaderboard.

### `GET /api/stocks/{ticker}`
**Auth:** public
Detail with recent trades and valuation breakdown.

### `GET /api/stocks/{ticker}/history`
**Auth:** public
90-day price history. Render with ASCII sparkline for v1 (good enough); a real chart can come later via QuickChart.

### `POST /api/stocks/{ticker}/buy`
**Auth:** user
**Body:** `{"shares": int}`
- Business stocks gated on the buyer being a member of the issuing nation.
**Success:** `200 {"success": true, "shares_owned", "total_cost_tc"}`
**Errors:** `400` insufficient balance; `403` non-citizen for business stock.

### `POST /api/stocks/{ticker}/sell`
**Auth:** user
**Body:** `{"shares": int}`
**Errors:** `400` not enough shares.

### `POST /api/stocks/{stock_id}/close`
**Auth:** world_mint OR shop_owner (for business stocks of own shop)
**Body:** `{"reason?": str}`
Closes the stock and pays out all holders at the close price.

---

## 6. World Mint (Admin) — gate Discord-side too

All endpoints require the linked Exchange user to have `role=world_mint`. **Strongly recommend** Stars also gate these Discord commands behind a Discord role check (`World Mint` or server-owner).

### `GET /api/mint/stats`
Global economy dashboard.

### `POST /api/mint/execute`
**Body:** `{"to_address", "amount", "memo?"}` — mints to a wallet or treasury. Subject to per-nation `mint_cap`.

### `GET /api/mint/allocations`
Returns pending + approved + recently-distributed allocations.

### `POST /api/mint/allocations/{id}/approve`
**Body:** `{"approved_amount?": int}` — defaults to the proposed amount.

### `POST /api/mint/allocations/{id}/execute`
Distribute one already-approved allocation to its nation treasury.

### `POST /api/mint/execute-all-approved`
Batch-distribute every approved-but-unexecuted allocation.

### `POST /api/mint/calculate-allocations`
**Body:** `{"period?": str}` (default = current month)
Generates the next batch of monthly allocations.

### `POST /api/mint/nations/{id}/approve`
Approve a pending nation. Auto-IPO's its stock.

### `POST /api/mint/nations/{id}/reject`
Reject a pending nation.

### `POST /api/mint/nations/{id}/suspend`
Suspend an approved nation. Demotes the leader to `citizen` (V4 fix), unless they lead another approved nation.

### `POST /api/mint/nations/{id}/unsuspend`
Restore a suspended nation. Re-promotes the leader to `nation_leader`.

### `POST /api/mint/recalculate-gdp`
Force a GDP recalc + stimulus check.

### `GET /api/mint/gdp-history?nation_id=&limit=`
GDP snapshots. `limit` default 30.

### `GET /api/mint/stimulus-proposals?status=&limit=`
Auto-generated stimulus proposals (triggered on nation GDP drops).

### `POST /api/mint/stimulus-proposals/{id}/approve`
**Body:** `{"approved_amount?", "reason?"}`

### `POST /api/mint/stimulus-proposals/{id}/reject`
**Body:** `{"reason?"}`

### `GET /api/mint/settings`
Returns global `{burn_rate_bps, interest_rate_cap_bps, interest_burn_rate_bps}`.

### `POST /api/mint/settings`
**Body:** `{"burn_rate_bps", "interest_rate_cap_bps", "interest_burn_rate_bps?"}`

---

## Working examples

These are the exact curl commands I used to verify the integration is live. Replace `BOT_KEY` with your actual key and `DISCORD_ID` with a linked Discord user ID.

```bash
BOT_KEY="tx_live_<32hex>"
DISCORD_ID="123456789012345678"

# 1. Start a link for a brand new Discord user
curl -s -X POST https://travelers-exchange.online/api/auth/discord-link/start \
  -H "Authorization: Bearer ${BOT_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"discord_id\":\"${DISCORD_ID}\"}"
# → {"code":"511783","expires_in":600,"link_url":"..."}
# DM the code + link_url to the user; they paste it on the Settings page.

# 2. After they've linked, fetch their wallet
curl -s https://travelers-exchange.online/api/wallet \
  -H "Authorization: Bearer ${BOT_KEY}" \
  -H "X-Discord-User-Id: ${DISCORD_ID}"
# → {"address":"TRV-...","balance":0,...}

# 3. Send TC on their behalf
curl -s -X POST https://travelers-exchange.online/api/transactions/transfer \
  -H "Authorization: Bearer ${BOT_KEY}" \
  -H "X-Discord-User-Id: ${DISCORD_ID}" \
  -H "Content-Type: application/json" \
  -d '{"to_address":"TRV-aaaa1111","amount":50,"memo":"From Discord"}'
# → {"success":true,"tx_hash":"..."} OR {"success":false,"error":"Insufficient balance..."}

# 4. List approved nations (no X-Discord-User-Id needed, public)
curl -s https://travelers-exchange.online/api/nations \
  -H "Authorization: Bearer ${BOT_KEY}"
# → {"nations":[...]}

# 5. Pay a loan and show the burn breakdown in the embed
curl -s -X POST "https://travelers-exchange.online/api/loans/42/pay" \
  -H "Authorization: Bearer ${BOT_KEY}" \
  -H "X-Discord-User-Id: ${DISCORD_ID}" \
  -H "Content-Type: application/json" \
  -d '{"amount":100}'
# → full breakdown — render every field
```

---

## What to do when

| Situation | Response |
|---|---|
| HTTP 303 from a user-tier endpoint | "You're not linked yet — run `/exchange link`." |
| HTTP 401 | Bot key was rejected — check `Authorization` header / key wasn't revoked. |
| HTTP 403 | The user lacks the required role (e.g. citizen calling NL endpoint). Embed message: surface `detail` verbatim. |
| HTTP 404 | The resource isn't there. Surface `detail`. |
| HTTP 409 | A conflict (already linked, name taken, double-vote, etc.). Surface `detail`. |
| HTTP 429 | Rate-limited. Back off ~30s and retry. |
| `{"success": false, "error": "..."}` on `/transfer` | Render `error` in red. The HTTP status will still be `200`. |

---

## Branch / commit you're targeting

- Branch: `keeper-integration-p0`
- Commit: `3ce49e6`
- Repo: `Parker1920/Master-Haven`
- Spec: `Haven-Exchange/EXCHANGE_KEEPER_INTEGRATION_SPEC.md` (the doc Parker wrote you)
- Reference (this file): `Haven-Exchange/KEEPER_API_REFERENCE.md`

The branch is not yet merged to `main`. Parker will merge after his review. URL behavior is identical against the running Pi `https://travelers-exchange.online` once merged + deployed.
