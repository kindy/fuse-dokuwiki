#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

import logging

from collections import defaultdict
from errno import ENOENT, EROFS
from stat import S_IFDIR, S_IFLNK, S_IFREG
from time import time
import re

from dokuwiki import DokuWiki
from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
from cache import LruCache as LRU

if not hasattr(__builtins__, 'bytes'):
    bytes = str


class Doku(LoggingMixIn, Operations):
    'Example memory filesystem. Supports only one level of files.'

    def __init__(self, url, user, password):
        self.doku = DokuWiki(url, user, password)

        self.fd = 0
        self._pages = {}
        self._dirs = {}

        # now = time()
        # st_mode=(S_IFDIR | 0o755),
        # st_ctime=now,
        # st_mtime=now,
        # st_atime=now,
        # st_nlink=2
        # file

    @LRU(timeout=60)
    def doku_page(self, page_id):
        return self.doku.pages.get(page_id)

    def get_by_path(self, path):
        obj = self.pages.get(path, self.dirs.get(path))
        if not obj:
            raise FuseOSError(ENOENT)
        return obj

    def getxattr(self, path, name, position=0):
        try:
            page_path, sb_name = self.parse_sb_for_typora(path)
            page_tmps = self.pages[page_path]['tmps']
            if sb_name in page_tmps:
                return ''

        except FuseOSError:
            pass

        attrs = self.get_by_path(path).get('attrs', {})

        try:
            return attrs[name]
        except KeyError:
            return ''       # Should return ENOATTR

    def listxattr(self, path):
        attrs = self.get_by_path(path).get('attrs', {})

        return attrs.keys()

    def removexattr(self, path, name):
        attrs = self.get_by_path(path).get('attrs', {})

        try:
            del attrs[name]
        except KeyError:
            pass        # Should return ENOATTR

    def setxattr(self, path, name, value, options, position=0):
        attrs = self.get_by_path(path).get('attrs', {})
        attrs[name] = value

    @LRU(timeout=60)
    def doku_pages(self):
        pages = {}
        now = time()
        dirs = defaultdict(lambda : {
            'is_dir': True,
            'attr': {'st_mode': S_IFDIR | 0777, 'st_ctime': now, 'st_mtime': now, 'st_atime': now, 'st_nlink': 2},
            'attrs': {},
            'subs': {},
        })
        for page in self.doku.pages.list():
            page_id = page['id']
            path = '/' + page_id.replace(':', '/')
            if not path.endswith('.md'):
                path = path + '.md'

            pages[path] = page
            page['attr'] = dict(
                st_mode=(S_IFREG | 0666),
                st_nlink=1,
                st_size=page['size'],
                st_ctime=page['mtime'],
                st_mtime=page['mtime'],
                st_atime=page['mtime'],
            )
            page['attrs'] = {}
            page['tmps'] = {}
            paths = path.split('/')
            page['name'] = paths[-1]
            while len(paths) > 1:
                name = paths.pop()
                dir_ = '/'.join(paths)
                if dir_ == '':
                    dir_ = '/'
                dirs[dir_]['subs'][name] = True

        self._pages = pages
        self._dirs = dirs

    @property
    def pages(self):
        self.doku_pages()
        return self._pages

    @property
    def dirs(self):
        self.doku_pages()
        return self._dirs

    def access(self, path, mask):
        try:
            page_path, sb_name = self.parse_sb_for_typora(path)
            return 0
        except FuseOSError:
            pass

        try:
            def_ = self.get_by_path(path)
        except FuseOSError:
            return -ENOENT

        return 0

    def getattr(self, path, fh=None):
        try:
            page_path, sb_name = self.parse_sb_for_typora(path)
            page_tmps = self.pages[page_path]['tmps']
            if sb_name in page_tmps:
                return page_tmps[sb_name]['attr']
        except FuseOSError:
            pass

        def_ = self.get_by_path(path)

        return def_.get('attr')

    def open(self, path, flags):
        self.fd += 1
        return self.fd

    def create(self, path, flags):
        page_path, sb_name = self.parse_sb_for_typora(path)

        page = self.pages[page_path]
        page['tmps'][sb_name] = {
            'con': '',
            'attr': {
                'st_size': 0,
                'st_mode': (S_IFREG | 0666),
            },
        }

        self.fd += 1
        return self.fd

    def get_page_con(self, path):
        if path not in self.pages:
            raise FuseOSError(ENOENT)

        page_id = self.pages[path]['id']
        page_con = self.doku_page(page_id).encode('utf-8')

        return page_con

    def read(self, path, size, offset, fh):
        con = self.get_page_con(path)

        return con[offset:offset+size]

    def readdir(self, path, fh):
        return ['.', '..'] + self.dirs[path]['subs'].keys()

    def _statfs(self, path):
        return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)

    def truncate(self, path, length, fh=None):
        page = self.pages[path]
        con = self.get_page_con(path)

        # make sure extending the file fills in zero bytes
        full_con = con[:length].ljust(length, '\x00'.encode('ascii'))

        self.write_page_and_flush(path, page, full_con)

    def write_page_and_flush(self, path, page, full_con):
        page_id = page['id']
        self.doku.pages.set(page_id, full_con)

        self.doku_page.invalidate(self, page_id)

        con = self.get_page_con(path)
        size = len(con)
        page['size'] = size
        page['attr']['st_size'] = size

        return page

    def write(self, path, data, offset, fh):
        try:
            page_path, sb_name = self.parse_sb_for_typora(path)
            tmp = self.pages[page_path]['tmps'][sb_name]
            con = tmp['con']
            full_con = con[:offset].ljust(offset, '\x00'.encode('ascii')) + data + ((offset + len(data) < len(con)) and con[offset + len(data)] or '')
            tmp['con'] = full_con
            tmp['attr']['st_size'] = len(full_con)

            return len(data)
        except FuseOSError:
            pass

        page = self.pages[path]
        if not page:
            raise FuseOSError(ENOENT)

        con = self.get_page_con(path)
        full_con = con[:offset].ljust(offset, '\x00'.encode('ascii')) + data + ((offset + len(data) < len(con)) and con[offset + len(data)] or '')
        # make sure the data gets inserted at the right offset
        # self.data[path][:offset].ljust(offset, '\x00'.encode('ascii'))
        # + data
        # and only overwrites the bytes that data is replacing
        # + self.data[path][offset + len(data):])

        self.write_page_and_flush(path, page, full_con)

        return len(data)

    '''
    %% support Typora
    for file a.md, Typora will:
        1. create new file a~.md
        2. create new files a.md.sb-\w+-\w+
        3. rename a.md <-> a~.md
        4. rename a.md.sb-\w+-\w+ -> a.md
        5. unlink a~.md
    '''
    def rename(self, old, new):
        # backup a.md -> a~.md
        if old in self.pages:
            if not self.is_a_for_typora(new):
                raise FuseOSError(EROFS)

        if new in self.pages:
            # a~.md -> a.md
            if self.is_a_for_typora(new):
                return

            # a.md.sb-xxx -> a.md
            page_path, sb_name = self.parse_sb_for_typora(old)
            page = self.pages[page_path]
            con = page['tmps'][sb_name]['con']
            self.write_page_and_flush(page_path, page, con)
            del page['tmps'][sb_name]

    def unlink(self, path):
        if self.is_a_for_typora(path):
            return

        page_path, sb_name = self.parse_sb_for_typora(path)
        page_tmps = self.pages[page_path]['tmps']
        if sb_name not in page_tmps:
            raise FuseOSError(ENOENT)

        del page_tmps[sb_name]

    def chmod(self, path, mode):
        return 0

    def is_a_for_typora(self, path):
        m = re.match(r'^(.+?)~(\.md)$', path)
        if m:
            page_path = '{}{}'.format(m.group(1), m.group(2))
            return page_path in self.pages

        return False

    def parse_sb_for_typora(self, path):
        m = re.match(r'^(.+?\.md)(\.sb-\w+-\w+)$', path)
        if not m:
            raise FuseOSError(EROFS)

        page_path = m.group(1)
        if page_path not in self.pages:
            raise FuseOSError(EROFS)

        return page_path, m.group(2)



if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mount')
    parser.add_argument('--server', '-s', required=True,
        help='dokuwiki url, like http://dokuwiki.com:80')
    parser.add_argument('--user', '-u', default='superuser',
        help='wiki user that can call xmlrpc, default to "superuser"')
    parser.add_argument('--password', '-p', default='bitnami1',
        help='user passpord, default to "bitnami1"')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, filename='./run.log')
    doku = Doku(args.server, args.user, args.password)

    fuse = FUSE(doku, args.mount, foreground=True, allow_other=True, nothreads=True)