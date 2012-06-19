#!/usr/bin/env python
#
# Copyright (C) 2012 Johannes 'josch' Schauer <j.schauer@email.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#TODO
# gettext
# get addressbar/title/tabtitle right

# no double entries for smbc
# drag&drop doesnt create new items

from gettext import gettext as _
from gi.repository import Gtk, GLib, GObject, GdkPixbuf, Pango, WebKit, Soup
import yaml
from urlparse import urlparse, urlunparse, urljoin
import feedparser
from lxml import etree
from cStringIO import StringIO
import shelve
import time
import datetime
import os, re

def get_time_pretty(time):
    """
    return a pretty string representation of time given in unix time
    """
    time = datetime.datetime.fromtimestamp(time)
    diff = datetime.datetime.now() - time

    today = datetime.datetime.combine(datetime.date.today(), datetime.time())
    yesterday = datetime.datetime.combine(datetime.date.today(), datetime.time())-datetime.timedelta(days=1)

    if time > today:
        return _("Today")+" "+time.strftime("%H:%M")
    elif time > yesterday:
        return _("Yesterday")+" "+time.strftime("%H:%M")
    elif diff.days < 7:
        return time.strftime("%a %H:%M")
    elif diff.days < 365:
        return time.strftime("%b %d %H:%M")
    else:
        return time.strftime("%b %d %Y")


def pixbuf_new_from_file_in_memory(data, size=None):
    """
    return a pixbuf of imagedata given by data
    optionally resize image to width/height tuple given by size
    """
    loader = GdkPixbuf.PixbufLoader()
    if size:
        loader.set_size(*size)
    loader.write(data)
    loader.close()
    return loader.get_pixbuf()

def find_shortcut_icon_link_in_html(data):
    """
    data is a html document that will be parsed by lxml.etree.HTMLParser()
    returns the href attribute of the first link tag containing a rel attribute
    that lists icon as one of its types
    """
    tree = etree.parse(StringIO(data), etree.HTMLParser())
    #for link in tree.xpath("//link[@rel='icon' or @rel='shortcut icon']/@href"):
    #    return link
    links = tree.findall("//link")
    for link in links:
        rel = link.attrib.get('rel')
        if not rel:
            continue
        if 'icon' not in rel.split():
            continue
        href = link.attrib.get('href')
        if not href:
            continue
        return href

def markup_escape_text(text):
    """
    use GLib.markup_escape_text to escape text for usage in pango markup
    fields.
    it will escape <, >, &, ' and " and some html entities
    """
    if not text:
        return ""
    return GLib.markup_escape_text(text.encode('utf-8'))

class TabLabel(Gtk.HBox):
    """A class for Tab labels"""

    __gsignals__ = {
        "close": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_OBJECT,))
        }

    def __init__ (self, title, child):
        """initialize the tab label"""
        Gtk.HBox.__init__(self)
        self.set_homogeneous(False)
        self.set_spacing(4)
        self.title = title
        self.child = child
        self.label = Gtk.Label(title)
        self.label.props.max_width_chars = 30
        self.label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.label.set_alignment(0.0, 0.5)

        icon = Gtk.Image.new_from_stock(Gtk.STOCK_ORIENTATION_PORTRAIT, Gtk.IconSize.BUTTON)
        close_image = Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU)
        close_button = Gtk.Button()
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        def _close_tab (widget, child):
            self.emit("close", child)
        close_button.connect("clicked", _close_tab, child)
        close_button.set_image(close_image)
        self.pack_start(icon, False, False, 0)
        self.pack_start(self.label, True, True, 0)
        self.pack_start(close_button, False, False, 0)

        self.set_data("label", self.label)
        self.set_data("close-button", close_button)

        def tab_label_style_set_cb (tab_label, style):
            context = tab_label.get_pango_context()
            metrics = context.get_metrics(tab_label.get_style().font_desc, context.get_language())
            char_width = metrics.get_approximate_digit_width()
            (_, width, height) = Gtk.icon_size_lookup(Gtk.IconSize.MENU)
            tab_label.set_size_request(20 * char_width/1024.0 + 2 * width, (metrics.get_ascent() + metrics.get_descent())/1024.0)
        self.connect("style-set", tab_label_style_set_cb)

    def set_label (self, text):
        """sets the text of this label"""
        self.label.set_label(text)

