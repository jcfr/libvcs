#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Subversion object for libvcs.

libvcs.svn
~~~~~~~~~~

The follow are from saltstack/salt (Apache license):

- :py:meth:`SubversionRepo.get_revision_file`

The following are pypa/pip (MIT license):

- :py:meth:`SubversionRepo.get_url_and_revision_from_pip_url`
- :py:meth:`SubversionRepo.get_url`
- :py:meth:`SubversionRepo.get_revision`
- :py:meth:`~.get_rev_options`

"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import re

from ._compat import urlparse
from .util import run
from .base import BaseRepo

logger = logging.getLogger(__name__)


class SubversionRepo(BaseRepo):
    bin_name = 'svn'
    schemes = ('svn', 'svn+ssh', 'svn+http', 'svn+https', 'svn+svn')

    def __init__(self, url, **kwargs):
        """A svn repository.

        :param url: URL in subversion repository
        :type url: str

        :param svn_username: username to use for checkout and update
        :type svn_username: str or None

        :param svn_password: password to use for checkout and update
        :type svn_password: str or None

        :param svn_trust_cert: trust the Subversion server site certificate
            (default False)
        :type svn_trust_cert: bool
        """
        if 'svn_trust_cert' not in kwargs:
            self.svn_trust_cert = False
        BaseRepo.__init__(self, url, **kwargs)

    def _user_pw_args(self):
        args = []
        for param_name in ['svn_username', 'svn_password']:
            if hasattr(self, param_name):
                args.extend(['--' + param_name[4:],
                             getattr(self, param_name)])
        return args

    def obtain(self, quiet=None):
        self.check_destination()

        url, rev = self.url, self.rev

        cmd = ['checkout', '-q', url, '--non-interactive']
        if self.svn_trust_cert:
            cmd.append('--trust-server-cert')
        cmd.extend(self._user_pw_args())
        cmd.extend(get_rev_options(url, rev))
        cmd.append(self.path)

        self.run(cmd)

    def get_revision_file(self, location=None):
        """Return revision for a file."""

        if location:
            cwd = location
        else:
            cwd = self.path

        current_rev = run(['info', cwd])
        infos = current_rev['stdout']

        _INI_RE = re.compile(r"^([^:]+):\s+(\S.*)$", re.M)

        info_list = []
        for infosplit in infos:
            info_list.extend(_INI_RE.findall(infosplit))

        return int(dict(info_list)['Revision'])

    def get_revision(self, location=None):
        """
        Return the maximum revision for all files under a given location
        """

        if not location:
            location = self.url

        if os.path.exists(location) and not os.path.isdir(location):
            return self.get_revision_file(location)

        # Note: taken from setuptools.command.egg_info
        revision = 0

        for base, dirs, files in os.walk(location):
            if '.svn' not in dirs:
                dirs[:] = []
                continue    # no sense walking uncontrolled subdirs
            dirs.remove('.svn')
            entries_fn = os.path.join(base, '.svn', 'entries')
            if not os.path.exists(entries_fn):
                # FIXME: should we warn?
                continue

            dirurl, localrev = self._get_svn_url_rev(base)

            if base == location:
                base_url = dirurl + '/'   # save the root url
            elif not dirurl or not dirurl.startswith(base_url):
                dirs[:] = []
                continue    # not part of the same svn tree, skip it
            revision = max(revision, localrev)
        return revision

    @classmethod
    def get_url_and_revision_from_pip_url(cls, pip_url):
        # hotfix the URL scheme after removing svn+ from svn+ssh:// re-add it
        url, rev = super(
            SubversionRepo, cls).get_url_and_revision_from_pip_url(pip_url)
        if url.startswith('ssh://'):
            url = 'svn+' + url
        return url, rev

    def update_repo(self, dest=None):
        self.check_destination()
        if os.path.isdir(os.path.join(self.path, '.svn')):
            dest = self.path if not dest else dest

            url, rev = self.url, self.rev

            cmd = ['update']
            cmd.extend(self._user_pw_args())
            cmd.extend(get_rev_options(url, rev))

            self.run(cmd)
        else:
            self.obtain()
            self.update_repo()


def get_rev_options(url, rev):
    """Return revision options.

    from pip pip.vcs.subversion.

    """
    if rev:
        rev_options = ['-r', rev]
    else:
        rev_options = []

    r = urlparse.urlsplit(url)
    if hasattr(r, 'username'):
        # >= Python-2.5
        username, password = r.username, r.password
    else:
        netloc = r[1]
        if '@' in netloc:
            auth = netloc.split('@')[0]
            if ':' in auth:
                username, password = auth.split(':', 1)
            else:
                username, password = auth, None
        else:
            username, password = None, None

    if username:
        rev_options += ['--username', username]
    if password:
        rev_options += ['--password', password]
    return rev_options
