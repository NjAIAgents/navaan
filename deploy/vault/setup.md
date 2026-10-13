# Vault setup for NAVAAN (Nj runs this with his own admin login)

Creates a separate kv-v2 mount `navaan/`, a policy limited to it and an AppRole the container uses. Commands only: no value appears here, and none should be pasted into chat. Layout: `specs/001-run-navaan-on-server/contracts/vault-layout.md`.

Vault is `engagehub-vault` (file storage, Shamir 2 of 3, manual unseal). It must be unsealed first. All commands run on the VM as `ods`.

## 1. Admin login (your own, stays in the container's token file)
```sh
docker exec -it engagehub-vault vault login
```

## 2. Mount, policy, AppRole
```sh
docker exec engagehub-vault vault secrets enable -path=navaan -version=2 kv

docker exec -i engagehub-vault vault policy write navaan - <<'POLICY'
path "navaan/data/*"     { capabilities = ["create", "read", "update"] }
path "navaan/metadata/*" { capabilities = ["list", "read"] }
POLICY

docker exec engagehub-vault vault auth list | grep -q '^approle/' || docker exec engagehub-vault vault auth enable approle

docker exec engagehub-vault vault write auth/approle/role/navaan \
  token_policies=navaan token_ttl=1h token_max_ttl=4h secret_id_ttl=0 token_num_uses=0
```

## 3. Role id and secret id into Docker secret files (never printed)
```sh
sudo install -d -m 700 /opt/navaan/secrets
umask 077
docker exec engagehub-vault vault read  -field=role_id   auth/approle/role/navaan/role-id        | sudo tee /opt/navaan/secrets/vault_role_id   >/dev/null
docker exec engagehub-vault vault write -f -field=secret_id auth/approle/role/navaan/secret-id    | sudo tee /opt/navaan/secrets/vault_secret_id >/dev/null
sudo chown 10001 /opt/navaan/secrets/vault_role_id /opt/navaan/secrets/vault_secret_id    # the container user
sudo chmod 400   /opt/navaan/secrets/vault_role_id /opt/navaan/secrets/vault_secret_id
```
Rotate the secret id any time by repeating the second command and restarting the container.

## 4. Put the secrets in (from the Mac, task T024)
Reach Vault from the Mac with an ssh tunnel to the container's address, for example
`ssh -L 8200:$(ssh njPRD docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' engagehub-vault | head -n1):8200 njPRD`
(any other way you already use is fine), then:
```sh
export VAULT_ADDR=http://127.0.0.1:8200
vault login                                      # your admin login on the Mac
python3 deploy/vault_sync.py set-gate            # asks for the shared gate password, hidden; stores only its hash
python3 deploy/vault_sync.py push                # uploads the credential files found in ~/.config/navaan
```
`claude.env` holds one line, `CLAUDE_CODE_OAUTH_TOKEN=...` (from `claude setup-token`) or `ANTHROPIC_API_KEY=...`; create it in `~/.config/navaan/` with mode 600 before the push. `auth.json` is not pushed from the Mac: the server creates its own login on first run and writes it to Vault itself.

## 5. Check
Logs show `secrets: ok (N files ...)` (`docker logs navaan`). Files in the container's memory-only folder have mode 600:
`docker exec navaan ls -l /home/navaan/.config/navaan`

## After a VM reboot
Vault comes back sealed. Enter two unseal keys; the container notices within 15 seconds (the sign-in page says "secrets waiting" until then).