class ContentPane (Gtk.Notebook):

    __gsignals__ = {
        "focus-view-title-changed": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_OBJECT, GObject.TYPE_STRING,)),
        "progress-changed": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_FLOAT,)),
        "hover-link-changed": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_STRING,))
        }

    def __init__ (self):
        """initialize the content pane"""
        Gtk.Notebook.__init__(self)
        self.props.scrollable = True
        def _switch_page (notebook, page, page_num):
            child = self.get_nth_page(page_num)
            view = child.get_child()
            frame = view.get_main_frame()
            self.emit("focus-view-title-changed", frame, frame.props.title)
        self.connect("switch-page", _switch_page)

        self.show_all()
        self._hovered_uri = None

    def load_uri (self, text):
        """load the given uri in the current web view"""
        #child = self.get_nth_page(self.get_current_page())
        child = self.get_nth_page(0);
        view = child.get_child()
        view.load_uri(text)

    def load_string (self, text):
        """load the given uri in the current web view"""
        #child = self.get_nth_page(self.get_current_page())
        child = self.get_nth_page(0);
        view = child.get_child()
        view.load_string(text, "text/html", "utf-8", "")

    def back(self):
        child = self.get_nth_page(self.get_current_page())
        view = child.get_child()
        view.go_back()

    def forward(self):
        child = self.get_nth_page(self.get_current_page())
        view = child.get_child()
        view.go_forward()

    def refresh(self):
        child = self.get_nth_page(self.get_current_page())
        view = child.get_child()
        view.reload()

    def zoom_in(self):
        child = self.get_nth_page(self.get_current_page())
        view = child.get_child()
        view.zoom_in()

    def zoom_out(self):
        child = self.get_nth_page(self.get_current_page())
        view = child.get_child()
        view.zoom_out()

    def zoom_100(self):
        child = self.get_nth_page(self.get_current_page())
        view = child.get_child()
        if not (view.get_zoom_level() == 1.0):
            view.set_zoom_level(1.0)

    def set_focus(self):
        child = self.get_nth_page(self.get_current_page())
        view = child.get_child()
        view.grab_focus()

    def print_page(self):
        child = self.get_nth_page(self.get_current_page())
        view = child.get_child()
        mainframe = view.get_main_frame()
        mainframe.print_full(Gtk.PrintOperation(), Gtk.PrintOperationAction.PRINT_DIALOG);

    def new_tab (self, url=None):
        """creates a new page in a new tab"""
        # create the tab content
        web_view = WebKit.WebView()
        web_view.set_full_content_zoom(True)

        def _hovering_over_link_cb (view, title, uri):
            self._hovered_uri = uri
            self.emit("hover-link-changed", uri)

        web_view.connect("hovering-over-link", _hovering_over_link_cb)

        def _populate_page_popup_cb(view, menu):
            if self._hovered_uri:
                open_in_new_tab = Gtk.MenuItem()
                open_in_new_tab.set_label(_("Open Link in New Tab"))
                def _open_in_new_tab (menuitem, view):
                    self.new_tab(self._hovered_uri)
                open_in_new_tab.connect("activate", _open_in_new_tab, view)
                menu.insert(open_in_new_tab, 0)
                menu.show_all()
        web_view.connect("populate-popup", _populate_page_popup_cb)

        def _view_load_finished_cb(view, frame):
            child = self.get_nth_page(self.get_current_page())
            label = self.get_tab_label(child)
            title = frame.get_title()
            if not title:
                title = frame.get_uri()
            if title:
                label.set_label(title)
            #view.execute_script(open("youtube_html5_everywhere.user.js", "r").read())
            for path in [".", "/usr/share/pyferea"]:
                if not os.path.exists(path):
                    continue
                for f in [os.path.join(path, p) for p in os.listdir(path)]:
                    if not f.endswith(".js"): continue
                    if not os.path.isfile(f): continue
                    view.execute_script(open(f, "r").read())
            """
            dom = view.get_dom_document()
            head = dom.get_head()
            if not head:
                return
            style = dom.create_element("style")
            style.set_attribute("type", "text/css")
            style.set_text_content("* {color:green;}")
            head.append_child(style)
            """
        web_view.connect("load-finished", _view_load_finished_cb)

        def _title_changed_cb (view, frame, title):
            child = self.get_nth_page(self.get_current_page())
            label = self.get_tab_label(child)
            label.set_label(title)
            self.emit("focus-view-title-changed", frame, title)
        web_view.connect("title-changed", _title_changed_cb)

        def _progress_changed_cb(view, progress):
            self.emit("progress-changed", view.get_progress())
        web_view.connect("notify::progress", _progress_changed_cb)

        def _mime_type_policy_decision_requested_cb(view, frame, request, mime, policy):
            # to make downloads possible, handle policy decisions and download
            # everything that the webview cannot show
            if view.can_show_mime_type(mime):
                policy.use()
            else:
                policy.download()
            return True
        web_view.connect("mime-type-policy-decision-requested", _mime_type_policy_decision_requested_cb)

        def _download_requested_cb(view, download):
            # get download directory from $XDG_DOWNLOAD_DIR, then from user-dirs.dirs
            # then fall back to ~/Downloads
            download_dir = os.environ.get("XDG_DOWNLOAD_DIR")
            if not download_dir:
                xdg_config_home = os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config')
                user_dirs = os.path.join(xdg_config_home, "user-dirs.dirs")
                if os.path.exists(user_dirs):
                    match = re.search('XDG_DOWNLOAD_DIR="(.*?)"', open(user_dirs).read())
                    if match:
                        # TODO: what about $HOME_FOO or ${HOME}? how to parse that correctly?
                        download_dir = os.path.expanduser(match.group(1).replace('$HOME', '~'))
                if not download_dir:
                    download_dir = os.path.expanduser('~/Downloads')
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            # TODO: check if destination file exists
            download.set_destination_uri("file://"+download_dir+"/"+download.get_suggested_filename())

            def _status_changed_cb(download, status):
                if download.get_status().value_name == 'WEBKIT_DOWNLOAD_STATUS_CANCELLED':
                    print "download cancelled"
                elif download.get_status().value_name == 'WEBKIT_DOWNLOAD_STATUS_CREATED':
                    print "download created"
                elif download.get_status().value_name == 'WEBKIT_DOWNLOAD_STATUS_ERROR':
                    print "download error"
                elif download.get_status().value_name == 'WEBKIT_DOWNLOAD_STATUS_FINISHED':
                    print "download finished"
                elif download.get_status().value_name == 'WEBKIT_DOWNLOAD_STATUS_STARTED':
                    print "download started"
            download.connect('notify::status', _status_changed_cb)

            def _progress_changed_cb(download, progress):
                print "download", download.get_progress()*100, "%", download.get_current_size(), "bytes", download.get_elapsed_time(), "seconds"
            download.connect('notify::progress', _progress_changed_cb)

            print "download total size:", download.get_total_size()
            print "download uri:", download.get_uri()
            print "download destination:", download_dir+"/"+download.get_suggested_filename()

            return True
        web_view.connect("download-requested", _download_requested_cb)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.props.hscrollbar_policy = Gtk.PolicyType.AUTOMATIC
        scrolled_window.props.vscrollbar_policy = Gtk.PolicyType.AUTOMATIC
        scrolled_window.add(web_view)

        # create the tab
        label = TabLabel(url, scrolled_window)
        def _close_tab (label, child):
            page_num = self.page_num(child)
            if page_num != -1:
                view = child.get_child()
                view.destroy()
                self.remove_page(page_num)
            self.set_show_tabs(self.get_n_pages() > 1)
        label.connect("close", _close_tab)
        label.show_all()

        new_tab_number = self.append_page(scrolled_window, label)
        #self.set_tab_label_packing(scrolled_window, False, False, Gtk.PACK_START)
        self.set_tab_label(scrolled_window, label)

        # hide the tab if there's only one
        self.set_show_tabs(self.get_n_pages() > 1)

        self.show_all()
        self.set_current_page(new_tab_number)

        # load the content
        self._hovered_uri = None
        if not url:
            web_view.load_uri("about:blank")
        else:
            web_view.load_uri(url)


