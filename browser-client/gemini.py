#!/usr/bin/env python3

import cgi, os, re, socket, ssl, textwrap, urllib.parse, logging

width = 80
max_tries = 5

def absolutise_url(base, relative):
    if "://" in relative:
        return relative
    if relative=="": # jetforce expects that this removes an existing query string, urljoin doesn't
        return base.split("?")[0]
    return urllib.parse.urljoin(base.replace("gemini://","http://"), relative).replace("http://", "gemini://")

class GeminiResponse:
    def __init__(self, url, status, meta, body=""):
        self.url = url
        self.status = status
        self.meta = meta
        self.body = body
        logging.info(f"{url} {status} {len(body)}")

    def __len__(self):
        return len(self.body or "")

    def decode_body(self):
        mime, mime_opts = cgi.parse_header(self.meta)
        return self.body.decode(mime_opts.get("charset","UTF-8"))

def get(url, ca_cert=None, client_cert=None, key=None):
    if not "://" in url:
        url = "gemini://" + url

    if ca_cert is not None or client_cert is not None or key is not None:
        if ca_cert is None or client_cert is None or key is None:
           return GeminiResponse(url, "60", "Need a CA certificate, client certificate and client key to proceed.")

    tries = 0
    while tries < max_tries:
        tries += 1
        logging.warning(f"get {url}")

        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme != "gemini":
            return GeminiResponse(url, "30", url)

        logging.warning(f"connecting to {parsed_url.hostname} port {parsed_url.port}")
        s = socket.create_connection((parsed_url.hostname, parsed_url.port or 1965))
        context = ssl.SSLContext()
        context.check_hostname = False

        context.verify_mode = ssl.CERT_NONE
        if client_cert:
            context.load_verify_locations(ca_cert)
            context.load_cert_chain(certfile=client_cert,keyfile=key)

        s = context.wrap_socket(s, server_hostname = parsed_url.hostname)
        s.sendall((url + '\r\n').encode("UTF-8"))
        fp = s.makefile("rb")
        header = fp.readline()
        header = header.decode("UTF-8").strip()
        logging.warning(header)

        status, meta = (header.split(maxsplit=1)+[""])[:2]
        if not re.match('^[0-9][0-9]$',status):
            return GeminiResponse(url, "40", f"Bad header '{status}'")
        if not status.startswith("3"):
            break
        url = absolutise_url(url, meta)
    else:
        return GeminiResponse(url, "40", "Too many redirects")

    if not status.startswith("2"):
        return GeminiResponse(url, status, meta)

    return GeminiResponse(url, status, meta, fp.read())
