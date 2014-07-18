## Description
Tool for extracting xtrabackup to sqldump files

## Usage
```
usage: xtrabackup2sql.py [-h] [--uid UID] [--tmpdir TMPDIR]
                         [--database DATABASE [DATABASE ...]]
                         [--outdir OUTDIR] [--cleanup]
                         file

Extract XtraBackup to sql dump files.

positional arguments:
  file                  input file to process.

optional arguments:
  -h, --help            show this help message and exit
  --uid UID             user to start mysql as, only required if running as
                        root.
  --tmpdir TMPDIR       alternate tmp dir to use.
  --database DATABASE [DATABASE ...]
                        databases to be extracted. Wildcards such as ? or *
                        can be used.
  --outdir OUTDIR       output dir, default to current working directory.
  --cleanup             set to perform clean up of temp files.
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
- Prevent from being run as root, implement --uid
- Work with non xbstream backups
- Compress output, bz2 or gzip
- Add option for single file output
- Add error checking on mysqldump
- Clean up output
- Clean up README
