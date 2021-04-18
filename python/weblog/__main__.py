
from weblog.weblog import S3Log,Weblog
import sys
import logging
import logging.config
import yaml

if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Logfile maintenance program. Deduplicates lines and sorts, optionally filtering on year.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--merge",action='store_true',help='Merge multiple apache files; send results to stdout')
    parser.add_argument("--merges3",action='store_true',help='Merge multiple s3 files; suppress dups; send results to stdout')
    parser.add_argument("--notify",type=int, default=10000,help='How often to notify; use 0 to suppress')
    parser.add_argument("--debug",action='store_true',help='Enable debugging')
    parser.add_argument("--filter_year", type=int, help='If provided, only pass this year.')
    parser.add_argument("files",nargs='*',help='input files')
    args = parser.parse_args()

    logging.config.dictConfig( yaml.load(open('logging.yaml'),Loader=yaml.FullLoader))

    filter_count = 0

    if args.merge:
        factory = Weblog
    if args.merges3:
        factory = S3Log
    if args.merge or args.merges3:
        records = []
        seen    = set()
        dups    = 0
        for fn in args.files:
            logging.debug('reading %s',fn)
            for line in open(fn):
                if line in seen:
                    logging.debug("dup: %s",line)
                    dups += 1
                    continue
                obj = factory(line)
                if (args.filter_year is not None) and (args.filter_year != obj.time.year):
                    filter_count += 1
                    continue    # filtered

                records.append(obj)
                if (args.notify>0) and (len(records) % args.notify == 0):
                    print(f"{len(records)}...",file=sys.stderr)
        if args.notify>0:
            print("Total read: ",len(records)+dups,file=sys.stderr)
            print("Dups:       ",dups,file=sys.stderr)
            print("Filtered:   ",filter_count,file=sys.stderr)
            print("sorting",file=sys.stderr)
        records.sort(key=lambda a:a.time)
        for record in records:
            print(record.line)
