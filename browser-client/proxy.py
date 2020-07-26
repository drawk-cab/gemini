#!/usr/bin/python3

import bottle, gemini, logging, urllib.parse, os

CONFIG = os.environ.get("GEMINI_HOME",os.path.join(os.environ.get("HOME",""),".gemini"))

@bottle.route('/')
def app():
    return open("client.html","rb").read()

@bottle.route('/<fn:path>')
def serve(fn):
    bottle.response.content_type = "text/plain"

    proxied_url = fn+(bottle.request.query_string and "?"+bottle.request.query_string)
    resp = gemini.get(proxied_url)

    if resp.status.startswith("3"):
        logging.warning(f"Redirected out of Geminispace: {resp.meta}")
        bottle.redirect(resp.meta)
        return

    if resp.status.startswith("6"):
        p = urllib.parse.urlparse(proxied_url)
        cert_dir = os.path.join(CONFIG,p.netloc)

        if not os.path.isdir(cert_dir):
            bottle.response.status = 403
            return f"# {fn} required a client certificate but none was available"

        logging.info(f"Found a client certificate to use at {p.netloc}, retrying")
        ca_cert = os.path.join(cert_dir, "ca.pem")
        pem = os.path.join(cert_dir, "client.pem")
        key = os.path.join(cert_dir, "client.key")
        resp = gemini.get(proxied_url, ca_cert, pem, key)

    if resp.status.startswith("2") and resp.body:
        return resp.body

    if resp.status=="10":
        return f"# {resp.meta}\n\n?"

    return f"# {resp.status} {resp.meta}\n{resp.body or ''}"

bottle.run(host='localhost', port=1977)
