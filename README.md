# Wormhole mailbox and transit relay on Fly.io

This app runs the official Python mailbox server (0.8.0) and transit relay
(0.5.0) together on one always-on Fly Machine in `lax`. It supports the Rust
`wormhole-rs` client, including code matching and forced relay transfers.

| Service | Endpoint |
| --- | --- |
| Mailbox, secure WebSocket | `wss://erik-reed-wormhole.fly.dev/v1` |
| Mailbox, plain WebSocket on port 4000 | `ws://erik-reed-wormhole.fly.dev:4000/v1` |
| Transit relay, raw TCP | `tcp://erik-reed-wormhole.fly.dev:4001` |

The mailbox listens on port 4000 inside the Machine. Fly also exposes it
through TLS on port 443. The installed wormhole-rs 0.8.1 binary reports
`TLS support not compiled in`, so the verified commands below use port 4000.
Clients built with TLS support can use the secure WebSocket endpoint instead.
The transit listener on port 4001 has no HTTP, TLS, or PROXY handler.

## Use wormhole-rs

Set both endpoints in the shell on **both** the sending and receiving machines:

```bash
export WORMHOLE_MAILBOX_URL=ws://erik-reed-wormhole.fly.dev:4000/v1
export WORMHOLE_RELAY_URL=tcp://erik-reed-wormhole.fly.dev:4001
```

Send a file:

```bash
wormhole-rs send --force-relay ./file.tar.zst
```

Receive it on the other machine, using the code printed by the sender:

```bash
wormhole-rs receive --force-relay 7-example-code
```

These commands use wormhole-rs 0.8.1. For explicit flags instead of environment
variables, use:

```bash
wormhole-rs send \
  --rendezvous-server ws://erik-reed-wormhole.fly.dev:4000/v1 \
  --relay-server tcp://erik-reed-wormhole.fly.dev:4001 \
  --force-relay ./file.tar.zst

wormhole-rs receive \
  --rendezvous-server ws://erik-reed-wormhole.fly.dev:4000/v1 \
  --relay-server tcp://erik-reed-wormhole.fly.dev:4001 \
  --force-relay 7-example-code
```

`--force-relay` ensures the transfer tests this relay. Remove it for normal
direct-first operation. Both peers must use the same mailbox, and both must
set the custom relay to avoid offering a default public relay.

## Deploy

The configured app is `erik-reed-wormhole` in the `personal` organization.
For a fresh deployment, create the app and storage first:

```bash
flyctl auth login
flyctl apps create erik-reed-wormhole --org personal
flyctl ips allocate-v4
flyctl ips allocate-v6
flyctl volumes create mailbox_data --size 1 --region lax
```

Then deploy, or update the existing app:

```bash
flyctl config validate
flyctl deploy --ha=false --remote-only
flyctl status
flyctl checks list
```

The remote builder does not require a local Docker engine. `.dockerignore`
limits the build context to the Dockerfile, requirements, and server startup
file.

Keep exactly **one Machine in one region**. Transit connections are paired
in memory, and the mailbox uses one SQLite database. Scaling this app to
multiple Machines can split peers across different servers. Keep passing
`--ha=false` on future deployments.

## Storage and runtime

- One shared CPU and 1 GB RAM, with automatic stopping disabled.
- One encrypted 1 GB `mailbox_data` volume mounted at `/data`.
- Mailbox state in `/data/mailbox.sqlite`, retained across deployments.
- Both services share one Twisted process, configured in `server.tac`.
- Startup sets volume ownership, then drops to UID/GID 10001 before starting
  either service.
- TCP health checks on the transit listener and HTTP health checks on the
  mailbox listener.
- No optional usage database is enabled. Bulk files are streamed through the
  transit relay and are not saved to the mailbox volume.

Deployments and restarts interrupt active connections. Schedule updates while
idle. This single-Machine deployment does not provide high availability.
Fly's automatic volume snapshots are enabled with five days of retention.

## Verification and operations

Deployment verified on November 10, 2026 (Pacific time):

- One running Machine in `lax`, with both service health checks passing.
- Two wormhole-rs 0.8.1 processes transferred an 8 MiB random file through
  the public mailbox on port 4000 and transit relay on port 4001.
- Both clients used `--force-relay` and reported the custom relay at
  `169.155.48.77:4001`. Sender and receiver SHA-256 checksums matched.
- Public transit protocol pairing and bidirectional payload checks passed.
- The secure mailbox endpoint passed an independent certificate-verified TLS
  connection and HTTP 101 WebSocket upgrade check. The installed client
  cannot use `wss://` until it is rebuilt with TLS support.

Check public TCP pairing and bidirectional forwarding:

```bash
python3 check-relay.py erik-reed-wormhole.fly.dev
```

Expected output starts with `PASS`. This validates matching relay handshakes
and random payload forwarding in both directions, rather than just checking
whether the port is open.

Check the mailbox HTTP endpoint:

```bash
curl --fail https://erik-reed-wormhole.fly.dev/
```

Expected response: `Wormhole Relay`. Complete verification uses the send and
receive commands above with `--force-relay`, then compares the received file
with the original.

```bash
flyctl logs
flyctl checks list
flyctl status
flyctl ips list
flyctl volumes list
```

The app is publicly accessible, with no service-wide account or password.
Anyone who knows the endpoints can use the servers and consume bandwidth.
Monitor compute, volume, dedicated IPv4, snapshots, and outbound bandwidth
charges in the Fly billing dashboard. See [current Fly pricing](https://fly.io/docs/about/pricing/).

## Upstream documentation

- [Official mailbox server](https://github.com/magic-wormhole/magic-wormhole-mailbox-server)
- [Official transit relay](https://github.com/magic-wormhole/magic-wormhole-transit-relay)
- [wormhole-rs](https://github.com/magic-wormhole/magic-wormhole.rs)
- [Fly public networking](https://docs.fly.io/networking/services)
- [Fly app configuration](https://docs.fly.io/reference/configuration)
