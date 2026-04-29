# docker/

Production and dev Docker artifacts for emhass-contributions.

## Files

- `Dockerfile.prototypes` — layers our prototypes onto upstream EMHASS image
- `compose-prod.yml` — production deploy on Unraid
- `compose-dev.yml` — local dev / repro on a developer machine
- `entrypoint.sh` — wraps upstream entrypoint to import prototypes/

## Build chain

Two-stage build:

```bash
# Stage 1: build vanilla upstream EMHASS from submodule
PIN=$(cd ../upstream && git describe --tags)
docker build -t emhass-base:${PIN} -f ../upstream/Dockerfile ../upstream/

# Stage 2: layer our prototypes
docker build -t emhass-contrib/prod:${PIN}-c1 \
  -f Dockerfile.prototypes \
  --build-arg BASE_IMAGE=emhass-base:${PIN} \
  ..
```

(Note `..` for build context — the parent directory of `docker/` so the Dockerfile can `COPY prototypes/`.)

## Image tag scheme

`emhass-contrib/prod:<UPSTREAM_TAG>-c<CONTRIB_REV>`

- `<UPSTREAM_TAG>` = current submodule pin (e.g. `v0.17.2`)
- `<CONTRIB_REV>` = our iteration counter, bumped on every prod-bound change (e.g. `c1`, `c2`)

When we bump the submodule, we typically reset rev to `c1` (e.g. `v0.17.3-c1`).

## Running prod

```bash
docker compose -f compose-prod.yml up -d
```

Designed for Unraid. Mounts `/mnt/user/appdata/emhass/` as the data volume; same path as the legacy upstream container.

## Running dev

```bash
docker compose -f compose-dev.yml up
```

Runs on `:5050`, separate data path. Flags can be enabled via `compose-dev.yml`'s mounted `contrib-flags.yaml` for full prototype testing.
