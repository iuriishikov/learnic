# syntax=docker/dockerfile:1.7

# Custom Caddy build. The stock image has no rate limiting, so we compile in the
# community rate-limit module via xcaddy. Everything else is vanilla Caddy.
# Pin caddy-ratelimit to a known-good version once you've confirmed one against
# this Caddy major (append @vX.Y.Z) for reproducible builds.
FROM caddy:2-builder AS builder
RUN xcaddy build --with github.com/mholt/caddy-ratelimit

FROM caddy:2-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
# Fail the build loudly if the rate-limit module didn't actually get compiled in
# (xcaddy can succeed while shipping a binary without the module on a fetch hiccup).
RUN caddy list-modules | grep -q rate_limit
