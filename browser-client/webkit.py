#!/usr/bin/env python3

import sys, html, hashlib, gemini, urllib.parse, os, logging
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, Gdk, WebKit2, Gio, GLib

home_url=os.environ.get("GEMINI_HOME_URL","gemkit-builtin://go")
start_tabs=sys.argv[1:] or [home_url]

STYLE = open("text.css","r").read()

NUMBERS = "1234567890"
KEYS = [ Gdk.KEY_1, Gdk.KEY_2, Gdk.KEY_3, Gdk.KEY_4, Gdk.KEY_5, Gdk.KEY_6, Gdk.KEY_7, Gdk.KEY_8, Gdk.KEY_9, Gdk.KEY_0 ]
REVKEYS = { k:n for n,k in enumerate(KEYS) }

def finish(rq,s,mime="text/html; charset=utf-8"):
    bs = Gio.MemoryInputStream.new()
    bs.add_bytes(GLib.Bytes.new(s.encode("utf-8")))
    rq.finish(bs,len(s),mime)

class Gemtext():
    def __init__(self, url, data, has_input=False):
        self.data = data
        self.has_input = has_input
        netloc = urllib.parse.urlparse(url).netloc
        self.hash = int(hashlib.sha1(netloc.encode("us-ascii")).hexdigest(), 16)

    def get_colour(self, n):
        b = self.hash
        while n>0:
            n -= 1
            b = b / 1800000
        b = int(b)
        return f"hsl({b%360},{(b//360)%100}%,{((b//36000)%50)+50}%)"

    def html(self):
        pre = False
        count = -1
        bits=[]
        for line in self.data.split("\n"):
            line = html.escape(line)
            if pre:
                if line.startswith("```"):
                    pre = False;
                    bits.append("</pre>")
                else:
                    bits.append(line+"\n")
            elif line.startswith("```"):
                pre = True; bits.append("<pre>")
            elif line.startswith("*"):
                bits.append(f"<li>{line[1:]}</li>")
            elif line.startswith("###"):
                bits.append(f"<h3>{line[3:]}</h3>")
            elif line.startswith("##"):
                bits.append(f'<h2 class="bb">{line[2:]}</h2>')
            elif line.startswith("#"):
                bits.append(f'<h1 class="bb">{line[1:]}</h1>')
            elif line.startswith("=&gt;"):
                link = line[5:].split(maxsplit=1)
                count += 1
                if count<len(NUMBERS):
                    accesskey = f'accesskey="{NUMBERS[count]}"'
                else:
                    accesskey = ''
                bits.append(f'<p><a id="link-{count}" {accesskey} href="{link[0]}">{link[-1]}</a></p>')
            else:
                bits.append(f"<p>{line}</p>")
        if self.has_input:
            bits.append('<input id="input" type="text" autofocus></input>')
        return f"""
<html><style>{STYLE}
.bb {{ border-bottom-color: {self.get_colour(0)} }}
a {{ color: {self.get_colour(1)} }}
pre {{ color: {self.get_colour(0)} }}
</style><body onload="init()">{"".join(bits)}</body></html>
"""

class BrowserTab(Gtk.VBox):
    def __init__(self, url, *args, **kwargs):
        super(BrowserTab, self).__init__(*args, **kwargs)

        self.url = url
        self.webcontext = WebKit2.WebContext()
        self.webcontext.register_uri_scheme("gemini",lambda rq, *args: self._handle_gemini_rq(rq, *args))
        self.webcontext.register_uri_scheme("gemkit-builtin",lambda rq, *args: self._handle_builtin_rq(rq, *args))

        # FIXME these don't do anything, but I can't find an unregister API
        self.webcontext.register_uri_scheme("http",lambda rq, *args: self._handle_http_rq(rq, *args))
        self.webcontext.register_uri_scheme("https",lambda rq, *args: self._handle_http_rq(rq, *args))

        self.webview = WebKit2.WebView.new_with_context(self.webcontext)
        self.webview.grab_focus()
        self.first_link = 0
        self.has_input = False
        self.webview.load_uri(url)
        self.show()

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.webview)
        self.pack_start(scrolled_window, True, True, 0)
        scrolled_window.show_all()

    def _handle_builtin_rq(self, rq, *args):
        url = urllib.parse.urlparse(rq.get_uri())
        if url.netloc == "go":
            if url.query:
               self._handle_redirected_rq(rq, url.query)
            else:
                self.has_input = True
                finish(rq, Gemtext("","# Where next?", True).html())
        else:
            finish(rq, Gemtext("", "# Unrecognized builtin").html())

    def _handle_gemini_rq(self, rq, *args):
        self._handle_redirected_rq(rq, rq.get_uri())

    def _handle_redirected_rq(self, rq, url):
        resp = gemini.get(url)
        self.has_input = False
        if resp.status.startswith("2"):
            html = Gemtext(url,resp.decode_body()).html()
            finish(rq,html)
        elif resp.status.startswith("5"):
            finish(rq,Gemtext(url,f"# {resp.status} {resp.meta}\n").html())
        else:
            finish(rq,Gemtext(url,f"# {resp.status} {resp.meta}\nNot implemented").html())

    def _handle_http_rq(self, rq, *args):
        url = rq.get_uri()
        msg = f"# HTTP"
        finish(rq,Gemtext(url,msg).html())

    def _load_url(self,url):
        if "://" not in url:
             url = "gemini://"+url
        logging.warning(f"Opening {url}")
        self.webview.load_uri(url)

    def follow_link(self, n):
        self.webview.run_javascript(f"""
window.location.href = document.getElementById('link-{n+self.first_link}').href;
""")

    def advance_links(self):
        pass

    def go_help(self):
        self.webview.run_javascript("window.location.href='http://placekitten.com'")




