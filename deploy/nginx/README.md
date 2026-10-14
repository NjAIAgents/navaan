# nginx for navaan.njlabs.dev

NAVAAN shares the VM's existing `engagehub-nginx` (owns 80 and 443). Nothing about EngageHub or Relayent changes except the three lines below on the nginx service. All steps run on the VM as `ods`.

Files: `navaan.conf` (full vhost), `navaan-acme.conf` (stage 1, port 80 only).

## 0. Snapshot the neighbours first (task T041)
```sh
printf '%s\n' https://engagehub.ignorelist.com/ https://relayent.ignorelist.com/ https://relayent-demo.ignorelist.com/ | sudo tee /opt/navaan/neighbours.txt >/dev/null
deploy/check-neighbours.sh > /tmp/before.txt
```
(create `/opt/navaan` first if it does not exist yet)

## 1. Back up and create the host files
```sh
sudo cp -a /opt/engagehub/docker-compose.yml /opt/engagehub/docker-compose.yml.bak-$(date +%F)
sudo mkdir -p /opt/navaan/nginx /opt/navaan/data /opt/navaan/secrets
sudo cp deploy/nginx/navaan-acme.conf /opt/navaan/nginx/navaan.conf      # stage 1
sudo install -m 644 -o 10001 /dev/null /opt/navaan/nginx/htpasswd   # empty; the navaan container (uid 10001) fills it from Vault
sudo chown 10001 /opt/navaan/data    # the data folder is written by the container user
```

## 2. Edit `/opt/engagehub/docker-compose.yml` (nginx service only)
The service is `nginx` (container `engagehub-nginx`); its existing vhost mounts and the `relayent-network: {external: true, name: ...}` entry are the style to copy (research.md R10). Three additions:

```yaml
services:
  nginx:                       # the service named engagehub-nginx
    volumes:
      # ...existing mounts stay...
      - /opt/navaan/nginx/navaan.conf:/etc/nginx/conf.d/navaan.conf:ro   # added: vhost
      - /opt/navaan/nginx/htpasswd:/run/navaan/htpasswd:ro               # added: hash of the shared password
    networks:
      # ...existing networks stay...
      - navaan-network                                                  # added
networks:
  navaan-network:
    external: true
    name: navaan-network
```
The `navaan-network` network is created by `deploy/compose.yml`, so bring NAVAAN up once first (`docker compose -f deploy/compose.yml up -d`) or `docker network create navaan-network`.

Two mounts, not one: nginx reads the password hash from a file, so the vhost and the hash are separate files. Write the hash file in place (`tee`), never replace it with `mv`; a bind-mounted file that is replaced goes stale until the container restarts.

## 3. Apply and check
```sh
cd /opt/engagehub && docker compose up -d nginx
docker exec engagehub-nginx nginx -t
```
Then run `deploy/check-neighbours.sh > /tmp/after.txt; diff /tmp/before.txt /tmp/after.txt` (empty diff).

## 4. Certificate (task T015)
```sh
sudo certbot certonly --webroot -w /var/www/certbot -d navaan.njlabs.dev \
  --deploy-hook "docker exec engagehub-nginx nginx -s reload"
sudo certbot renew --cert-name navaan.njlabs.dev --dry-run
```
If another vhost's default server already answers `/.well-known/acme-challenge/` for unknown hosts, stage 1 is not needed.

## 5. Switch to the full vhost
```sh
sudo tee /opt/navaan/nginx/navaan.conf < deploy/nginx/navaan.conf >/dev/null    # in place, same inode
docker exec engagehub-nginx nginx -t && docker exec engagehub-nginx nginx -s reload
```
The htpasswd file is written in place by the navaan container (`vault_sync.py`) from the Vault secret `gate.htpasswd`, through a read-write bind mount of that one file. Until it has content, every request gets 401.

## Gate and throttle
Since 2026-10-14 there is no shared password at nginx (owner's decision: the studio login has a second factor). To switch it back on add `auth_basic "NAVAAN"; auth_basic_user_file /run/navaan/htpasswd;` to the 443 server block; the hash is still written from the Vault key `gate.htpasswd`.

`limit_req` slows guessing of the studio login to 30 requests a minute per IP (300 a minute if the client sends a session-shaped cookie). The studio itself locks out per IP after 5 wrong tries.

## Rollback
Remove the two mounts and the network from the nginx service, `cd /opt/engagehub && docker compose up -d nginx`, delete `/opt/navaan/nginx/navaan.conf`. DNS and the certificate can stay.
