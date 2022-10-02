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
