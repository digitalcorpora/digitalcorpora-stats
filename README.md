[![codecov](https://codecov.io/gh/digitalcorpora/digitalcorpora-stats/branch/master/graph/badge.svg?token=rEVoZlToSm)](https://codecov.io/gh/digitalcorpora/digitalcorpora-stats)
This repo computes hash codes for the digitalcorpora collection stored in the s3://digitalcopora/ s3 bucket. It also downloads the bucket statistics and updates the SQL database. Becuase it has write access to the MySQL database, it runs under a different user than the https://github.com/digitalcorpora/app repo.

You can even run it in a specially-created VM.

# Getting going on a new VM
```
sudo yum install git emacs && git clone --recursive git@github.com:digitalcorpora/digitalcorpora-stats.git

cd digitalcorpora-stats
make install-dependencies
make check
```

# Stats for the Digital Corpora website
## Functionality:
- Parsed the logfiles for digitalcorpora.org
- Downloads and parses the S3 download logs
- Scans the corpora at s3://digitalcorpora/corpora/ and checks for:
  - New files that need to be hashed. They are hashed with a multi-threaded hasher.
  - Files that no longer exist. They are GCed from the database if they were never downloaded, and they are marked no longer present if they were downloaded.

## Design

- Run as a daemon/system service so whenever a new log is created, it is automatically parsed, using something like a watch folder.
- Reads database credentials from home directory.
- Options will be set using a config file
- On initial run, user will specify config file using -c option followed by the path to the config file

## Flow
- Program is run and set as a system service, using config file
- logfile name syntax and logfile syntax are specified in config file
- Data is parsed and stored in MySQL database
- MySQL database is read and output in html file under stats.digitalcorpora.org/reports
- bad logs will be sorted out, and an error log will be produced containing relevant information

## Deployment
- `$HOME/digitalcorpora-stats-dev` - Development directory
- `$HOME/digitalcorpora-stats` - Deployment directory

# Tools
## weblog
weblog is a python module that offers:

- Uniform parsing of Apache and S3 logs
- Ability to dedup logs, sort logs, and filter by year.
