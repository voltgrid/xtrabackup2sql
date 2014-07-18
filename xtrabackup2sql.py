#!/usr/bin/python

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

import argparse
import pprint
import tempfile
import subprocess
import fnmatch
import time
import os
import sys
import MySQLdb
import bz2

def logger(message):
  print message

def extract(file, outdir):
  logger("Beginning extraction")
  os.mkdir(outdir+'/mysql')
  file_in = open(file)
  p = subprocess.Popen(['xbstream','-x','-C',outdir+'/mysql'],stdin=file_in)
  p.wait()

def decomp(dir):
  matches = []
  for root, dirnames, filenames in os.walk(dir):
    for filename in fnmatch.filter(filenames, '*.qp'):
      matches.append(os.path.join(root, filename))
      file = os.path.join(root, filename)
      dir = os.path.dirname(file)
      subprocess.call(['qpress','-d',file,dir])
      os.unlink(file)
  #print matches

def apply_log(dir):
  subprocess.call(['innobackupex','--apply-log',dir+'/mysql'])

def main():
  # Parse command line options
  parser = argparse.ArgumentParser(description='Extract XtraBackup to sql dump files.')

  parser.add_argument('--uid', type=int,
    help='user to start mysql as, only required if running as root.')

  parser.add_argument('--tmpdir',
    help='alternate tmp dir to use.')

  parser.add_argument('--database', nargs='+',
    help='databases to be extracted. Wildcards such as ? or * can be used.')

  parser.add_argument('--outdir', default=os.getcwd(),
    help='output dir, default to current working directory.')

  parser.add_argument('--cleanup', action='store_true',
    help='set to perform clean up of temp files.')
  parser.set_defaults(cleanup=False)

  parser.add_argument('file',
    help='input file to process.')

  args = parser.parse_args()

  # Validate inputs
  if os.path.isfile(args.file) == False:
    logger("Input file does not exist")
    sys.exit(1)

  if args.tmpdir == None:
    temp_dir = tempfile.mkdtemp(prefix='xtrabackup2sql',dir=tempfile.gettempdir())
  else:
    temp_dir = args.tmpdir

  # Start processing
  pp = pprint.PrettyPrinter(indent=2)

  pp.pprint(temp_dir)
  pp.pprint(args)

  print os.getuid()
  print temp_dir

  if os.path.isdir(temp_dir+'/mysql'):
    print temp_dir+'/mysql already exists, skipping extract'
  else:
    extract(args.file,temp_dir)
  decomp(temp_dir)
  apply_log(temp_dir)

  # Start MySQL service
  if os.path.isdir(temp_dir+'/tmp') is False:
    os.mkdir(temp_dir+'/tmp')
  my_process = subprocess.Popen(['/usr/libexec/mysqld',
    '--pid-file='+temp_dir+'/mysqld.pid',
    '--skip-networking',
    '--tmpdir='+temp_dir+'/tmp',
    '--socket='+temp_dir+'/mysqld.sock',
    '--datadir='+temp_dir+'/mysql',
    '--general-log=0',
    '--read-only',
    '--slow-query-log=0',
    '--skip-grant-tables',
    '--open-files-limit=32000'])

  # Connect to mysql server
  db = None
  while db is None:
    try:
      db = MySQLdb.connect(unix_socket=temp_dir+'/mysqld.sock')
    except MySQLdb.Error as e:
      print e
      time.sleep(1)

  # Get databases
  dbs = []
  cursor = db.cursor()
  cursor.execute("SHOW DATABASES")
  db.commit()
  numrows = int(cursor.rowcount)
  for x in range(0,numrows):
    row = cursor.fetchone()
    dbs.append(row[0])

  
  if args.database is not None: 
    process_dbs = set()
    for pattern in args.database:
      for database in fnmatch.filter(dbs, pattern):
        process_dbs.add(database)
  else:
    process_dbs = set(dbs)      

  print "MySQL ready"
  for item in process_dbs:
    filename = args.outdir+'/'+item+'.sql'
    print "Dumping "+item+" to "+filename
    dumpfile = open(filename, 'w')
    subprocess.call(['mysqldump','-S',temp_dir+'/mysqld.sock','--skip-lock-tables','--add-drop-table',item], stdout=dumpfile)
    dumpfile.close
  print "Finished with databases"
  my_process.terminate()
  my_process.wait()

  if args.cleanup is True:
    for root, dirs, files in os.walk(temp_dir, topdown=False):
      for name in files:
        os.remove(os.path.join(root, name))
      for name in dirs:
        os.rmdir(os.path.join(root, name))
    os.rmdir(temp_dir)

if __name__ == "__main__":
  main()
