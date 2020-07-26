#!/usr/bin/env python3
import sys, html, hashlib, gemini, urllib.parse
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, Gdk, WebKit2, Gio, GLib

start_tabs=sys.argv

STYLE = open("text.css","r").read()

NUMBERS = "123456789abcdefghijklmnopqrstuvwxyz"
KEYS = [ Gdk.KEY_1, Gdk.KEY_2, Gdk.KEY_3, Gdk.KEY_4, Gdk.KEY_5, Gdk.KEY_6,
         Gdk.KEY_7, Gdk.KEY_8, Gdk.KEY_9, Gdk.KEY_a, Gdk.KEY_b, Gdk.KEY_c,
         Gdk.KEY_d, Gdk.KEY_e, Gdk.KEY_f, Gdk.KEY_g, Gdk.KEY_h, Gdk.KEY_i,
         Gdk.KEY_j, Gdk.KEY_k, Gdk.KEY_l, Gdk.KEY_m, Gdk.KEY_n, Gdk.KEY_o,
         Gdk.KEY_p, Gdk.KEY_q, Gdk.KEY_r, Gdk.KEY_s, Gdk.KEY_t, Gdk.KEY_u,
         Gdk.KEY_v, Gdk.KEY_w, Gdk.KEY_x, Gdk.KEY_y, Gdk.KEY_z
]
REVKEYS = { k:n for n,k in enumerate(KEYS) }

def finish(rq,s,mime="text/html; charset=utf-8"):
    bs = Gio.MemoryInputStream.new()
    bs.add_bytes(GLib.Bytes.new(s.encode("utf-8")))
    rq.finish(bs,len(s),mime)

class Gemtext():
    def __init__(self, url, data):
        self.data = data
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
        print(self.data)
        for line in self.data.split("\n"):
            line = html.escape(line)
            if pre:
                if line.startswith("```"):
                    pre = False;
                    bits.append("</pre>"); continue
                else:
                    bits.append(line+"\n"); continue
            if line.startswith("```"):
                pre = True; bits.append("<pre>"); continue
            if line.startswith("*"):
                bits.append(f"<li>{line[1:]}</li>"); continue
            if line.startswith("###"):
                bits.append(f"<h3>{line[3:]}</h3>"); continue
            if line.startswith("##"):
                bits.append(f'<h2 class="bb">{line[2:]}</h2>'); continue
            if line.startswith("#"):
                bits.append(f'<h1 class="bb">{line[1:]}</h1>'); continue
            if line.startswith("=&gt;"):
                link = line[5:].split(maxsplit=1)
                count += 1
                if count<len(NUMBERS):
                    accesskey = f'accesskey="{NUMBERS[count]}"'
                else:
                    accesskey = ''
                bits.append(f'<p><a id="link-{count}" {accesskey} href="{link[0]}">{link[-1]}</a></p>'); continue
            bits.append(f"<p>{line}</p>"); continue
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
        self.webcontext.register_uri_scheme("gemini",lambda rq, *args: self._handle_schemerq(rq, *args))
        self.webcontext.register_uri_scheme("http",lambda rq, *args: self._handle_httprq(rq, *args))
        self.webview = WebKit2.WebView.new_with_context(self.webcontext)
        self._load_url(url)
        self.show()

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.webview)
        self.pack_start(scrolled_window, True, True, 0)
        scrolled_window.show_all()

    def _handle_schemerq(self, rq, *args):
        url = rq.get_uri()
        resp = gemini.get(url)

        if resp.status.startswith("2"):
            html = Gemtext(url,resp.decode_body()).html()
            finish(rq,html)
            return

        msg = f"# {resp.status} {resp.meta}\n## Not implemented yet, sorry."
        finish(rq,Gemtext(url,msg).html())

    def _handle_httprq(self, rq, *args):
        url = rq.get_uri()
        msg = f"# HTTP"
        finish(rq,Gemtext(url,msg).html())

    def _load_url(self, url):
        if url.startswith("gemini://"):
            self.webview.load_uri(url)
        elif "://" not in url:
            self.webview.load_uri("gemini://"+url)
        else:
            raise ValueError(url)




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
        for url in start_tabs[1:]:
          if "://" not in url:
              url = "gemini://"+url
          self.tabs.append((self._create_tab(url), Gtk.Label(urllib.parse.urlparse(url).netloc)))
          self.notebook.append_page(*self.tabs[-1])

        if not self.tabs:
          self.tabs.append((self._create_tab("drawk.cab"), Gtk.Label("drawk.cab")))
          self.notebook.append_page(*self.tabs[-1])

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
        if self.notebook.get_n_pages() == 1:
            return
        page = self.notebook.get_current_page()
        current_tab = self.tabs.pop(page)
        self.notebook.remove(current_tab[0])

    def _open_new_tab(self,url):
        current_page = self.notebook.get_current_page()
        page_tuple = (self._create_tab(url), Gtk.Label(url))
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
        tab = self.tabs[self.notebook.get_current_page()][0]
        if event.keyval in REVKEYS:
            tab.webview.run_javascript(f"""
window.location.href = document.getElementById('link-{REVKEYS[event.keyval]}').getAttribute("href");
            """)
        #elif event.keyval == Gdk.KEY_t: FIXME broken
        #    self._open_new_tab(tab.url)
        elif event.keyval == Gdk.KEY_BackSpace:
            tab.webview.go_back()
        elif event.keyval == Gdk.KEY_comma:
            tab.webview.go_back()
        elif event.keyval == Gdk.KEY_period:
            tab.webview.go_forward()
        elif event.keyval == Gdk.KEY_F5:
            tab.webview.reload()
        elif event.keyval == Gdk.KEY_F1:
            tab.webview.run_javascript("window.location.href='http://placekitten.com'")
        elif event.keyval == Gdk.KEY_F4:
            self._close_current_tab()
        elif event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()
        else:
            print(f"unhandled key {event.keyval}")


if __name__ == "__main__":
    Gtk.init(sys.argv)

    browser = Browser()

Gtk.main()
