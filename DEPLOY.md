# Timeweb deployment

GitHub Actions deploys `main` to the Timeweb server over SSH.

## Required GitHub repository secrets

- `TIMEWEB_HOST` — server IPv4 address
- `TIMEWEB_USER` — SSH user, normally `root`
- `TIMEWEB_SSH_KEY` — private Ed25519 key used only by GitHub Actions

Never commit the private key and never put it in source files.

## Server prerequisites

Docker and Docker Compose must already be installed.

The deployment workflow creates `/opt/marketplace-parser/repo`, pulls `main`, rebuilds the image and verifies `GET http://127.0.0.1:8010/health`.

## SSH key setup

Generate a dedicated deploy key on a trusted machine:

```bash
ssh-keygen -t ed25519 -C "github-actions-marketplace-parser" -f ~/.ssh/marketplace_parser_deploy
```

Add the public key (`marketplace_parser_deploy.pub`) to the server user's `~/.ssh/authorized_keys`. Add the private key contents to the GitHub secret `TIMEWEB_SSH_KEY`.
