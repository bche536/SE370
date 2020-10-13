# !/usr/bin/env python

# SE370 Assignment 2
# Ben Chen BCHE536 804118313

from __future__ import print_function, absolute_import, division

import logging
import os
import sys
import errno

from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from time import time
from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

if not hasattr(__builtins__, 'bytes'):
    bytes = str


class A2Fuse2(LoggingMixIn, Operations):
    def __init__(self, src1, src2):
        self.src1 = src1
        self.src2 = src2
        self.files = {}
        self.data = defaultdict(bytes)
        self.fd = 0
        now = time()
        self.files['/'] = dict(st_mode=(S_IFDIR | 0o755), st_ctime=now,
                               st_mtime=now, st_atime=now, st_nlink=2)

    # Helpers
    # =======

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path1 = os.path.join(self.src1, partial)
        path2 = os.path.join(self.src2, partial)
        return [path1, path2]

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        if path not in self.files:
            src1, src2 = self._full_path(path)
            if os.path.isdir(src1) or os.path.isfile(src1):
                if not os.access(src1, mode):
                    raise FuseOSError(errno.EACCES)

            elif os.path.isdir(src2) or os.path.isfile(src2):
                if not os.access(src2, mode):
                    raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        if path not in self.files:
            src1, src2 = self._full_path(path)
            if os.path.isdir(src1) or os.path.isfile(src1):
                return os.chmod(src1, mode)

            elif os.path.isdir(src2) or os.path.isfile(src2):
                return os.chmod(src2, mode)

        else:
            self.files[path]['st_mode'] &= 0o770000
            self.files[path]['st_mode'] |= mode

    def chown(self, path, uid, gid):
        if path not in self.files:
            src1, src2 = self._full_path(path)
            if os.path.isdir(src1) or os.path.isfile(src1):
                return os.chown(src1, uid, gid)

            elif os.path.isdir(src2) or os.path.isfile(src2):
                return os.chown(src2, uid, gid)

        else:
            self.files[path]['st_uid'] = uid
            self.files[path]['st_gid'] = gid

    def getattr(self, path, fh=None):
        if path not in self.files:
            src1, src2 = self._full_path(path)
            if os.path.isdir(src1) or os.path.isfile(src1):
                st = os.lstat(src1)
                return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                                                                'st_gid', 'st_mode', 'st_mtime', 'st_nlink',
                                                                'st_size', 'st_uid'))
            elif os.path.isdir(src2) or os.path.isfile(src2):
                st = os.lstat(src2)
                return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                                                                'st_gid', 'st_mode', 'st_mtime', 'st_nlink',
                                                                'st_size', 'st_uid'))
            else:
                raise FuseOSError(ENOENT)

        else:
            return self.files[path]

    def readdir(self, path, fh):
        src1, src2 = self._full_path(path)
        dirents = ['.', '..']

        if os.path.isdir(src1):
            dirents.extend(os.listdir(src1))

        if os.path.isdir(src2):
            dirents.extend(os.listdir(src2))

        dirents.extend([x[1:] for x in self.files if x != '/'])
        for r in dirents:
            yield r

    def unlink(self, path):
        if path not in self.files:
            src1, src2 = self._full_path(path)
            if os.path.isfile(src1):
                return os.unlink(src1)

            elif os.path.isfile(src2):
                return os.unlink(src2)

        self.files.pop(path)

    def rename(self, old, new):
        if old not in self.files:
            old1, old2 = self._full_path(old)
            new1, new2 = self._full_path(new)
            if os.path.isdir(old1) or os.path.isfile(old1):
                return os.rename(old1, new1)

            elif os.path.isdir(old2) or os.path.isfile(old2):
                return os.rename(old2, new2)

        else:
            self.files[new] = self.files[old]
            self.data[new] = self.data[old]
            self.files.pop(old)
            self.data.pop(old)

    # File methods
    # ============

    def open(self, path, flags):
        if path not in self.files:
            src1, src2 = self._full_path(path)
            if os.path.isfile(src1):
                return os.open(src1, flags)

            elif os.path.isfile(src2):
                return os.open(src2, flags)

        else:
            self.fd += 1
            return self.fd

    def create(self, path, mode, fi=None):
        self.files[path] = dict(st_mode=(S_IFREG | mode), st_nlink=1,
                                st_size=0, st_ctime=time(), st_mtime=time(),
                                st_atime=time())

        self.chown(path, os.getuid(), os.getgid())
        self.fd += 1
        return self.fd

    def read(self, path, length, offset, fh):
        if path not in self.files:
            os.lseek(fh, offset, os.SEEK_SET)
            return os.read(fh, length)
        return self.data[path][offset:offset + length]

    def write(self, path, data, offset, fh):
        if path not in self.files:
            os.lseek(fh, offset, os.SEEK_SET)
            return os.write(fh, data)
        self.data[path] = self.data[path][:offset] + data
        self.files[path]['st_size'] = len(self.data[path])
        return len(data)

    def truncate(self, path, length, fh=None):
        if path not in self.files:
            src1, src2 = self._full_path(path)
            if os.path.isfile(src1):
                with open(src1, 'r+') as f:
                    f.truncate(length)

            elif os.path.isfile(src2):
                with open(src2, 'r+') as f:
                    f.truncate(length)

    def flush(self, path, fh):
        if path not in self.files:
            return os.fsync(fh)

    def release(self, path, fh):
        if path not in self.files:
            return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        if path not in self.files:
            return self.flush(path, fh)


def main(mountpoint, src1, src2):
    FUSE(A2Fuse2(src1, src2), mountpoint, nothreads=True, foreground=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[3], sys.argv[2], sys.argv[1])
