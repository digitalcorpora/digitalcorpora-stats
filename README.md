[![codecov](https://codecov.io/gh/digitalcorpora/digitalcorpora-stats/branch/master/graph/badge.svg?token=rEVoZlToSm)](https://codecov.io/gh/digitalcorpora/digitalcorpora-stats)
This repo computes hash codes for the digitalcorpora collection stored in the s3://digitalcopora/ s3 bucket. It also downloads the bucket statistics and updates the SQL database. Becuase it has write access to the MySQL database, it runs under a different user than the https://github.com/digitalcorpora/app repo.

You can even run it in a specially-created VM.

# Getting going on a new VM
```
sudo yum install git emacs && git clone --recursive git@github.com:digitalcorpo\
ra/digitalcorpora-stats.git
cd digitalcorpora-stats
make install-dependencies
make check
```

# digitalcorpora-stats
- Designing to parse Apache logfiles for digitalcorpora.org

# Design
- Run as a daemon/system service so whenever a new log is created, it is automatically parsed, using something like a watch folder.
- Options will be set using a config file
- On initial run, user will specify config file using -c option followed by the path to the config file

# Flow
- Program is run and set as a system service, using config file
- logfile name syntax and logfile syntax are specified in config file
- Data is parsed and stored in MySQL database
- MySQL database is read and output in html file under stats.digitalcorpora.org/reports
- bad logs will be sorted out, and an error log will be produced containing relevant information

# Tools
## weblog
weblog is a python module that offers:

- Uniform parsing of Apache and S3 logs
- Ability to dedup logs, sort logs, and filter by year.
