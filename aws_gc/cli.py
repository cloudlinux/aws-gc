import sys
import argparse

from aws_gc import clean_aws


def cli():
    parser = argparse.ArgumentParser(
        prog="Clean AWS resources",
        description="Command line tool for clean outdated VMs in cluster")

    commands = parser.add_subparsers(
        title="Commands",
        dest="command")

    cmd_clean = commands.add_parser(
        "clean",
        help="Delete outdated AWS Resources",
        description="Deletes outdated resources from a given AWS zone")
    cmd_clean.set_defaults(func=clean_aws)

    cmd_clean.add_argument(
        "-Z", "--zone", dest="aws_zone",
        default="us-east-1")
    cmd_clean.add_argument(
        "-u", "--user-key", dest="aws_user_key")
    cmd_clean.add_argument(
        "-p", "--user-secret-key", dest="aws_user_secret_key")
    cmd_clean.add_argument(
        "-O", "--outdated-hours", default=2, dest='hours')
    cmd_clean.add_argument(
        "-n", "--name-prefix", dest="aws_name_prefix",
        default="jenkins-")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    return parser.parse_args()


def main():
    args = cli()
    args.func(
        aws_zone=args.aws_zone,
        user_key=args.aws_user_key,
        user_secret_key=args.aws_user_secret_key,
        hours=args.hours,
        name_prefix=args.aws_name_prefix
    )
