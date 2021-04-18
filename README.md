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