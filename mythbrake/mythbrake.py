#!/usr/bin/env python

import sys, os, os.path, re, datetime, shutil, collections, subprocess

link_format = "/mnt/store/Incoming/tmp/%(link_name)s.mp4"
default_options = """
-f mp4 --preset Android -q 20 -Y 720 -X 720 --decomb --loose-anamorphic
-N dan --native-dub
-s scan --subtitle-default
--markers --large-file --optimize --ipod-atom
"""

# terrible, horrible printing hack for making unicode strings print
# (possibly not very pretty) in terminals instead of blowing up the
# entire application.
if sys.getdefaultencoding() in ['ascii']:
    reload(sys)
    sys.setdefaultencoding('utf-8')

import MythTV

db = MythTV.MythDB()
def startend(p):
    if p.cutlist:
        l = list(p.markup.getuncutlist())
        if len(l) > 0:
            yield "--start-at"
            yield "frame:%s" % l[0][0]
            yield "--stop-at"
            yield "frame:%s" % (l[0][1] - l[0][0])
        if len(l) == 1 or (len(l) == 2 and l[1][1] >= 999999):
            pass # end is Ok
        else:
            raise Exception("Wierd cutlist", l)

subfile = re.compile('[^ \[\]\-\w]', re.UNICODE)

def formatfile(p):
    s = p.title or ("%S_%S" % 
                          (p.chanid, p.starttime.isoformat()))
    fmt = lambda f: lambda x: f % x
    keys = [
        ('season', fmt('S%s')),
        ('episode', fmt('E%s')),
        ('subtitle', fmt(' - %s')),
        ('starttime', lambda t: t.strftime(" [%Y%m%d %H%M]")),
        ]
    for k,f in keys:
        v = p.get(k)
        if v is not None and v != 0 and v != '':
            s += f(v)
    return subfile.sub("_", s)

class UTC(datetime.tzinfo):
    ZERO = datetime.timedelta(0)
    HOUR = datetime.timedelta(hours=1)
    def utcoffset(self, dt): return self.ZERO
    def tzname(self, dt): return "UTC"
    def dst(self, dt): return self.ZERO
utc = UTC()

def leaves(args):
    """Linearize a tree of iterators down the leaves"""
    # Strings are iterable, but we always mean the atom :)
    if isinstance(args, (str, unicode)):
        yield args
    else:
        try:
            it = iter(args)
        except TypeError:
            yield args
        else:
            for i in it:
                for i2 in leaves(i):
                    yield i2

class Optional:
    def __init__(self, dry_run = None, do_print = None):
        self.dry_run = dry_run
        self.do_print = do_print
    def _print_quote(self, o):
        if isinstance(o, (str, unicode)):
            import pipes
            return pipes.quote(str(o))
        else:
            return str(o)
    def sub(self, prefix = None):
        def call(*args):
            args = [arg for arg in leaves([prefix, args]) if arg is not None]
            if self.do_print:
                q = self._print_quote
                print "*** ", \
                    " ".join(q(x) for x in args),
            if self.dry_run is not None and not self.dry_run:
                print "+++", args
                return subprocess.check_call(args)
        return call
    def fn(self, f):
        def call(*args, **kwargs):
            if self.do_print:
                q = self._print_quote
                print "*** %s\n" % str(f), \
                    ", ".join(q(x) for x in args), \
                    ", ".join("%s=%s" % (q(k), q(v))
                              for k,v in kwargs.items())
            f(*args, **kwargs)
        return call

def update_marks(p):
    p.seek.clean()
    p.markup.clean()
    p.transcoded = 1
    p.bookmark = 0
    p.cutlist = 0
    p.update()

opt = Optional(dry_run = False, do_print = True)

handbrake = opt.sub(prefix = ['ionice', '-c', '3', 'HandBrakeCLI'])
symlink = opt.fn(os.symlink)
move = opt.fn(shutil.move)
mark = opt.fn(update_marks)

def dirfile(p):
    keys = { 'groupname': p.storagegroup, 'hostname': p.hostname }
    try:
        storage = db.getStorageGroup(**keys).next()
    except StopIteration:
        raise KeyError("Unable to find storage", keys)
    src_dir = storage.dirname
    src_file = p.basename
    return src_dir, src_file

def _transcode(program,
               options = None,
               dst_path = None, 
               tmp_path = None,
               ):
    src_dir, src_file = dirfile(program)
    src_path = os.path.join(src_dir, src_file)
    if tmp_path is None:
        tmp_path = os.path.join(src_dir, "tmp-%s" % src_file)
    if options is None:
        import re
        options = re.split("[ \t\r\n]+", default_options.strip())
    if dst_path is None:
        dst_path=src_path

    handbrake("-i", src_path,
              "-o", tmp_path,
              list(startend(program)),
              options)
    move(tmp_path, dst_path)
    mark(program)
    return dst_path

def _autolink(p, dst_path = None):
    if dst_path is None:
        dst_path = os.path.join(*dirfile(p))
    link_name = formatfile(p)
    symlink(dst_path, link_format % locals())

def act(p, force_transcode = None):
    if force_transcode or (not p.transcoded) or p.cutlist:
        _transcode(p)
    _autolink(p)

def act_all(programs, force_transcode = None):
    errors = 0
    for p in programs:
        try:
            act(p, force_transcode = force_transcode)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            errors += 1
            sys.excepthook(*sys.exc_info())
    return errors

def main(argv):
    query = {}
    if len(argv) == 1:
        if argv[0] == '--2cuts':
            programs = [p for p in list(db.searchRecorded())
                        if p.cutlist and len(p.markup.getuncutlist()) == 2]
        else:
            programs = db.searchRecorded(basename = os.path.basename(argv[0]))
    else:
        raise Exception("Invalid arguments", argv)
    act_all(programs)

if __name__ == '__main__':
    if sys.argv in [["-c"]]:
        main(["/var/lib/mythtv/recordings/1003_20130611220100.mpg"])
    else:
        sys.exit(main(sys.argv[1:]))
