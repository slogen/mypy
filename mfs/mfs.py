#!/usr/bin/env python

# Handy shell commands to stop mfs
#  ps ax | grep 'python ./mfs.py' | grep -v grep | awk '{print $1;}' | xargs -r kill

# Standard libraries
import sys, os, os.path, time, stat
import re, datetime, itertools, traceback, errno

# Fuse for MythTV
import fuse, MythTV
fuse.fuse_python_api = (0, 2)

# terrible, horrible printing hack for making unicode strings print
# (possibly not very pretty) in terminals instead of blowing up the
# entire application.
if sys.getdefaultencoding() in ['ascii']:
    reload(sys)
    sys.setdefaultencoding('utf-8')

class Node(fuse.Stat, fuse.Direntry):
    """A node in a directory tree. (defaults to a File: S_IFREG)"""
    default_mode = stat.S_IFREG | 0444 # default to readonly
    default_uid = os.getuid()
    default_gid = os.getgid()
    def __init__(self, name,
                 st_mode = None,
                 st_ino = None,
                 st_dev = None,
                 st_size = None,
                 st_blocksize = None, 
                 st_blocks = None,
                 st_atime = None,
                 st_mtime = None,
                 st_ctime = None,
                 st_uid = None,
                 st_gid = None,
                 st_nlink = None):
        assert isinstance(name, str) # Unicode will not work
        self.name = name
        sz = st_size if st_size is not None else 0
        bz = st_blocksize if st_blocksize is not None else 1024
        blocks = st_blocks if st_blocks else sz/min(bz,1)
        mtime = st_mtime if st_mtime is not None else 0
        atime = st_atime if st_atime is not None else mtime
        ctime = st_ctime if st_ctime is not None else mtime
        ino = st_ino if st_ino is not None else id(self)
        assert isinstance(ino, (int, long)) # Inodes are integer identities
        fuse.Direntry.__init__(self, name = name, offset = 0, ino = ino)
        fuse.Stat.__init__(self,
            st_mode = st_mode if st_mode is not None else self.default_mode,
            st_ino = ino,
            st_dev = st_dev if st_dev is not None else 0,
            st_blksize = bz,
            st_nlink = st_nlink if st_nlink is not None else 1,
            st_uid = st_uid if st_uid is not None else self.default_uid,
            st_gid = st_gid if st_gid is not None else self.default_gid,
            st_blocks = blocks,
            st_rdev = 0,
            st_size = sz,
            st_atime = atime,
            st_mtime = mtime,
            st_ctime = ctime)
    def __repr__(self): return "%s[%s]" % (self, self.st_ino)
    def __str__(self): 
        return "%s%s" % ( 
            self.name,   
            "/" if self.st_mode & stat.S_IFDIR else "")

class Dir(Node, dict):
    """A directory is a node that holds a dict of children"""
    default_mode = stat.S_IFDIR | 0555
    def __init__(self, name):
        Node.__init__(self, name)
    def walk(self, topdown = True, path = None):
        """walk directory like os.walk, but with Path as dirpath"""
        dirs = [n for n in self.values() if n.st_mode & stat.S_IFDIR]
        files = [n for n in self.values() if n.st_mode & stat.S_IFREG]
        here = Path(path or []).joinparts(self.name)
        if topdown: yield (here, dirs, files)
        for d in dirs:
            for x, xdirs, xfiles in d.walk(topdown = topdown, path = here):
                yield x, xdirs, xfiles
        if not topdown: yield (here, dirs, files)
    def get(self, path, default = -errno.ENOENT, make_sub = None):
        """Recursive get sub-path. path can be str, unicode or seq of parts

If the head of path is not found the get will either return default or
invoke make_sub(self, head) to create a sub-directory.
"""
        path = Path(path)
        head = path.head
        if head == '':
            return self
        sub = dict.get(self, head, None)
        if sub is None:
            if make_sub is None:
                return default
            else:
                sub = make_sub(self, head)
                self[head] = sub
        tail = path.tail
        if len(tail) > 0:
            sub = sub.get(tail, default = default, make_sub = make_sub)
        return sub
    def __getitem__(self, path):
        """Dispatch to self.get

Raises IOError(errno.ENOENT) instead of  the usual KeyError"""
        i = self.get(path, default = None)
        if i is None:
            raise IOError(errno.ENOENT, "%s does not exist" % path)
        return i
    def flatten(self, flat = None):
        """Flatten a directory-tree"""
        if flat is None:
            flat = dict()
        for path, dirs, files in root.walk():
            for x in dirs + files:
                flat[str(Path(path).joinparts(x))] = x
        return flat