class WebToolbar(Gtk.Toolbar):

    __gsignals__ = {
        "load-requested": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_STRING,)),
        "back-requested": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        "forward-requested": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        "refresh-requested": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        "new-tab-requested": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        "zoom-in-requested": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        "zoom-out-requested": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        "zoom-100-requested": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        "print-requested": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        }

    def __init__(self):
        Gtk.Toolbar.__init__(self)

        self.set_style(Gtk.ToolbarStyle.ICONS)

        backButton = Gtk.ToolButton()
        backButton.set_stock_id(Gtk.STOCK_GO_BACK)
        def back_cb(button):
            self.emit("back-requested")
        backButton.connect("clicked", back_cb)
        self.insert(backButton, -1)

        forwardButton = Gtk.ToolButton()
        forwardButton.set_stock_id(Gtk.STOCK_GO_FORWARD)
        def forward_cb(button):
            self.emit("forward-requested")
        forwardButton.connect("clicked", forward_cb)
        self.insert(forwardButton, -1)

        self._entry = Gtk.Entry()
        def entry_activate_cb(entry):
            self.emit("load-requested", entry.props.text)
        self._entry.connect('activate', entry_activate_cb)
        entry_item = Gtk.ToolItem()
        entry_item.set_expand(True)
        entry_item.add(self._entry)
        self._entry.show()
        self.insert(entry_item, -1)

        refreshButton = Gtk.ToolButton()
        refreshButton.set_stock_id(Gtk.STOCK_REFRESH)
        def refresh_cb(button):
            self.emit("refresh-requested")
        refreshButton.connect("clicked", refresh_cb)
        self.insert(refreshButton, -1)

        zoom_in_button = Gtk.ToolButton()
        zoom_in_button.set_stock_id(Gtk.STOCK_ZOOM_IN)
        def zoom_in_cb(button):
            self.emit("zoom-in-requested")
        zoom_in_button.connect('clicked', zoom_in_cb)
        self.insert(zoom_in_button, -1)

        zoom_out_button = Gtk.ToolButton()
        zoom_out_button.set_stock_id(Gtk.STOCK_ZOOM_OUT)
        def zoom_out_cb(button):
            self.emit("zoom-out-requested")
        zoom_out_button.connect('clicked', zoom_out_cb)
        self.insert(zoom_out_button, -1)

        zoom_100_button = Gtk.ToolButton()
        zoom_100_button.set_stock_id(Gtk.STOCK_ZOOM_100)
        def zoom_hundred_cb(button):
            self.emit("zoom-100-requested")
        zoom_100_button.connect('clicked', zoom_hundred_cb)
        self.insert(zoom_100_button, -1)

        print_button = Gtk.ToolButton()
        print_button.set_stock_id(Gtk.STOCK_PRINT)
        def print_cb(button):
            self.emit("print-requested")
        print_button.connect('clicked', print_cb)
        self.insert(print_button, -1)

        addTabButton = Gtk.ToolButton()
        addTabButton.set_stock_id(Gtk.STOCK_ADD)
        def add_tab_cb(button):
            self.emit("new-tab-requested")
        addTabButton.connect("clicked", add_tab_cb)
        self.insert(addTabButton, -1)

    def location_set_text (self, text):
        self._entry.set_text(text)
        self._entrytext = text

    def location_set_progress(self, progress):
        self._entry.set_progress_fraction(progress%1)

    def show_hover_uri(self, uri):
        if uri:
            self._entrytext = self._entry.get_text()
            self._entry.set_text(uri)
        else:
            self._entry.set_text(self._entrytext)


