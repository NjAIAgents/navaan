"""objstore.py  the bucket through the OCI Python SDK: read, write, and short-lived links that let a browser fetch one object directly.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: NAV-6 stage 2. Replaces the `oci` command line call per link (a process start and a JSON parse per play) with the SDK; audio never passes through the app: the browser
gets a pre-authenticated request URL and talks to the bucket, which also serves Range requests.

Auth: OCI_CLI_AUTH=instance_principal (the production VM) uses the instance's identity; anything else reads the user's own ~/.oci/config, as the CLI does.
Links are cached per object for their lifetime (minus a margin), so a popular track makes one pre-authenticated request, not one per listener.
"""
import os, time, datetime, threading
import navaan_common as C
import navaan_log as L
LOG = L.get("objstore")

_LOCK = threading.Lock()
_CLIENT = None          # (client, namespace); tests put a fake here
_LINKS = {}             # (bucket, key) -> (url, expires_epoch)
MARGIN_S = 60


def _setting(name, default=""):
    return C.cfg("storage." + name, default)


def client():
    global _CLIENT
    with _LOCK:
        if _CLIENT is None:
            import oci
            if os.environ.get("OCI_CLI_AUTH") == "instance_principal":
                c = oci.object_storage.ObjectStorageClient({}, signer=oci.auth.signers.InstancePrincipalsSecurityTokenSigner())
            else:
                c = oci.object_storage.ObjectStorageClient(oci.config.from_file())
            _CLIENT = (c, c.get_namespace().data)
        return _CLIENT


def bucket():
    b = _setting("cloud_bucket")
    if not b or _setting("cloud_provider") != "oci": raise RuntimeError("the cloud bucket is not configured for oci")
    return b


def get(key):
    c, ns = client()
    return c.get_object(ns, bucket(), key).data.content


def put(key, data, content_type="application/octet-stream"):
    c, ns = client()
    c.put_object(ns, bucket(), key, data, content_type=content_type)


def par_url(key, seconds=300, now=None):
    """A URL that opens one object for `seconds`. Cached while it has more than a minute left."""
    now = now or time.time(); b = bucket()
    with _LOCK:
        hit = _LINKS.get((b, key))
        if hit and hit[1] - now > MARGIN_S: return hit[0]
    import oci
    c, ns = client()
    exp = datetime.datetime.fromtimestamp(now + seconds + MARGIN_S, datetime.timezone.utc)
    d = oci.object_storage.models.CreatePreauthenticatedRequestDetails(name=f"navaan-play-{int(now)}", access_type="ObjectRead", object_name=key, time_expires=exp)
    uri = c.create_preauthenticated_request(ns, b, d).data.access_uri
    url = f"https://objectstorage.{_setting('cloud_region') or 'us-chicago-1'}.oraclecloud.com{uri}"
    with _LOCK: _LINKS[(b, key)] = (url, now + seconds + MARGIN_S)
    return url
