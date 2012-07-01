import sqlite3


def dbcreate(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS feeds (
    feed TEXT NOT NULL,
    title TEXT,
    favicon BLOB,
    etag TEXT,
    lastmodified TEXT,
    unread INTEGER
    )
    """)
    conn.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS feedidx ON feeds (feed)
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS entries (
    feed TEXT NOT NULL,
    entry TEXT NOT NULL,
    title TEXT,
    content TEXT,
    link TEXT,
    date INTEGER,
    unread INTEGER,
    categories TEXT
    )""")
    conn.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS entridx ON entries (feed,entry)
    """)
    conn.commit()

def convert(filename):
    conn = sqlite3.connect(filename)
    conn.text_factory = str
    dbcreate(conn)
    import shelve
    feeddb = shelve.open("pyferea.db")
    for feed, fvalues in feeddb.items():
        conn.execute("""REPLACE INTO feeds (feed, title, favicon, etag, lastmodified, unread) VALUES (?,?,?,?,?,?)""",
        (feed, fvalues.get('title'), fvalues.get('favicon'), fvalues.get('etag'), fvalues.get('lastmodified'), fvalues.get('unread')))
        for entry, evalues in fvalues['items'].items():
            conn.execute("""REPLACE INTO entries (feed, entry, title, content, link, date, unread, categories) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (feed, entry, evalues.get('title'), evalues.get('content'), evalues.get('link'), evalues.get('date'), evalues.get('unread'), ', '.join(evalues.get('categories') or [])))
    conn.commit()
    conn.close()
    feeddb.close()

class SQLStorage():
    def __init__(self, filename=':memory:'):
        self.conn = sqlite3.connect(filename)
        self.conn.text_factory = str
        dbcreate(self.conn)

    def get_feed(self, feed):
        result = self.conn.execute("""SELECT title, favicon, etag, lastmodified, unread FROM feeds WHERE feed=?""", (feed,)).fetchone()
        if result:
            return dict(zip(('title', 'favicon', 'etag', 'lastmodified', 'unread'), result))
        else:
            return dict()

    def get_entry(self, feed, entry):
        result = self.conn.execute("""SELECT title, content, link, date, unread, categories FROM entries WHERE feed=? AND entry=?""", (feed, entry)).fetchone()
        if result:
            return dict(zip(('title', 'content', 'link', 'date', 'unread', 'categories'), result))
        else:
            return dict()

    def get_entries_all(self, feed):
        result = self.conn.execute(
            """SELECT entry, title, date, unread FROM entries WHERE feed=? ORDER BY date DESC""",
            (feed,)).fetchall()
        if result:
            return [dict(zip(('entry', 'title', 'date', 'unread'), c)) for c in result]
        else:
            return list()

    def add_entry(self, feed, entry, values):
        self.conn.execute("""REPLACE INTO entries (feed, entry, title, content, link, date, unread, categories) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (feed, entry, values['title'], values['content'], values['link'], values['date'], values['unread'], values['categories']))
        self.conn.commit()

    def update_feed(self, feed, values):
        self.conn.execute("""UPDATE feeds SET title=?, favicon=?, etag=?, lastmodified=?, unread=? WHERE feed=?""",
            (values['title'], values.get('favicon'), values.get('etag'), values.get('lastmodified'), values['unread'], feed))
        self.conn.commit()

    def set_favicon(self, feed, favicon):
        self.conn.execute("""UPDATE feeds SET favicon=? WHERE feed=?""", (favicon, feed))
        self.conn.commit()

    def mark_read(self, feed, entry):
        self.conn.execute("""UPDATE entries SET unread=0 WHERE feed=? AND entry=?""", (feed, entry))
        self.conn.execute("""UPDATE feeds SET unread=unread-1 WHERE feed=?""", (feed,))
        self.conn.commit()

    def mark_read_feed(self, feed):
        self.conn.execute("""UPDATE entries SET unread=0 WHERE unread=1""")
        self.conn.execute("""UPDATE feeds set unread=0 WHERE feed=?""", (feed,))
        self.conn.commit()

    def close(self):
        self.conn.close()

    def sync(self):
        pass

if __name__ == "__main__":
    convert("pyferea.sqlite")
