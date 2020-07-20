#!/usr/bin/env python3

import cgi, mailcap, os, re, socket, ssl, tempfile, textwrap, urllib.parse, logging

width = 80
caps = mailcap.getcaps()
max_tries = 5

def absolutise_url(base, relative):
    if "://" not in relative:
        base = base.replace("gemini://","http://")
        relative = urllib.parse.urljoin(base, relative)
        relative = relative.replace("http://", "gemini://")
    return relative

class GeminiResponse:
    def __init__(self, url, status, meta, body=None):
        self.url = url
        self.status = status
        self.meta = meta
        self.body = body
        self.links, self.text = self.read_body()

    def read_body(self):
        if not self.body or not self.meta.startswith("text/"):
            return [],None

        mime, mime_opts = cgi.parse_header(self.meta)
        body = self.body.decode(mime_opts.get("charset","UTF-8"))

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

def get(url):
    if not "://" in url:
        url = "gemini://" + url

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
        s = context.wrap_socket(s, server_hostname = parsed_url.hostname)
        s.sendall((url + '\r\n').encode("UTF-8"))
        fp = s.makefile("rb")
        header = fp.readline()
        header = header.decode("UTF-8").strip()
        logging.warning(header)
        status, meta = header.split(maxsplit=1)
        if not re.match('^[0-9][0-9]$',status):
            return GeminiResponse(url, "40", f"Bad header '{header}'")
        if status.startswith("3"):
            url = absolutise_url(url, meta)
        else:
            break
    else:
        return GeminiResponse(url, "40", "Too many redirects")

    if not status.startswith("2"):
        return GeminiResponse(url, status, meta)

    return GeminiResponse(url, status, meta, fp.read())
