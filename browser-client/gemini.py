#!/usr/bin/env python3

import cgi, mailcap, os, re, socket, ssl, tempfile, textwrap, urllib.parse, logging

width = 80
caps = mailcap.getcaps()
max_tries = 5

def absolutise_url(base, relative):
    if "://" in relative:
        return relative
    if relative=="": # jetforce expects that this removes an existing query string, urljoin doesn't
        return base.split("?")[0]
    return urllib.parse.urljoin(base.replace("gemini://","http://"), relative).replace("http://", "gemini://")

class GeminiResponse:
    def __init__(self, url, status, meta, body=None):
        self.url = url
        self.status = status
        self.meta = meta
        self.body = body
        self.links, self.text = self.read_body()

    def __len__(self):
        return len(self.body or "")

    def decode_body(self):
        mime, mime_opts = cgi.parse_header(self.meta)
        return self.body.decode(mime_opts.get("charset","UTF-8"))

    def read_body(self):
        if not self.body or not self.meta.startswith("text/"):
            return [],None

        body = self.decode_body()
        if not self.meta.startswith("text/gemini"):
            return [],body

        lines = []
        links = []
        pre = False
        for line in body.splitlines():
            if line.startswith("```"):
                pre = not pre
            elif pre:
                lines.append(line)
            elif line.startswith("=>") and line[2:].strip():
                bits = line[2:].strip().split(maxsplit=1)
                links.append( ( absolutise_url(self.url, bits[0]), bits[-1] ) )
                lines.extend(textwrap.wrap(line, width))
            else:
                lines.append(line)

        return links, "\n".join(lines)


    def display(self):
        if self.text:
            print(self.text)
            return

        tmpfp = tempfile.NamedTemporaryFile("wb", delete=False)
        tmpfp.write(self.body)
        tmpfp.close()

        cmd_str, _ = mailcap.findmatch(caps, mime, filename=tmpfp.name)
        os.system(cmd_str)
        os.unlink(tmpfp.name)

def respond(url, code, message, body=None):
    resp = GeminiResponse(url, code, message, body)
    logging.info(f"{url} {code} {len(resp)}")
    return resp

def get(url, ca_cert=None, client_cert=None, key=None):
    if not "://" in url:
        url = "gemini://" + url

    if ca_cert is not None or client_cert is not None or key is not None:
        if ca_cert is None or client_cert is None or key is None:
           return respond(url, "60", "Need a CA certificate, client certificate and client key to proceed.")

    tries = 0
    while tries < max_tries:
        tries += 1
        logging.warning(f"get {url}")

        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme != "gemini":
            return respond(url, "30", url)

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
            return respond(url, "40", f"Bad header '{status}'")
        if not status.startswith("3"):
            break
        url = absolutise_url(url, meta)
    else:
        return respond(url, "40", "Too many redirects")

    if not status.startswith("2"):
        return respond(url, status, meta)

    return respond(url, status, meta, fp.read())