class Browser(Gtk.Window):
    def __init__(self, *args, **kwargs):
        super(Browser, self).__init__(*args, **kwargs)

        # create notebook and tabs
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)

        # basic stuff
        self.tabs = []
        self.set_size_request(700, 700)

        # create a first, empty browser tab
        for url in start_tabs:
          self._open_new_tab(url)
          #tabs.append((self._create_tab(url), Gtk.Label(urllib.parse.urlparse(url).netloc)))
          #self.notebook.append_page(*self.tabs[-1])

        self.add(self.notebook)

        # connect signals
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self._key_pressed)
        self.notebook.connect("switch-page", self._tab_changed)

        self.notebook.show()
        self.show()

    def _tab_changed(self, notebook, current_page, index):
        if not index:
            return
        title = self.tabs[index][0].webview.get_title()
        if title:
            self.set_title(title)

    def _create_tab(self, url):
        tab = BrowserTab(url)
        return tab

    def _close_current_tab(self):
        page = self.notebook.get_current_page()
        current_tab = self.tabs.pop(page)
        self.notebook.remove(current_tab[0])

    def _open_new_tab(self,url):
        logging.warning(f"Opening new tab with {url}")
        if "://" not in url:
             url = "gemini://"+url
        current_page = self.notebook.get_current_page()
        label = Gtk.Label(urllib.parse.urlparse(url).netloc)
        page_tuple = (self._create_tab(url), label)
        self.tabs.insert(current_page + 1, page_tuple)
        self.notebook.insert_page(page_tuple[0], page_tuple[1],
            current_page + 1)
        self.notebook.set_current_page(current_page + 1)

    def _focus_url_bar(self):
        current_page = self.notebook.get_current_page()
        self.tabs[current_page][0].url_bar.grab_focus()

    def _raise_find_dialog(self):
        current_page = self.notebook.get_current_page()
        self.tabs[current_page][0].find_box.show_all()
        self.tabs[current_page][0].find_entry.grab_focus()

    def _key_pressed(self, widget, event):
        shift = event.state & Gdk.ModifierType.SHIFT_MASK
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        alt = event.state & Gdk.ModifierType.MOD1_MASK

        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()
        elif not self.tabs:
            if event.keyval in (Gdk.KEY_BackSpace, Gdk.KEY_comma, Gdk.KEY_less, Gdk.KEY_b):
                for url in start_tabs:
                    self._open_new_tab(url)
                return
            self._open_new_tab("gemkit-builtin://go")
            return

        tab = self.tabs[self.notebook.get_current_page()][0]

        def _new_tab_callback(so, result, *user_data):
            self._open_new_tab(tab.webview.run_javascript_finish(result).get_js_value().to_string())

        def _same_tab_callback(so, result, *user_data):
            tab._load_url(tab.webview.run_javascript_finish(result).get_js_value().to_string())

        if tab.has_input and (shift or not event.state):
            logging.warning("gak")
            tab.webview.run_javascript(f"""
document.getElementById('input').focus()
""")
            if event.keyval == Gdk.KEY_Return:
                tab.webview.run_javascript(f"""
document.getElementById('input').value
""", None, _same_tab_callback)
                return True
            return False

        if event.keyval in REVKEYS:
            if not event.state:
                tab.follow_link(REVKEYS[event.keyval])
            elif ctrl:
                tab.webview.run_javascript(f"""
document.getElementById('link-{REVKEYS[event.keyval]+tab.first_link}').href
""", None, _new_tab_callback)
            elif alt:
                self.notebook.set_current_page(REVKEYS[event.keyval])
        elif event.keyval in (Gdk.KEY_t, Gdk.KEY_Insert):
            tab.webview.run_javascript(f"""
window.location.href
""", None, _new_tab_callback)
        elif event.keyval in (Gdk.KEY_w, Gdk.KEY_Delete):
            self._close_current_tab()
        elif event.keyval == Gdk.KEY_Tab:
            if ctrl or not event.state:
                self.notebook.next_page()
            elif shift:
                self.notebook.prev_page()
        elif event.keyval in (Gdk.KEY_ISO_Left_Tab, Gdk.KEY_grave, Gdk.KEY_bracketleft, Gdk.KEY_p):
            self.notebook.prev_page()
        elif alt and event.keyval == Gdk.KEY_Page_Up:
            self.notebook.prev_page()
        elif event.keyval in (Gdk.KEY_bracketright, Gdk.KEY_n):
            self.notebook.next_page()
        elif alt and event.keyval == Gdk.KEY_Page_Down:
            self.notebook.next_page()
        elif event.keyval in (Gdk.KEY_BackSpace, Gdk.KEY_comma, Gdk.KEY_less, Gdk.KEY_b):
            tab.webview.go_back()
        elif event.keyval in (Gdk.KEY_period, Gdk.KEY_greater, Gdk.KEY_f):
            tab.webview.go_forward()
        elif event.keyval in (Gdk.KEY_F5, Gdk.KEY_r):
            tab.webview.reload()
        elif event.keyval == (Gdk.KEY_F1, Gdk.KEY_h):
            tab.go_help()
        elif event.keyval == Gdk.KEY_space:
            tab.advance_links()
        elif event.keyval == Gdk.KEY_g:
            self._open_new_tab("gemkit-builtin://go")
        elif event.keyval == Gdk.KEY_q:
            Gtk.main_quit()
        else:
            return False
        return True


if __name__ == "__main__":
    Gtk.init(sys.argv)

    browser = Browser()

Gtk.main()