class EntryTree(Gtk.TreeView):
    __gsignals__ = {
        "item-selected": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_STRING, GObject.TYPE_STRING))
    }

    def __init__(self, config, feeddb):
        Gtk.TreeView.__init__(self)

        self.feeddb = feeddb

        def on_cursor_changed_cb(treeview):
            _, it = self.get_selection().get_selected()
            if not it: return
            item = self.get_model().get_value(it, 0)
            entry = self.feeddb[self.feedurl]
            if entry['items'][item]['unread']:
                title = markup_escape_text(entry['items'][item]['title'])
                date = get_time_pretty(entry['items'][item]['date'])
                self.get_model().set_value(it, 1, title)
                self.get_model().set_value(it, 2, date)
                entry['items'][item]['unread'] = False
                entry['unread'] -= 1
                self.feeddb[self.feedurl] = entry
                #self.feeddb.sync() # dont sync on every unread item - makes stuff extremely slow over time
            self.emit("item-selected", self.feedurl, item)
        self.connect("cursor-changed", on_cursor_changed_cb)

        self.models = dict()
        # id, date, label
        self.empty_model = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING)

        cell = Gtk.CellRendererText()
        column1 = Gtk.TreeViewColumn("Date", cell, markup=2)
        #column1.set_sort_column_id(0)
        column2 = Gtk.TreeViewColumn("Headline", cell, markup=1)
        #column2.set_sort_column_id(1)
        self.append_column(column1)
        self.append_column(column2)
        self.set_model(self.empty_model)
        self.feedurl = None

        for feedurl in config:
            if self.feeddb.get(feedurl):
                self.update(feedurl)

    def display(self, feedurl):
        if not feedurl or feedurl not in self.feeddb:
            self.set_model(self.empty_model)
            self.feedurl = None
        else:
            self.set_model(self.models[feedurl])
            self.feedurl = feedurl

    def update(self, feedurl):
        model = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_STRING)
        # using model.set_sort_column_id is horribly slow, so append them
        # sorted instead
        items = sorted(self.feeddb[feedurl]['items'].iteritems(), key=lambda x: x[1]['date'], reverse=True)
        for guid, value in items:
            title = markup_escape_text(value.get('title', ""))
            date = get_time_pretty(value['date'])
            if value['unread']:
                title = "<b>"+title+"</b>"
                date = "<b>"+date+"</b>"
            model.append([guid, title, date])
        def compare_date(model, a, b, data):
            item1 = model.get_value(a, 0)
            item2 = model.get_value(b, 0)
            items = self.feeddb[feedurl]['items']
            return -1 if items[item1]['date'] < items[item2]['date'] else 1
        #model.set_sort_func(0, compare_date)
        def compare_title(model, a, b, data):
            item1 = model.get_value(a, 0)
            item2 = model.get_value(b, 0)
            items = self.feeddb[feedurl]['items']
            return -1 if items[item1]['title'] < items[item2]['title'] else 1
        #model.set_sort_func(1, compare_title) # deactivate both sortings as it takes too long if accidentally clicked
        # this takes loooooong
        #model.set_sort_column_id(0, Gtk.SortType.DESCENDING)
        self.models[feedurl] = model
        if self.feedurl == feedurl:
            self.set_model(model)

