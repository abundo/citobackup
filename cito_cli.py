#!/usr/bin/env python3

"""
Backup files, databases, applications and more using restic

For each server, do SSH to server with remote port forwarding, then run backup.
The backup program restic will initiate a ssh connection back to us through the
remote port forwarding.
"""

# ----- Start of configuration -----------------------------------------------

ETCDIR = "/etc/citobackup"
CONFIG_FILE = f"{ETCDIR}/citobackup.yaml"

# ----- End of configuration -------------------------------------------------

import argparse
import getpass
import glob
import os
import sys
import yaml
import platform

# dependencies installed with pip
from orderedattrdict import AttrDict

sys.path.insert(0, "/opt")
import ablib.utils as abutils
from ablib.email1 import Email

import cito_util
from cito_restic import Restic


class Backups:
    """
    Load all yaml configuration files, specifying what to backup
    """
    def __init__(self):
        """
        """
        self.backups = AttrDict()
        filenames = glob.glob(ETCDIR + "/*.yaml")
        for filename in filenames:
            if filename == CONFIG_FILE:
                # Ignore config file
                continue
            hostname = os.path.basename(filename)[:-5]  # default hostname
            try:
                c = abutils.yaml_load(filename)
                if "backups" in c:
                    if "hostname" in c:
                        hostname = c
                    self.backups[hostname] = c
            except yaml.YAMLError as err:
                print("Error: can't load file %s, error:", err)
                sys.exit(1)

    def __len__(self):
        return len(self.backups)

    def iter(self, hostname=None):
        """
        Return a subset (filtered on hostname) or all backups as [hostname, backup]
        Hostname can be a single host, or a comma separated list of hostnames
        """
        if hostname:
            filter_hosts = hostname.split(",")
            for hostname, backup in self.backups.items():
                if hostname in filter_hosts:
                    yield hostname, backup

        else:
            for hostname, backup in self.backups.items():
                yield hostname, backup


def main():
    config = abutils.load_config(CONFIG_FILE)
    if getpass.getuser() != "citobackup":
        print("This script must be executed as user 'citobackup'")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("cmd",
                        choices=[
                            "backup",
                            "check",
                            "init",
                            "ls",
                            "prune",
                            "setup",
                            "snapshots",
                            "stats",
                            "unlock",
                        ],
                        )
    parser.add_argument("--etcdir", default=ETCDIR, help="Directory with backup configurations")
    parser.add_argument("-H", "--hostname", help="SSH hostname")
    parser.add_argument("-p", "--port", default=22, help="SSH port")
    parser.add_argument("--id", help="Restic snapshot id")
    parser.add_argument("-d", "--debug", help="Show debug info")
    parser.add_argument("--email",
                        help="Email addresses, backup summary is sent here",
                        action="append"
                        )

    args = parser.parse_args()
    
    backups = Backups()
    restic = Restic(config=config, backups=backups)
    headers = [
        "hostname", "name", "subname", "type",
        "files<br>new", "files<br>changed", "files<br>unmodified",
        "dirs<br>new", "dirs<br>changed", "dirs<br>unmodified",
        "total<br>files", "total<br>bytes", "duration", "snapshot ID",
    ]

    if args.cmd == "backup":
        backups = restic.backup(hostname_filter=args.hostname, port=args.port)

        t = cito_util.Table(headers=headers)

        # Create table with result
        for hostname, backup in backups.iter(args.hostname):
            for ix, result in enumerate(backup.results):
                t.add_cell(result.hostname)
                t.add_cell(result.name)
                t.add_cell(result.subname)
                if result.include_stat:
                    t.add_cell(result.backup_type)
                    t.add_cell(result.files_new)
                    t.add_cell(result.files_changed)
                    t.add_cell(result.files_unmodified)

                    t.add_cell(result.dirs_new)
                    t.add_cell(result.dirs_changed)
                    t.add_cell(result.dirs_unmodified)

                    t.add_cell(result.total_files_processed)
                    tmp = cito_util.human_readable_size(result.total_bytes_processed)
                    t.add_cell(tmp)
                    t.add_cell(round(result.total_duration, 1))
                    t.add_cell(result.snapshot_id)
                else:
                    for i in range(len(headers) - 3):
                        t.add_cell("")
 
                t.add_row()

        if args.email:
            msg = t.as_html()
            email1 = Email()
            for email in args.email:
                print(f"Sending email to {email}")
                email1.send(recipient=email,
                            sender="noreply@example.com",
                            subject="citobackup on %s" % platform.node(),
                            msg=msg,
                            )
        else:
            print(t)
 
    elif args.cmd == "check":
        restic.check(hostname_filter=args.hostname)

    elif args.cmd == "init":
        if args.hostname is None:
            print("Error: must specify hostname")
            sys.exit(1)
        restic.init(hostname=args.hostname)

    elif args.cmd == "ls":
        if args.hostname is None or args.id is None:
            print("Error: must specify hostname and id")
            sys.exit(1)
        restic.ls(hostname=args.hostname, id=args.id)

    elif args.cmd == "prune":
        restic.prune(hostname_filter=args.hostname)

    elif args.cmd == "setup":
        if args.hostname is None:
            print("Error: must specify hostname")
            sys.exit(1)
        restic.setup_host(hostname=args.hostname, port=args.port)

    elif args.cmd == "snapshots":
        restic.snapshots(hostname_filter=args.hostname)

    elif args.cmd == "stats":
        restic.stats(hostname_filter=args.hostname)

    elif args.cmd == "unlock":
        restic.unlock(hostname_filter=args.hostname)

    else:
        print("Unknown command %s" % args.cmd)


if __name__ == "__main__":
    main()
