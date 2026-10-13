# Quickstart: validation scenarios

Run on the VM unless marked Mac. Order matches the plan.

1. **DNS**: `dig +short navaan.njlabs.dev` returns 163.192.110.178.
2. **Image builds and renders** (before anything else): `docker compose -f /opt/navaan/compose.yml build` then render the synthetic test song. Expect a valid mp4 with audio and a 16:9 cover, in under 10 minutes for 30 s.
3. **Vault ready** (Nj, own admin login): mount, policy, AppRole as in `deploy/vault/setup.md`; put secrets with the sync script's `push` command from files copied from the Mac. Check `docker logs navaan` shows `secrets: ok` and `ls -l` of the tmpfs shows mode 600 files.
4. **nginx wiring**: back up `/opt/engagehub/docker-compose.yml`, add the mount and network, `docker compose up -d nginx`, then `docker exec engagehub-nginx nginx -t`. Confirm EngageHub and Relayent health URLs still answer.
5. **Certificate**: `certbot certonly --webroot -w /var/www/certbot -d navaan.njlabs.dev --deploy-hook "docker exec engagehub-nginx nginx -s reload"`, then `certbot renew --cert-name navaan.njlabs.dev --dry-run`.
6. **Edge checks**: `curl -sI https://navaan.njlabs.dev/` gives 401 without the shared password; with it, 200 and the sign-in page; `curl -s -u gate:... https://navaan.njlabs.dev/api/settings` gives 401 JSON. Cookie has `Secure; HttpOnly; SameSite=Strict`.
7. **First-time setup**: read the setup code from the container (`docker exec navaan cat ~/.config/navaan/auth_setup_code`), create the login, sign out, sign in with authenticator code, with a recovery code, and with a passkey on the real domain.
8. **Throttle**: 40 quick requests without a cookie return 503/429 after the limit; with a session they do not.
9. **Sealed Vault drill**: seal Vault, `docker restart navaan`; the sign-in page reports secrets waiting and the scheduler stays paused; unseal; within 1 minute status is `ok`.
10. **Data move**: rsync songs, `analytics.db`, `navaan.config.json`; compare `ls songs | wc -l` and `sqlite3 analytics.db 'select count(*) from media'` with the Mac.
11. **Scheduled post with the Mac off**: set `NAVAAN_SCHEDULER=off` on the Mac, schedule a test item on the server a few minutes ahead, approve its gates, sleep the Mac, confirm it publishes once.
12. **Backup and restore**: run `backup.sh`, restore to a scratch directory, compare file counts.
13. **Rollback**: remove the mount and network from the nginx service, `docker compose up -d nginx`, EngageHub and Relayent still answer; the Mac studio still works.
