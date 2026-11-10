# Wormhole transit relay on Fly.io

Run one Fly App containing one small, always-on Fly Machine. The server is
the official Python `magic-wormhole-transit-relay` (pinned to 0.5.0), which
speaks the transit protocol used by the Rust `wormhole-rs` client.

This deployment relays bulk data. Clients continue using their default public
mailbox/rendezvous server for code matching and connection negotiation.
Hosting the mailbox too is a separate choice; see below.

## Deploy

1. Install [flyctl](https://docs.fly.io/flyctl/install/) and have a Fly account
   with billing enabled.
2. Change `app` in `fly.toml` to a globally unique app name, for example
   `erik-wormhole-relay`. The example name is not reserved.
3. Optionally change `primary_region`. `lax` is Los Angeles; choose a region
   close to your usual users. `iad` and `ewr` are the cheapest compute regions
   in the pricing documentation reviewed on November 9, 2026.
4. Run these commands from this directory. Use the same name in `apps create`
   that you entered in `fly.toml`:

```bash
fly auth login
fly apps create erik-wormhole-relay
fly ips allocate-v4
fly deploy --ha=false --remote-only
fly scale count 1
fly status
fly ips list
```

If you have multiple organizations, select the intended one when creating the
app. The remote builder means you do not need Docker installed locally.

Check that `fly status` shows exactly one app Machine in the intended region.
Fly's build infrastructure is separate from this app Machine.

## Verify the public relay

Replace the hostname with your app's hostname:

```bash
python3 check-relay.py erik-wormhole-relay.fly.dev
```

Expected output begins with `PASS`. This makes two real relay connections,
checks their matching handshakes, and sends a random payload in each direction.
It requires only Python's standard library. A successful check verifies the
relay and public TCP route, rather than just checking that a port is open.

## Use wormhole-rs

On the sending machine, using wormhole-rs 0.8.1:

```bash
wormhole-rs send \
  --relay-server tcp://erik-wormhole-relay.fly.dev:4001 \
  --force-relay ./file.tar.zst
```

On the receiving machine, replace the example code with the sender's code:

```bash
wormhole-rs receive \
  --relay-server tcp://erik-wormhole-relay.fly.dev:4001 \
  --force-relay 7-example-code
```

Set the custom relay on **both ends**, so neither offers a default public
transit relay. Use `--force-relay` on both for initial verification; otherwise
a successful transfer might have used a direct connection. Remove it for
normal direct-first operation if desired.

For wormhole-rs 0.8.1 these options follow `send`/`receive`. Older manpages
show a different layout; use your installed client's subcommand help if it
rejects these commands.

To make this relay the default in a shell on each machine:

```bash
export WORMHOLE_RELAY_URL=tcp://erik-wormhole-relay.fly.dev:4001
wormhole-rs send --force-relay ./file.tar.zst
# On the other machine, after setting the same environment variable:
wormhole-rs receive --force-relay 7-example-code
```

The custom relay flag replaces the default relay when supplied. Both machines
must still use the same mailbox server. `WORMHOLE_RELAY_URL` does not change it.

## Why this configuration

- One Machine: matching relay connections are held in memory. Two clients
  routed to different Machines cannot be paired. Avoid scaling this app to
  multiple Machines or regions. Fly's default spare Machine creation is
  disabled by `--ha=false`; keep using this option for later deploys.
- Raw TCP on port 4001: no HTTP, TLS, or PROXY handler should alter the byte
  stream. The client URL is `tcp://`, not `https://` or `tls://`.
- Dedicated IPv4: shared IPv4 routing depends on HTTP or TLS. This raw TCP
  service needs a dedicated address for IPv4 clients. IPv6-only deployment
  can avoid that address charge if every client has working IPv6.
- No volume or database: transit forwarding needs no persistent file state.
  Files are streamed through the server rather than saved to disk. Optional
  usage database logging is not enabled.
- Always on: `auto_stop_machines = "off"` avoids cold starts. The restart
  policy restarts an unexpectedly exited service. Neither setting provides
  high availability; this is intentionally a single Machine.
- 256 MB and one shared CPU: a starting size for modest personal/team use.
  Increase memory in `fly.toml` and redeploy if needed. The connection limit
  counts TCP connections, including pending peers, rather than transfers;
  it is not a guarantee that 20 busy transfers fit within 256 MB.
- Rolling deployments update the single Machine. Updates/restarts interrupt
  active transfers; deploy while idle. Avoid canary/blue-green deployment
  modes that temporarily introduce additional relay Machines.

This is a publicly reachable relay with no account/password access control
configured. Anyone who knows its address can use it and consume bandwidth.
The Wormhole pairing token is not a service-wide access credential. If you
need an access-restricted relay, put it behind a private network or add a
compatible access-control layer before publishing it for wider use.

## Cost

Pricing reviewed November 9, 2026, in USD:

| Item | Cost |
| --- | --- |
| One always-on 256 MB shared-cpu-1x Machine in `iad` or `ewr` | $2.19 per 30 days |
| Dedicated IPv4 | $2/month |
| Internet egress from North America or Europe | $0.02/GB |
| Internet ingress | Free |

The minimum baseline above is about $4.19 per 30-day month plus bandwidth,
before any account-specific credits/waivers. Other regions, including the
default `lax`, can have different compute prices. A 100 GB transfer through
the relay produces roughly 100 GB of public egress, about $2 at that rate,
plus protocol overhead and any applicable cross-region routing charges.
Direct transfers do not send the bulk file through this relay.

## Operations

```bash
fly logs
fly checks list
fly status
# Future deployments, from this directory:
fly deploy --ha=false --remote-only
```

Use Fly's billing dashboard to monitor bandwidth and costs.

For infrequent use, a later optimization is `auto_stop_machines = "stop"`
with `auto_start_machines = true` and `min_machines_running = 0` inside
`[[services]]`. Test cold-start transfers before relying on that mode.
The dedicated IPv4 remains billable even while the Machine is stopped.

## If you also want your own mailbox server

The mailbox/rendezvous server is a separate WebSocket service:
[`magic-wormhole-mailbox-server`](https://github.com/magic-wormhole/magic-wormhole-mailbox-server).
It uses SQLite for persisted mailbox state. A clean Fly layout is a second
single-Machine app with a small volume and an HTTPS/WebSocket endpoint.
Configure both clients with:

```bash
wormhole-rs send \
  --rendezvous-server wss://YOUR-MAILBOX-APP.fly.dev/v1 \
  --relay-server tcp://erik-wormhole-relay.fly.dev:4001 \
  --force-relay ./file.tar.zst
```

Use the same `--rendezvous-server` and `--relay-server` options on the receiving
side. The mailbox app is not included in this transit-only deployment.

## Validation performed

- Installed the pinned relay on Python 3.12 and checked its actual startup
  options.
- Started it as an unprivileged user using the configured listener.
- Paired two TCP clients and verified bidirectional payload forwarding.
- Parsed `fly.toml` with Python's TOML parser.
- Checked client flag placement against the released wormhole-rs 0.8.1
  source from both GitHub and crates.io.

The Docker image was not built here (no local Docker engine), and no Fly app
has been deployed. Fly's server-side config validation requires an authenticated
account and must run after `fly auth login`. The public relay check above is
the final deployment verification.

## Sources

- [Official transit relay and protocol overview](https://github.com/magic-wormhole/magic-wormhole-transit-relay)
- [Relay startup options](https://github.com/magic-wormhole/magic-wormhole-transit-relay/blob/master/docs/running.md)
- [Pinned server release on PyPI](https://pypi.org/project/magic-wormhole-transit-relay/0.5.0/)
- [wormhole-rs 0.8.1 CLI source](https://github.com/magic-wormhole/magic-wormhole.rs/blob/0.8.1/cli/src/main.rs)
- [Fly public networking and dedicated IPv4](https://docs.fly.io/networking/services)
- [Fly app configuration](https://docs.fly.io/reference/configuration)
- [Fly deploy options, including HA default](https://docs.fly.io/flyctl/cmd/fly_deploy)
- [Fly resource pricing](https://docs.fly.io/about/pricing)