class Path(tuple):
    """Path represented as a tuple of parts"""
    _pathsep_re = re.compile("//*")
    _pathend_re = re.compile("/*$")
    _pathbeg_re = re.compile("^/*") 
    encoding = "utf-8"
    def __new__(cls, path):
        if isinstance(path, (str, unicode)):
            parts = Path._pathsep_re.split(
                Path._pathend_re.sub(
                    "", Path._pathbeg_re.sub("", path)).encode(Path.encoding))
        else:
            if not all(isinstance(x, str) for x in path): # only str parts
                path = [x.encode(Path.encoding) for x in path]
            parts = path
        return tuple.__new__(cls, parts)
        
    @property
    def dirname(self): return "/".join(self.dirparts)
    @property
    def basename(self): return self[-1] if len(self) > 0 else ""
    @property
    def split(self): return (self.dirname, self.basename)
    @property
    def dirparts(self): return self[:-1]
    @property
    def splitparts(self): return (self.dirparts, self.basename)
    @property
    def path(self): return "/".join(self)
    @property
    def head(self): return self[0]
    @property
    def tail(self): return self[1:]
    def __str__(self): return self.path

    def joinparts(self, postfix): return Path(self + Path(postfix))
    def join(self, postfix): return self.joinparts(postfix).path
    
class Recordings:
    """Access recordings from MythTV"""
    encoding = 'utf-8'
    def __init__(self, db):
        self.db = db
    # How to format a recording
    subfile = re.compile('[^ \[\]\-\.\w]', re.UNICODE) # replace nasty paths
    def format_recording(self, p, ext = ".mpg"):
        path = []
        cat = p.get('category')
        if cat is not None and cat != 0 and cat != '':
            path.append(self.subfile.sub("_", cat))
        else:
            path.append('Unknown')

        s = p.title or ("%S_%S" % 
                        (p.chanid, p.starttime.isoformat()))
        fmt = lambda f: lambda x: f % x
        keys = [
            ('season', fmt('S%s')),
            ('episode', fmt('E%s')),
            ('subtitle', fmt(' - %s')),
            ('starttime', lambda t: t.strftime(" [%Y-%m-%d %H.%M]")),
            ]
        for k,f in keys:
            v = p.get(k)
            if v is not None and v != 0 and v != '':
                s += f(v)
        s = self.subfile.sub("_", s)
        if ext is not None:
            s += ext
        path.append(s)
        return Path("/".join(path))

    class Rec(Node):
        """Directory Node representing a recording"""
        def __init__(self, name, recording):
            self.recording = recording
            self.refcount = 0
            self.stream = None
            Node.__init__(
                self, name = name,
                st_mtime = int(
                    time.mktime(recording.lastmodified.timetuple())),
                st_size = recording.filesize)
        def __repr__(self): return "%s: %s" % (self.name, self.recording)

        def open(self, flags = None):
            if self.stream is None:
                self.refcount = 0
                self.stream = self.recording.open()
            self.refcount += 1
        def read(self, length, offset, fh = None):
            s = self.stream
            if s is None: return -errno.ENOENT
            if s.tell() != offset: s.seek(offset)
            return s.read(length)
        def release(self, flags = None):
            self.refcount -= 1
            if self.refcount <= 0:
                self.refcount = 0
                try:
                    if self.stream:
                        self.stream.close()
                finally:
                    self.stream = None

    def find(self, root = None, existing = None, **kwargs):
        """Find recordings matching **kwargs. 

Reuses existing Rec objects if passed"""
        if root is None:
            root = Dir(name = "")
        items = ((self.format_recording(x), x) 
                 for x in self.db.searchRecorded(**kwargs))
        
        for path, recording in items:
            path = Path(path)
            basename = path.basename
            rec = ((existing is not None 
                    and existing.get(path, default = None)) 
                   or self.Rec(name = basename, recording = recording))
            root.get(
                path.dirparts, 
                make_sub = lambda x,h: Dir(h))[basename] = rec
        return root

