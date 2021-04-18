
import sys
import logging
import logging.config
import yaml
import os
import os.path

from weblog.weblog import S3Log,Weblog

def merge(factory, paths, notify, filter_year):
    """
    :param factory:  function to take a line and turn it into a weblog object.
    :param paths:    list of paths to merge
    :param notify:  Do we report what was merged?
    :param filter_year: if provided, only use this year.
    """
    records = []
    dates   = []
    seen    = set()
    dups    = 0

    def merge_input(path):
        nonlocal dups,seen,dates,records
        logging.info('reading %s',path)
        for line in open(path):
            line = line.strip()
            if line=='':
                continue        # ignore blank lines
            if line in seen:
                logging.debug("dup: %s",line)
                dups += 1
                continue
            seen.add(line)
            obj = factory(line)
            if (filter_year is not None) and (filter_year != obj.dtime.year):
                filter_count += 1
                continue    # filtered

            dates.append(obj.dtime)
            records.append(obj)
            if (notify>0) and (len(records) % notify == 0):
                print(f"{len(records)}...",file=sys.stderr)

    for path in paths:
        if os.path.isfile(path):
            merge_input(path)
        elif os.path.isdir(path):
            for (root, dirs, files) in os.walk(path):
                for name in files:
                    merge_input( os.path.join(root, name))

    if notify>0:
        print(f"""
Total read: {len(records)+dups}
Dups:       {dups}
Filtered:   {filter_count}
Date Range: {min(dates)} to {max(dates)}
Total written: {len(records)}

Now sorting...
""",file=sys.stderr)
    records.sort(key=lambda a:a.dtime)
    for record in records:
        print(record.line)


if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Logfile maintenance program. Deduplicates lines and sorts, optionally filtering on year.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--merge",action='store_true',help='Merge multiple apache files; send results to stdout')
    parser.add_argument("--merges3",action='store_true',help='Merge multiple s3 files; suppress dups; send results to stdout')
    parser.add_argument("--notify",type=int, default=10000,help='How often to notify; use 0 to suppress')
    parser.add_argument("--debug",action='store_true',help='Enable debugging')
    parser.add_argument("--filter_year", type=int, help='If provided, only pass this year.')
    parser.add_argument("paths",nargs='*',help='input files or directories')
    args = parser.parse_args()

    logging.config.dictConfig( yaml.load(open('logging.yaml'),Loader=yaml.FullLoader))

    filter_count = 0

    if args.merge:
        factory = Weblog
    if args.merges3:
        factory = S3Log
    if args.merge or args.merges3:
        merge(factory, args.paths, args.notify, args.filter_year)
