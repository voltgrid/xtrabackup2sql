#!/usr/bin/env python

# The MIT License (MIT)
#
# Copyright (c) 2014 Tim Robinson <tim@voltgrid.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import click
import pprint
import tempfile
import subprocess
import fnmatch
import time
import os
import sys
import MySQLdb
import bz2file

import logging

MYSQL_DIR = 'mysql'
MYSQL_TEMP = 'tmp'

class UserManager(object):
    """ User manager """

    def __init__(self, user):
        if os.geteuid() == 0:
            self.is_root = True
            logging.warning("Running as root")
        else:
            self.is_root = False

        if self.is_root and user == None:
            logging.critical("--user must be specified when running as root")
            sys.exit(1)

        if self.is_root:
            import pwd
            try:
                pwd = pwd.getpwnam(user)
            except KeyError:
                logging.critical("User \"%s\" was not found on the system" % user)
                sys.exit(1)
            else:
                self.uid = pwd.pw_uid
                self.gid = pwd.pw_gid
        else:
            self.uid = os.geteuid()
            self.gid = os.getegid()

class TmpDirManager(object):
    """ Temporary directory manager """

    def __init__(self, tmpdir, user):
        self.user = user
        if tmpdir == None:
            self.temp_dir = tempfile.mkdtemp(prefix='xtrabackup2sql',dir=tempfile.gettempdir())
        else:
            if not os.path.exists(tmpdir):
                logging.critical("%s tmpdir does not exist" % tempdir)
                sys.exit(1)
            self.temp_dir = tmpdir
        logging.info("Temp directory is %s" % self.temp_dir)
        os.chown(self.temp_dir, os.geteuid(), self.user.gid)
        os.chmod(self.temp_dir, 0750)

    def path(self):
        return self.temp_dir

    def create_dir(self, dir):
        try:
            os.mkdir(dir, 0770)
            os.chown(dir, self.user.uid, self.user.gid)
        except OSError as e:
            logging.critical("%s %s" % (dir, e.strerror))
            sys.exit(1)

class InFileManager(object):
    """ Input file manager """

    def __init__(self, temp, infile, user):
        self.temp = temp
        self.file = infile
        self.user = user
        self.mysql_dir = os.path.join(self.temp.path(), MYSQL_DIR)

    def extract(self):
        logging.info('Start extract')

        if os.path.exists(self.mysql_dir):
            logging.warning('MySQL directory already exists skipping extract')
            return True

        self.temp.create_dir(self.mysql_dir)
        with open(self.file) as file_in:
            p = subprocess.Popen(['xbstream','-x','-C',self.mysql_dir], stdin=file_in, preexec_fn=lambda: (os.setgid(self.user.gid), os.setuid(self.user.uid)))
            p.wait()

    def decomp(self):
        logging.info('Starting decompression')
        matches = []
        for root, dirnames, filenames in os.walk(self.mysql_dir):
            for filename in fnmatch.filter(filenames, '*.qp'):
                matches.append(os.path.join(root, filename))
                file = os.path.join(root, filename)
                dir = os.path.dirname(file)
                p = subprocess.Popen(['qpress','-d',file,dir], preexec_fn=lambda: (os.setgid(self.user.gid), os.setuid(self.user.uid), os.umask(0077)))
                p.wait()
                os.unlink(file)