class FeedTree(Gtk.TreeView):
    __gsignals__ = {
        "refresh-begin": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        "refresh-complete": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        "feed-selected": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_STRING,)),
        "update-feed": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_STRING,))
    }

    def __init__(self, config, feeddb):
        Gtk.TreeView.__init__(self)

        self.updating = set()
        self.feeddb = feeddb

        def on_button_press_event(treeview, event):
            if event.button != 3: return False
            pthinfo = self.get_path_at_pos(event.x, event.y)
            if pthinfo is None: return False
            path, col, cellx, celly = pthinfo
            #self.grab_focus()
            #self.set_cursor(path, col, 0)
            it = self.model.get_iter(path)
            popup = self.model.get_value(it, 3)
            popup.popup(None, None, None, None, event.button, event.time)
            #return True
        self.connect("button_press_event", on_button_press_event)

        def on_cursor_changed_cb(treeview):
            _, it = self.get_selection().get_selected()
            if it:
                self.emit("feed-selected", self.model.get_value(it, 0))
        self.connect("cursor-changed", on_cursor_changed_cb)

        error_icon = self.render_icon(Gtk.STOCK_DIALOG_ERROR, Gtk.IconSize.MENU, None)
        folder_icon = self.render_icon(Gtk.STOCK_DIRECTORY, Gtk.IconSize.MENU, None)

        # url, label, icon, popup
        self.model = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_STRING, GdkPixbuf.Pixbuf, Gtk.Menu)

        # reorganize configuration data into categories
        categories = dict()
        for feedurl, feedprops in config.items():
            if feedprops['category'] not in categories:
                categories[feedprops['category']] = list()
            categories[feedprops['category']].append(feedurl)

        for category, feeds in categories.items():
            it = self.model.append(None, [None, category, folder_icon, None])
            for feedurl in feeds:
                if self.feeddb.get(feedurl):
                    feed_icon = self.feeddb[feedurl].get('favicon')
                    if feed_icon:
                        feed_icon = pixbuf_new_from_file_in_memory(feed_icon, (16, 16))
                    else:
                        feed_icon = self.render_icon(Gtk.STOCK_FILE, Gtk.IconSize.MENU, None)

                    label = markup_escape_text(self.feeddb[feedurl].get('title', feedurl))
                    unread = self.feeddb[feedurl].get('unread')
                    if unread > 0:
                        label = "<b>"+label+" (%d)"%unread+"</b>"
                else:
                    feed_icon = error_icon
                    label = feedurl
                # append new item to category
                # use resulting iter to update popup menu entry
                itc = self.model.append(it, [feedurl, label, feed_icon, None])
                self.model.set_value(itc, 3, self.get_popup_menu(itc))

        column = Gtk.TreeViewColumn("Feeds")
        col_cell_img = Gtk.CellRendererPixbuf()
        col_cell_text = Gtk.CellRendererText()
        column.pack_start(col_cell_img, False)
        column.pack_start(col_cell_text, True)
        column.add_attribute(col_cell_text, "markup", 1)
        column.add_attribute(col_cell_img, "pixbuf", 2)

        self.set_model(self.model)
        self.append_column(column)
        self.set_headers_visible(False)
        self.expand_all()
        self.show()

        self.session = Soup.SessionAsync.new()

    def mark_read_all(self):
        it = self.model.get_iter_first()
        while (it):
            itc = self.model.iter_children(it)
            while (itc):
                self.mark_read(itc, sync=False)
                itc = self.model.iter_next(itc)
            it = self.model.iter_next(it)
        self.feeddb.sync()

    def mark_read(self, it, sync=True):
        feedurl = self.model.get_value(it, 0)
        entry = self.feeddb.get(feedurl)
        if not entry: return
        entry['unread'] = 0
        for item in entry['items'].values():
            item['unread'] = False
        self.model.set_value(it, 1, markup_escape_text(entry['title']))
        self.feeddb[feedurl] = entry
        self.emit("update-feed", feedurl)
        if sync:
            self.feeddb.sync()

    def disable_context_update(self):
        it = self.model.get_iter_first()
        while (it):
            itc = self.model.iter_children(it)
            while (itc):
                self.model.get_value(itc, 3).deactivate_update()
                itc = self.model.iter_next(itc)
            it = self.model.iter_next(it)

    def get_popup_menu(self, it):
        popup = Gtk.Menu()
        feedurl = self.model.get_value(it, 0)

        update_item = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_REFRESH, None)
        update_item.set_label(_("Update"))
        def on_update_item_activate_cb(menuitem):
            self.emit("refresh-begin")
            self.disable_context_update()
            self.updating.add(feedurl)
            self.update_feed(it)
        update_item.connect("activate", on_update_item_activate_cb)

        mark_item = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_APPLY, None)
        mark_item.set_label(_("Mark As Read"))
        def on_mark_item_activate_cb(menuitem):
            self.mark_read(it, sync=True)
            self.emit("update-feed", feedurl)
        mark_item.connect("activate", on_mark_item_activate_cb)

        popup.deactivate_update = lambda: update_item.set_sensitive(False)
        popup.activate_update = lambda: update_item.set_sensitive(True)
        popup.append(update_item)
        popup.append(mark_item)
        popup.show_all()
        return popup

    def update_view_all(self):
        it = self.model.get_iter_first()
        while (it):
            itc = self.model.iter_children(it)
            while (itc):
                feedurl = self.model.get_value(itc, 0)
                title = markup_escape_text(self.feeddb[feedurl]['title'])
                unread = self.feeddb[feedurl]['unread']
                if unread > 0:
                    title = "<b>"+title+" (%d)"%unread+"</b>"
                self.model.set_value(itc, 1, title)
                itc = self.model.iter_next(itc)
            it = self.model.iter_next(it)

    def update_feed_all(self):
        self.emit("refresh-begin")

        # disable updating via context menu
        self.disable_context_update()

        it = self.model.get_iter_first()
        while (it):
            # add feedurls to self.updating so that each feed can remove itself
            # from it once it is done and the last feed knows to take cleanup
            # actions
            itc = self.model.iter_children(it)
            while (itc):
                self.updating.add(self.model.get_value(itc, 0))
                itc = self.model.iter_next(itc)

            itc = self.model.iter_children(it)
            while (itc):
                self.update_feed(itc)
                itc = self.model.iter_next(itc)
            it = self.model.iter_next(it)

    def update_feed_done(self, feedurl):
        self.updating.remove(feedurl)
        if self.updating: return
        self.feeddb.sync()

        # enable updating via context menu
        it = self.model.get_iter_first()
        while (it):
            itc = self.model.iter_children(it)
            while (itc):
                self.model.get_value(itc, 3).activate_update()
                itc = self.model.iter_next(itc)
            it = self.model.iter_next(it)
        # enable updating
        self.emit("refresh-complete")

    def update_feed(self, it):
        feedurl = self.model.get_value(it, 0)
        msg = Soup.Message.new("GET", feedurl)
        if self.feeddb.get(feedurl) and self.feeddb[feedurl].get('etag'):
            msg.request_headers.append('If-None-Match', self.feeddb[feedurl]['etag'])
        if self.feeddb.get(feedurl) and self.feeddb[feedurl].get('lastmodified'):
            msg.request_headers.append('If-Modified-Since', self.feeddb[feedurl]['lastmodified'])

        def complete_cb(session, msg, it):
            if msg.status_code not in [200, 304]:
                error_icon = self.render_icon(Gtk.STOCK_DIALOG_ERROR, Gtk.IconSize.MENU, None)
                self.model.set_value(it, 2, error_icon)
                self.update_feed_done(feedurl)
                return

            # get existing feedentry or create new one
            entry = self.feeddb.get(feedurl, dict())

            if entry.get('favicon'):
                icon = pixbuf_new_from_file_in_memory(entry['favicon'], (16, 16))
            else:
                icon = self.render_icon(Gtk.STOCK_FILE, Gtk.IconSize.MENU, None)
            self.model.set_value(it, 2, icon)

            if msg.status_code == 304:
                self.update_feed_done(feedurl)
                return

            # filling default values
            if not entry.has_key('unread'):
                entry['unread'] = 0
            if not entry.has_key('items'):
                entry['items'] = dict()

            # updating etag and lastmodified
            if msg.response_headers.get_one('ETag'):
                entry['etag'] = msg.response_headers.get_one('ETag')
            if msg.response_headers.get_one('Last-Modified'):
                entry['lastmodified'] = msg.response_headers.get_one('Last-Modified')

            try:
                feed = feedparser.parse(msg.response_body.flatten().get_data())
            except:
                print "error parsing feed:"
                print msg.response_body.flatten().get_data()
                error_icon = self.render_icon(Gtk.STOCK_DIALOG_ERROR, Gtk.IconSize.MENU, None)
                self.model.set_value(it, 2, error_icon)
                self.update_feed_done(feedurl)
                return

            if feed.bozo != 0:
                # retrieved data was no valid feed
                error_icon = self.render_icon(Gtk.STOCK_DIALOG_ERROR, Gtk.IconSize.MENU, None)
                self.model.set_value(it, 2, error_icon)
                self.update_feed_done(feedurl)
                return

            entry['title'] = feed.feed.get('title')
            self.model.set_value(it, 1, markup_escape_text(entry['title']))

            # assumption: favicon never changes
            if not entry.has_key('favicon'):
                self.updating.add(feedurl+"_icon")
                self.update_icon(it, feedurl)

            for item in feed.entries:
                # use guid with fallback to link as identifier
                itemid = item.get("id", item.get("link"))
                if not itemid:
                    # TODO: display error "cannot identify feeditems"
                    break

                if entry['items'].has_key(itemid):
                    # already exists
                    continue

                new_item = {
                    'link': item.get('link'),
                    'title': item.get('title'),
                    'date': item.get('published_parsed'),
                    'content': item.get('content'),
                    'categories': [cat for _, cat in item.get('categories', [])] or None,
                    'unread': True
                }

                if not new_item['date']:
                    new_item['date'] = item.get('updated_parsed')

                if new_item['date']:
                    new_item['date'] = int(time.mktime(new_item['date']))
                else:
                    new_item['date'] = int(time.time())

                if new_item['content']:
                    new_item['content'] = new_item['content'][0]
                else:
                    new_item['content'] = item.get('summary_detail')

                if new_item['content']:
                    new_item['content'] = new_item['content']['value']
                else:
                    new_item['content'] = ""

                entry['items'][itemid] = new_item

                entry['unread'] += 1

            if entry['unread'] > 0:
                self.model.set_value(it, 1, '<b>'+markup_escape_text(entry['title'])+" (%d)"%entry['unread']+'</b>')

            self.feeddb[feedurl] = entry

            self.emit("update-feed", feedurl)

            self.update_feed_done(feedurl)
        self.session.queue_message(msg, complete_cb, it)

    def update_icon(self, it, feedurl):
        msg = Soup.Message.new("GET", feedurl)
        def complete_cb(session, msg, it):
            if msg.status_code == 200:
                icon_url = find_shortcut_icon_link_in_html(msg.response_body.flatten().get_data())
                if icon_url:
                    icon_url = urljoin(feedurl, icon_url)
                    self.update_icon_link(it, feedurl, icon_url)
                else:
                    self.update_icon_favicon(it, feedurl)
            else:
                self.update_icon_favicon(it, feedurl)
        self.session.queue_message(msg, complete_cb, it)

    # get shortcut icon from link rel
    def update_icon_link(self, it, feedurl, url):
        msg = Soup.Message.new("GET", url)
        def complete_cb(session, msg, it):
            if msg.status_code == 200:
                data = msg.response_body.flatten().get_data()
                if len(data):
                    icon = pixbuf_new_from_file_in_memory(data, (16, 16))
                    entry = self.feeddb[feedurl]
                    entry['favicon'] = data
                    self.feeddb[feedurl] = entry
                    self.model.set_value(it, 2, icon)
                    self.update_feed_done(feedurl)
                else:
                    self.update_icon_favicon(it, feedurl)
            else:
                self.update_icon_favicon(it, feedurl)
        self.session.queue_message(msg, complete_cb, it)

    # get /favicon.ico
    def update_icon_favicon(self, it, feedurl):
        url = urlparse(feedurl)
        url = urlunparse((url.scheme, url.netloc, 'favicon.ico', '', '', ''))
        msg = Soup.Message.new("GET", url)
        def complete_cb(session, msg, it):
            data = None
            if msg.status_code == 200:
                data = msg.response_body.flatten().get_data()
                if len(data):
                    icon = pixbuf_new_from_file_in_memory(data, (16, 16))
                else:
                    icon = self.render_icon(Gtk.STOCK_FILE, Gtk.IconSize.MENU, None)
            else:
                icon = self.render_icon(Gtk.STOCK_FILE, Gtk.IconSize.MENU, None)
            entry = self.feeddb[feedurl]
            entry['favicon'] = data
            self.feeddb[feedurl] = entry
            self.model.set_value(it, 2, icon)
            self.update_feed_done(feedurl+"_icon")
        self.session.queue_message(msg, complete_cb, it)


class FeedReaderWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)

        # try the following paths for pyferea.db in this order
        xdg_data_home = os.environ.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')
        feeddb_paths = [
            "./pyferea.db",
            os.path.join(xdg_data_home, "pyferea", "pyferea.db"),
        ]
        feeddb = None
        for path in feeddb_paths:
            if os.path.exists(path):
                feeddb = shelve.open(path)
                break
        if not feeddb:
            print "cannot find pyferea.db in any of the following locations:"
            for path in feeddb_paths:
                print path
            print "creating new db at %s"%feeddb_paths[0]
            feeddb = shelve.open(feeddb_paths[0])

        # try the following paths for feeds.yaml in this order
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config')
        feeds_paths = [
            "./feeds.yaml",
            os.path.join(xdg_config_home, "pyferea", "feeds.yaml"),
            "/usr/share/pyferea/feeds.yaml.example"
        ]
        conig = None
        for path in feeds_paths:
            if os.path.exists(path):
                with open(path) as f:
                    config = yaml.load(f)
                break
        if not config:
            print "cannot find feeds.yaml in any of the following locations:"
            for path in feeds_paths:
                print path
            exit(1)

        toolbar = WebToolbar()

        def load_requested_cb(widget, text):
            if not text:
                return
            content_pane.load_uri(text)
        toolbar.connect("load-requested", load_requested_cb)

        def new_tab_requested_cb(toolbar):
            content_pane.new_tab("about:blank")
        toolbar.connect("new-tab-requested", new_tab_requested_cb)

        def back_requested_cb(toolbar):
            content_pane.back()
        toolbar.connect("back-requested", back_requested_cb)

        def forward_requested_cb(toolbar):
            content_pane.forward()
        toolbar.connect("forward-requested", forward_requested_cb)

        def refresh_requested_cb(toolbar):
            content_pane.refresh()
        toolbar.connect("refresh-requested", refresh_requested_cb)

        def zoom_in_requested_cb(toolbar):
            content_pane.zoom_in()
        toolbar.connect("zoom-in-requested", zoom_in_requested_cb)

        def zoom_out_requested_cb(toolbar):
            content_pane.zoom_out()
        toolbar.connect("zoom-out-requested", zoom_out_requested_cb)

        def zoom_100_requested_cb(toolbar):
            content_pane.zoom_100()
        toolbar.connect("zoom-100-requested", zoom_100_requested_cb)

        def print_requested_cb(toolbar):
            content_pane.print_page()
        toolbar.connect("print-requested", print_requested_cb)

        content_pane = ContentPane()
        def title_changed_cb (tabbed_pane, frame, title):
            if not title:
               title = frame.get_uri()
            self.set_title(_("PyFeRea - %s") % title)
            uri = frame.get_uri()
            if uri:
                toolbar.location_set_text(uri)
        content_pane.connect("focus-view-title-changed", title_changed_cb)

        def progress_changed_cb(pane, progress):
            toolbar.location_set_progress(progress)
        content_pane.connect("progress-changed", progress_changed_cb)

        def hover_link_changed_cb(pane, uri):
            toolbar.show_hover_uri(uri)
        content_pane.connect("hover-link-changed", hover_link_changed_cb)

        entries = EntryTree(config, feeddb)

        def item_selected_cb(entry, feedurl, item):
            item = feeddb[feedurl]['items'][item]
            if config[feedurl]['loadlink']:
                content_pane.load_uri(item['link'])
            else:
                if item.get('categories'):
                    content_string = "<h1>%s</h1><p>%s</p>"%(item['title'], ', '.join(item['categories']))
                else:
                    content_string = "<h1>%s</h1>"%item['title']
                content_pane.load_string(content_string+item['content'])
                toolbar.location_set_text(item['link'])
                self.set_title(_("PyFeRea - %s")%item['title'])
            feedtree.update_view_all()
        entries.connect("item-selected", item_selected_cb)

        feedtree = FeedTree(config, feeddb)

        def feed_selected_cb(feedtree, feedurl):
            entries.display(feedurl)
        feedtree.connect("feed-selected", feed_selected_cb)

        def update_feed_cb(feedtree, feedurl):
            entries.update(feedurl)
        feedtree.connect("update-feed", update_feed_cb)

        def refresh_begin_cb(feedtree):
            button_refresh.set_label(_("Updating..."))
            button_refresh.set_sensitive(False)
        feedtree.connect("refresh-begin", refresh_begin_cb)
        def refresh_complete_cb(feedtree):
            button_refresh.set_label(_("Update All"))
            button_refresh.set_sensitive(True)
        feedtree.connect("refresh-complete", refresh_complete_cb)

        def timeout_cb(foo):
            if feedtree.updating: return True
            feedtree.update_feed_all()
            return True
        GLib.timeout_add_seconds(3600, timeout_cb, None)

        button_refresh = Gtk.Button()
        button_refresh.set_image(Gtk.Image.new_from_stock(Gtk.STOCK_REFRESH, Gtk.IconSize.MENU))
        button_refresh.set_label(_("Update All"))
        def refresh_cb(button):
            feedtree.update_feed_all()
        button_refresh.connect("clicked", refresh_cb)

        button_mark_all = Gtk.Button()
        button_mark_all.set_image(Gtk.Image.new_from_stock(Gtk.STOCK_APPLY, Gtk.IconSize.MENU))
        button_mark_all.set_label(_("Mark All As Read"))
        def mark_all_cb(button):
            feedtree.mark_read_all()
        button_mark_all.connect("clicked", mark_all_cb)

        hbox = Gtk.HBox()
        hbox.pack_start(button_refresh, False, False, 0)
        hbox.pack_start(button_mark_all, False, False, 0)

        scrolled_feedtree = Gtk.ScrolledWindow()
        scrolled_feedtree.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_feedtree.add(feedtree)

        vbox2 = Gtk.VBox()
        vbox2.pack_start(hbox, False, False, 0)
        vbox2.pack_start(scrolled_feedtree, True, True, 0)

        scrolled_entries = Gtk.ScrolledWindow()
        scrolled_entries.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_entries.add(entries)

        vbox = Gtk.VBox()
        vbox.pack_start(toolbar, False, False, 0)
        vbox.pack_start(content_pane, True, True, 0)

        vpane2 = Gtk.HPaned()
        vpane2.add1(scrolled_entries)
        vpane2.add2(vbox)

        vpane1 = Gtk.HPaned()
        vpane1.add1(vbox2)
        vpane1.add2(vpane2)

        self.add(vpane1)
        self.set_default_size(800, 600)

        def destroy_cb(window):
            feeddb.close()
            self.destroy()
            Gtk.main_quit()
        self.connect('destroy', destroy_cb)

        def key_press_event(window, event):
            if event.keyval == 49: # 1
                feedtree.grab_focus()
                return True
            elif event.keyval == 50: # 2
                entries.grab_focus()
                return True
            elif event.keyval == 51: # 3
                content_pane.set_focus()
                return True
            return False
        self.connect('key-press-event', key_press_event)

        feedtree.update_feed_all()

        self.show_all()

        content_pane.new_tab()

if __name__ == "__main__":
    jar = Soup.CookieJarText.new("cookies.txt", False)
    session = WebKit.get_default_session()
    session.add_feature(jar)
    session.set_property("timeout", 60)
    feedreader = FeedReaderWindow()
    Gtk.main()