class MFS(fuse.Fuse):
    """Actual file-system representation"""
    def __init__(self, db = None, *args, **kwargs):
        fuse.Fuse.__init__(self, *args, **kwargs)
        if db is None:
            db = MythTV.MythDB()
        self.db = db
        self.root = Dir("")
        

    def _calculate(self):
        root = Dir("")
        # Add recordings (this should be much easier... will have to refactor)
        root["Recordings"] = Recordings(db = self.db).find(
            root = Dir("Recordings"),
            existing = self.get("Recordings", default = None)) 
        # Fixup "stuff"
        for path, dirs, files in root.walk(topdown = False):
            for x in dirs: # dir mtime recursively max
                x.st_mtime = max(y.st_mtime for y in dirs + files)
        return root

    def update(self): self.root = self._calculate()

    def get(self, path, default = -errno.ENOENT):
        return self.root.get(Path(path), default)
    def __getitem__(self, path):
        return self.root[path]

    def fsinit(self):
        self.update()
        #sys.settrace(_tracefunc_top)
        pass
    
    # Simple path dispatch. Could not make the fuse file_class work
    def getattr(self, path): return self[path]
    def readdir(self, path, offset = None): return self[path].values()
    def read(self, path, length, offset):
        return self[path].read(length = length, offset = offset)
    def release(self, path, flags): return self[path].release(flags)
    def fsync(self, path, isfsyncfile): return 0
    def flush(self, path): return 0
    def fgetattr(self, path): return self[path]
    def open(self, path, flags = None): return self[path].open(flags = flags)

    # Unsupported
    def readlink(self, path): return -errno.ENOSYS
    def unlink(self, path): return -errno.ENOSYS
    def rmdir(self, path): return -errno.ENOSYS
    def symlink(self, path): return -errno.ENOSYS
    def rename(self, path): return -errno.ENOSYS
    def link(self, path): return -errno.ENOSYS
    def chmod(self, path): return -errno.ENOSYS
    def chown(self, path): return -errno.ENOSYS
    def truncate(self, path): return -errno.ENOSYS
    def mknod(self, path): return -errno.ENOSYS
    def mkdir(self, path): return -errno.ENOSYS
    def write(self, path, buf, offset): return -errono.ENOSYS
    def ftruncate(self, path): return -errono.ENOSYS
    def lock(self, path, cmd, own, **kw): return -errono.ENOSYS
    # Ignored
    def utime(self, path): pass
    def utimens(self, path, ts_acc, ts_mode): pass
    # Mocked
    def statfs(self): return fuse.StatVfs()
    def access(self, path, mode): return 0
    

def main(*args):
    fs = MFS(version='MFS 0.1.0', usage='')
    fs.parse(errex=1)
    fs.flags = 0
    fs.multithreaded = False
    fs.main(*args)

def _tracefunc_top(frame, event, arg):
    """helper function for tracing execution when debugging"""
    import repr as reprlib

    loc = frame.f_locals
    code = frame.f_code
    self = loc.get('self', None)
    do_trace = (
        True
        #and self is not None 
        #and self.__class__.__module__ in '__main__'
        and not code.co_name.startswith("_"))
    if event == 'exception':
        print 'exception: File "%s", line %s, in %s' % (
            code.co_filename, frame.f_lineno, code.co_name)
        if isinstance(arg[0], (GeneratorExit, )):
            return None
        traceback.print_exception(*arg)
    if do_trace:
        if event == 'return':
            print 'return: %s  File "%s", line %i, in %s' % (
                arg, code.co_filename, frame.f_lineno,code.co_name)
            return _tracefunc_top
        elif event == 'call':
            print 'call:  File "%s", line %i, in %s\n%s' % (
                code.co_filename, frame.f_lineno, code.co_name, 
                reprlib.repr(loc))
            return _tracefunc_top
    
if __name__ == '__main__':
    # special support for my editor :)
    if os.environ.get('INSIDE_EMACS') and not sys.gettrace():
        print "--- MFS"
        mfs = MFS()
        mfs.update()
    else:
        main()
