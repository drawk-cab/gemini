#!/usr/bin/python3

import bottle, gemini, logging

@bottle.route('/')
def app():
    return open("client.html","rb").read()

@bottle.route('/<fn:path>')
def serve(fn):
    bottle.response.content_type = "text/plain"
    resp = gemini.get(fn)

    if resp.status.startswith("3"):
        logging.warning(f"Redirected out of Geminispace: {resp.meta}")
        bottle.redirect(resp.meta)
        return

    if resp.body:
        return resp.body

    return f"# {resp.status} {resp.meta}\n{resp.body or ''}"

bottle.run(host='localhost', port=1977)
