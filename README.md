Introduction
============

pyferea is my solution to [this
email](http://lists.debian.org/debian-user/2011/07/msg01362.html) that I posted
to the debian-users list in 2011. I was fed up with there being no sane RSS
reader in existance that could just render some RSS entries in a fast and
simple fashion.

Quick Start
===========

Create a feeds.yaml (you can copy feeds.yaml.example) and then run:

	$ python pyferea.py

Naming
======

It is called pyferea (python feed reader) for now as I was inspired by the
layout of liferea (linux feed reader). I guess I'm just too lazy to come up
with another name but suggestions are welcome. Pyferea is just the first thing
that sprang to my mind when I had to give the sourcecode directory a name and I
didnt change it since.

Purpose
=======

I might really overlook something out there but everytime I checked there was
no sane RSS feed reader out there that would please me. I did not think that I
would require much. Just three panes for feeds, entries and content, keeping
record of unread entries and rendering content in a browser. Liferea came close
but was poisoned by feature bloat (as many others... especially gnome
dependencies) and major slowness. On top of that it created a new feed entry
everytime I accidentally drag&drop something. I call all of those bugs and they
never got fixed. Pyferea does just what I want, is simple, DE agnostic (uses
python and gtk) and fits in about 1000 lines of code.

Pyferea is for you if you want:

 - an offline feed reader
 - no gnome, KDE, mono dependencies
 - no rss reader as a browser plugin
 - not terminal based, hence webbrowser for rendering

Bugs
====

Pyferea as it is now is enough for my daily use but there are still some issues
that need to be fixed: the back/forward functionality of the browser must be
fixed (i seldomly use it), the date/time in the entry panel doesnt update
correctly over time (i can live with it for now) and the text in the
addressbar, title and tabtitle must be synced. I will fix that once I feel like
it. If anybody feels inclined to do so, then patches are welcome.

Dependencies
============

	apt-get install python-gobject python-yaml python-lxml python-feedparser gir1.2-webkit-3.0

As of February 2012, the dependency size of the following feed readers in a
fresh Debian Sid minimal chroot:

	pyferea: 172MB
	liferea: 225MB
	gpodder: 226MB
	blam: 408MB
	akregator: 758MB

Keyboard shortcuts
==================

To make it faster to switch between the three panes and scroll in them, use the
keys 1, 2 and 3 to select the first, second or third pane respectively.

feeds.yaml
==========

It is a yaml dictionary with rss/atom feeds as keys and subdictionaries as
values. For each entry they store the category a feed is in and if the link
given in a feed entry should be loaded instead of the feed text.

Example:

```yaml
http://planet.debian.org/rss20.xml:
  category: "IT news"
  loadlink: False
http://slashdot.org/slashdot.rss:
  category: "IT news"
  loadlink: True
```

Cookies
=======

Cookies are kept in cookies.txt and are automatically accepted

ythtml5.js
==========

A javascript that I load upon each pageload to convert youtube videos into
their html5 versions so that the webkit plugin can render them even withoutme
having flash.

Possible future work
====================

(patches welcome)

 - build debian package
 - add hooks to load custom javascript/css for feeds
 - i18n