class MysqlManager(object):
    """ MySQL service manager """

    def __init__(self, temp, user):
        self.mysql_dir = os.path.join(temp.path(), MYSQL_DIR)
        self.mysql_temp = os.path.join(temp.path(), MYSQL_TEMP)
        self.mysql_run = os.path.join(temp.path(), "run")
        self.mysql_sock = os.path.join(self.mysql_run, 'mysqld.sock')
        self.temp_base = temp.path()
        self.temp = temp
        self.user = user

    def apply_log(self):
        logging.info("Starting log replay")
        p = subprocess.Popen(['innobackupex', '--apply-log', self.mysql_dir], preexec_fn=lambda: (os.setgid(self.user.gid), os.setuid(self.user.uid)))
        p.wait()

    def start(self):
        # Start MySQL service
        logging.info("Starting MySQL service")
        if os.path.isdir(self.mysql_temp) is False:
            self.temp.create_dir(self.mysql_temp)
        if not os.path.isdir(self.mysql_run):
            self.temp.create_dir(self.mysql_run)
        self.mysql_proc = subprocess.Popen(['mysqld',
            "--pid-file=%s" % os.path.join(self.mysql_run,'mysqld.pid'),
            '--skip-networking',
            "--user=%d" % self.user.uid,
            "--tmpdir=%s" % self.mysql_temp,
            "--socket=%s" % self.mysql_sock,
            "--datadir=%s" % self.mysql_dir,
            '--general-log=0',
            '--read-only',
            '--slow-query-log=0',
            '--skip-grant-tables',
            '--open-files-limit=32000'])

    def wait_ready(self):
        logging.info("Waiting for MySQL to become ready")
        # Connect to mysql server
        self.conn = None
        while self.conn is None:
            # Need to exit if the main mysql process failed
            if self.mysql_proc.poll() is not None:
                logging.critical("MySQL unexpectedly finished")
                sys.exit(1)
            try:
                self.conn = MySQLdb.connect(unix_socket=self.mysql_sock)
            except MySQLdb.Error as e:
                logging.debug(e[1])
                time.sleep(1)
        logging.info("MySQL is ready for connections")

    def stop(self):
        logging.info("Shutting down MySQL service")
        self.mysql_proc.terminate()
        self.mysql_proc.wait()


    def get_dbs(self):
        logging.info("Getting database list")
        self.dbs = set()
        cursor = self.conn.cursor()
        cursor.execute("SHOW DATABASES")
        self.conn.commit()
        numrows = int(cursor.rowcount)
        for x in range(0,numrows):
            row = cursor.fetchone()
            self.dbs.add(row[0])

    def filter_dbs(self, databases):
        logging.info("Filtering database set")
        dump_dbs = set()
        for pattern in databases:
            for database in fnmatch.filter(self.dbs, pattern):
                dump_dbs.add(database)
        self.dbs = dump_dbs

    def dump_dbs(self, outdir):
        for item in self.dbs:
            filename = os.path.join(outdir, '%s.sql.bz2' % item)
            logging.info("Dumping %s to %s" % (item, filename))
            with bz2file.BZ2File(filename, 'wb', compresslevel=6) as dumpfile:
                p = subprocess.Popen(['mysqldump','-S',self.mysql_sock,'--skip-lock-tables','--add-drop-table',item], stdout=subprocess.PIPE)
                for ln in p.stdout:
                    dumpfile.write(ln)
                p.wait()

def pp(message):
    click.echo(pprint.pformat(message))

@click.command()
@click.option('--user', help="user to start mysql as when running as root")
@click.option('--tmpdir', help="alternate tmp dir to use")
@click.option('--databases', help="databases to be extracted. Wildcards can be used.", multiple=True)
@click.option('--outdir', help="output dir.", default=os.getcwd(), show_default=True)
@click.option('--cleanup/--no-cleanup', default=False, help="cleanup tmp when completed", show_default=True)
@click.argument('src', type=click.Path(exists=True), nargs=1)
def main(user, tmpdir, databases, outdir, cleanup, src):
    """This script converts a binary xtrabackup or innobackupex file to a sql dump as would be produced by mysqldump"""
    logging.basicConfig(level=logging.DEBUG)
    user = UserManager(user)

    temp = TmpDirManager(tmpdir, user)

    infile = InFileManager(temp, src, user)
    infile.extract()
    infile.decomp()

    mysql = MysqlManager(temp, user)
    mysql.apply_log()
    mysql.start()
    mysql.wait_ready()

    mysql.get_dbs()

    if databases is not None:
        mysql.filter_dbs(databases)

    pp(mysql.dbs)

    mysql.dump_dbs(outdir)

    mysql.stop()

if __name__ == '__main__':
    main()
