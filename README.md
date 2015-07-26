## Xtrabackup2sql

Tool for extracting xtrabackup to sqldump files

## Usage
```
Usage: xtrabackup2sql.py [OPTIONS] SRC

  This script converts a binary xtrabackup or innobackupex file to a sql
  dump as would be produced by mysqldump

Options:
  --user TEXT               user to start mysql as when running as root
  --tmpdir TEXT             alternate tmp dir to use
  --databases TEXT          databases to be extracted. Wildcards can be used.
  --outdir TEXT             output dir.  [default: /]
  --cleanup / --no-cleanup  cleanup tmp when completed  [default: False]
  --help                    Show this message and exit.
```

## Requirments
- python
- percona-xtrabackup
- qpress
- xbstream
- mysql-server

### Tested on:
- CentOS 6.5
- Ubuntu 12.04

## Install 
### CentOS 6.5
```
yum install python-argparse mysql-server MySQL-python
rpm -Uhv http://www.percona.com/downloads/percona-release/percona-release-0.0-1.x86_64.rpm
yum install qpress percona-xtrabackup-20 percona-toolkit-2.1.10-1
```

### Ubuntu 12.04
Add percona package repo http://www.percona.com/doc/percona-server/5.5/installation/apt_repo.html
```
sudo apt-get install python-mysqldb mysql-server
sudo apt-get install percona-xtrabackup qpress
```

## Known Issues
- Doesn't work with Apparmor or Selinux

## TODO
- Work with non xbstream backups.
- Compress options none, bz2 or gzip. Currently only bz2.
- Add option for single file output.
- Add error checking on mysqldump.
- Prevent MySQL process from becoming orphaned.
- Clean up output. Coloured loggin, settable loglevel, hide mysql output.
- Clean up README.

## Development

```
# Fedora 22
sudo dnf install python-virtualenv MySQL-python
virtualenv --system-site-packages .venv
. .venv/bin/activate
pip install -r requirements.txt
```