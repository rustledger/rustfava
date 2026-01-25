# Deploying with Docker

## Quick Start (Pre-built Image)

The easiest way to run rustfava with Docker is using the pre-built image from GitHub Container Registry:

```bash
docker run -p 5000:5000 -v /path/to/ledger:/data ghcr.io/rustledger/rustfava /data/main.beancount
```

Then visit http://localhost:5000.

## Building Your Own Image

The Dockerfile in this directory allows you to build a custom rustfava image.

### Building

```bash
docker build -t rustfava .
```

To incorporate a new version of rustfava, use the `--no-cache` flag:

```bash
docker build --no-cache -t rustfava .
```

### Running

```bash
docker run --detach --name="rustfava" --publish 5000:5000 \
  --volume $(pwd)/ledger.beancount:/data/ledger.beancount \
  rustfava /data/ledger.beancount
```

Arguments explained:

- `--detach`: Run in the background as a daemon
- `--name`: Name for the container instance
- `--publish`: Expose container port 5000 to localhost:5000
- `--volume`: Mount your beancount file into the container

Visit http://localhost:5000 to access rustfava.

## Advanced Deployment

For production deployments with authentication and HTTPS, see the following sections.

### Reverse Proxy with Authentication

For a secure, authenticated deployment, use a reverse proxy like nginx or Caddy with OAuth2 authentication.

Example with [oauth2-proxy](https://github.com/oauth2-proxy/oauth2-proxy):

```bash
# Run rustfava
docker run --detach --name="rustfava" \
  --volume $(pwd)/ledger:/data \
  ghcr.io/rustledger/rustfava /data/main.beancount

# Run oauth2-proxy in front
docker run --detach --name="rustfava-auth" \
  --link rustfava \
  --publish 4180:4180 \
  quay.io/oauth2-proxy/oauth2-proxy \
  --upstream="http://rustfava:5000" \
  --provider=google \
  --client-id="YOUR_CLIENT_ID" \
  --client-secret="YOUR_CLIENT_SECRET" \
  --cookie-secret="YOUR_COOKIE_SECRET" \
  --email-domain="yourdomain.com"
```

### HTTPS with Let's Encrypt

For automatic HTTPS certificates, use [Caddy](https://caddyserver.com/) as a reverse proxy:

```yaml
# docker-compose.yml
services:
  rustfava:
    image: ghcr.io/rustledger/rustfava
    command: /data/main.beancount
    volumes:
      - ./ledger:/data

  caddy:
    image: caddy:2
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data

volumes:
  caddy_data:
```

```
# Caddyfile
your-domain.com {
    reverse_proxy rustfava:5000
}
```

Caddy automatically obtains and renews Let's Encrypt certificates.

### Docker Compose Example

A complete example with persistent data:

```yaml
# docker-compose.yml
services:
  rustfava:
    image: ghcr.io/rustledger/rustfava
    command: /data/main.beancount
    ports:
      - "5000:5000"
    volumes:
      - ./ledger:/data
    restart: unless-stopped
```

```bash
docker compose up -d
```
