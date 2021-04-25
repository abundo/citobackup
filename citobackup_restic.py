#!/usr/bin/env python3

"""
Manage restic, using the CLI
"""

import json
import yaml
import traceback

import citobackup_util
from citobackup_ssh import SSH


# ----- globals --------------------------------------------------------

backup_results = []

# ----------------------------------------------------------------------


class Restic:
    """
    Manage restic backups
    """

    def __init__(self, config=None, backups=None):
        self.config = config
        self.backups = backups

    def print_header(self, msg):
        print()
        print("\u250c%s\u2510" % ("\u2500" * (len(msg) + 2)))
        print("\u2502 %s \u2502" % msg)
        print("\u2514%s\u2518" % ("\u2500" * (len(msg) + 2)))
        print()

    def print_subheader(self, msg):
        print()
        print("\u2500" * 5, msg, "\u2500" * 5)
        print()

    def backup_print_summary(self, r):
        print("Summary:")
        print("  files_new             :", r.get("files_new", ""))
        print("  files_changed         :", r.get("files_changed", ""))
        print("  files_unmodified      :", r.get("files_unmodified", ""))
        print("  dirs_new              :", r.get("dirs_new", ""))
        print("  dirs_changed          :", r.get("dirs_changed", ""))
        print("  dirs_unmodified       :", r.get("dirs_unmodified", ""))
        print("  data_added            :", r.get("data_added", ""))
        print("  total_files_processed :", r.get("total_files_processed", ""))
        print("  total_bytes_processed :", r.get("total_bytes_processed", ""))
        print("  total_duration        :", r.get("total_duration", ""))
        print("  snapshot_id           :", r.get("snapshot_id", ""))

    def add_backup_output(self, output=None, result=None):
        """
        in
          output, text from restic json outpt
          result, collects backup result
        """
        for r in output:
            if "message_type" in r:
                if r["message_type"] == "error":
                    try:
                        msg = print("Error %s(%s): %s" % (r["error"]["Op"], r["error"]["Err"], r["item"]))
                    except KeyError as err:
                        msg = f"Unknown error: {err}"
                    result.add_error(msg)
                elif r["message_type"] == "summary":
                    self.backup_print_summary(r)
                    result.files_new = r["files_new"]
                    result.files_changed = r["files_changed"]
                    result.files_unmodified = r["files_unmodified"]
                    result.dirs_new = r["dirs_new"]
                    result.dirs_changed = r["dirs_changed"]
                    result.dirs_unmodified = r["dirs_unmodified"]
                    result.total_files_processed = r["total_files_processed"]
                    result.total_bytes_processed = r["total_bytes_processed"]
                    result.total_duration = r["total_duration"]
                    result.snapshot_id = r["snapshot_id"]

                    # Data from stdin, total_bytes_processed is zero
                    data_added = r.get("data_added", None)
                    if data_added > 0 and result.total_bytes_processed == 0:
                        result.total_bytes_processed = data_added
                    
    def backup_docker_compose(self, remote_srv, src, results=None, name=None, subname=None):
        """
        Open and parse the docker-compose.yaml file
        backup database and configuration files
        """

        result = citobackup_util.Backup_Result()
        result.name = name
        result.subname = ""
        result.backup_type = "docker-compose"
        result.include_stat = False
        results.add(result)

        self.print_subheader(f"Stop {name}")
        cmd = f"cd {src}; docker-compose stop"
        output = remote_srv.ssh(cmd)
        print("output", output)

        self.backup_files(remote_srv, [src], results=results, name="", subname=src, tags=[name])

        # Get the docker-compose.yaml file
        dc_file = f"{src}/docker-compose.yaml"
        if not remote_srv.file_exists(dc_file):
            dc_file = f"{src}/docker-compose.yml"
        if not remote_srv.file_exists(dc_file):
            print("Error: cannot find docker-compose.yaml file")
            return
        
        dc_content = remote_srv.read_from_file(dc_file)
        dc = yaml.safe_load(dc_content)

        basename = src.split("/")[-1]
        volumes = dc.get("volumes", None)
        if volumes:
            for volume in volumes.keys():
                volume_name = f"{basename}_{volume}"
                print("backing up volume", volume_name)

                if 1:
                    # Ugly, copy volume directly from filesystem, until we find a better
                    # way to handle named volumes
                    # Host now have the volume files in /tmp/citobackup/{volume_name}, backup the files
                    src2 = f"/var/lib/docker/volumes/{volume_name}"
                    self.backup_files(remote_srv, [src2], results=results, name="", subname=volume_name, tags=[name, f"Volume {volume_name}"], backup_type="Volume")

                else:
                    # Start a container, mounting the volume
                    cmd = f"docker container run --rm --name citobackup-alpine -v {volume_name}:/mnt/{volume_name}:ro -v /tmp/citobackup:/mnt:ro -dit alpine /bin/ash"
                    print("cmd", cmd)
                    output = remote_srv.ssh(cmd.split(" "))
                    print("output", output)

                    # Host now have the volume files in /tmp/citobackup/{volume_name}, backup the files
                    src2 = f"/tmp/citobackup/{volume_name}"
                    self.backup_files(remote_srv, [src2], results=results, name="", subname=f"Volume {volume_name}", tags=[name, f"Volume {volume_name}"])

                    # Stop the container
                    # cmd = f"docker attach {container_id} ; exit"
                    cmd = "docker stop citobackup-alpine"
                    print("cmd", cmd)
                    output = remote_srv.ssh(cmd.split(" "))
                    print("output", output)

                    cmd = "fdocker rm {container_id}"
                    print("cmd", cmd)
                    output = remote_srv.ssh(cmd.split(" "))
                    print("output", output)

                    cmd = "docker ps | grep citobackup"
                    print("cmd", cmd)
                    output = remote_srv.ssh(cmd.split(" "))
                    print("output", output)

        self.print_subheader(f"Start {name}")
        cmd = f"cd {src}; docker-compose start"
        output = remote_srv.ssh(cmd)
        print("output", output)

    def backup_esxi(self, remote_srv, src, results=None, name=None, subname=None):
        """
        Backup an ESXI VM (Virtual Machine).
        If the VM is running:
            - create an snapshot
            - backup the snapshot
            - remove snapshot
        if the VM is not running:
            - backup the VM

        dedup is very important here, VMs are LARGE!

        before snapshopt
        .vmx,.nvram, .vmsd, .vmdk

        during snapshot
        *-flat.vmdk

        """
        result = citobackup_util.Backup_Result()
        result.name = name
        result.subname = subname
        result.backup_type = "esxi"

        # vim-cmd vmsvc/getallvms
        #    parse out the vm id

        # Check if there is an old snapshot from previous backups, if so remove it
        # and send notify, last backup wasn't 100% correct
        # vim-cmd vmsvc/snapshot.remove <id>

        # Copy files, we do this before snapshot, so there is no mentioning of the
        # snapshot in these files. It makes restore easier.
        #    .vmx .nvram .vmsd .vmdk
        #
        # create snapshot
        # vim-cmd vmsvc/snapshot.create <id> backup backup-snapshot 0 0

        # copy the virtual disk, it is now in read-only
        #
        # delete the snapshot
        # vim-cmd vmsvc/snapshot.remove <id>

        results.add(result)

    def backup_files(self, remote_srv, src, results=None, name=None, subname=None, tags=None, backup_type="files"):
        """
        Backup files
        We don't compress the backup, compression and dedup is not great
        """
        self.print_subheader("Backup files")
        result = citobackup_util.Backup_Result()
        result.name = name
        result.subname = subname
        result.backup_type = backup_type

        print("Backup files")
        for path in src:
            print(f"  {path}")
        print()

        # Write and copy list of files to backup if more than one file
        if len(src) > 1:
            remote_srv.write_to_file(filename="/tmp/backup_list", data="\n".join(src))

        # Run backup
        cmd = []
        cmd += ["/opt/restic/restic"]
        cmd += ["-r", "sftp:127.0.0.1:%s/%s" % (self.config.default_dest, remote_srv.hostname)]
        cmd += ["backup"]
        cmd += ["-p", "/tmp/restic_password.txt"]
        cmd += ["--one-file-system"]
        cmd += ["--json"]
        if len(src) > 1:
            cmd += ["--files-from", "/tmp/backup_list"]
        else:
            cmd += [src[0]]
        if tags:
            for tag in tags:
                cmd += ["--tag", f'"{tag}"']
        print(" ".join(cmd))
        output = remote_srv.ssh(cmd, decode_json=True)
        self.add_backup_output(output=output, result=result)
        results.add(result)

    def backup_mysql(self, remote_srv, src, results=None, name=None, subname=None):
        """
        Backup a mysql/mariadb database
        We don't compress the backup, compression makes dedup very hard
        """
        self.print_subheader("Backup mysql database %s" % src["database"])
        result = citobackup_util.Backup_Result()
        result.name = name
        result.subname = subname
        result.backup_type = "mysql"

        # Run backup
        cmdfile = "/tmp/mysql_backup.sh"

        cmd = []
        cmd += ["/usr/bin/mysqldump"]
        cmd += ["--user=%s" % src["username"]]
        cmd += ["--password=%s" % src["password"]]
        cmd += [src["database"]]
        cmd += ["|"]

        cmd += ["/opt/restic/restic"]
        cmd += ["-r", "sftp:127.0.0.1:%s/%s" % (self.config.default_dest, remote_srv.hostname)]
        cmd += ["backup"]
        cmd += ["-p", "/tmp/restic_password.txt"]

        cmd += ["--stdin"]
        cmd += ["--stdin-filename", "%s.mysql.dump" % src["database"]]
        cmd += ["--json"]

        cmd = "#!/bin/bash\n" + " ".join(cmd)
        remote_srv.write_to_file(filename=cmdfile, data=cmd, mode="700")
      
        output = remote_srv.ssh(cmdfile, decode_json=True)
        self.add_backup_output(output=output, result=result)
        results.add(result)

        # Cleanup
        # remote_srv.ssh(f"rm {cmdfile}")

    def backup_osticket(self, remote_srv, src, results=None, name=None, subname=None):
        """
        Make a complete backup of osticket, and its mysql database
        """

        self.print_subheader("Backup osticket site %s" % src)
        result = citobackup_util.Backup_Result()
        result.name = name
        result.subname = subname
        result.backup_type = "osticket"

        # Parse the osticket config file, get mysql parameters
        c = "'"
        c += f'include("{src}/include/ost-config.php"); '
        c += '$a=array('
        c += '  "host"=>DBHOST, '
        c += '  "database"=>DBNAME, '
        c += '  "username"=>DBUSER, '
        c += '  "password"=>DBPASS, '
        c += ');'
        c += 'print(json_encode($a)); '
        c += "'"
        
        cmd = ["php", "-r", c]
        lines = remote_srv.ssh(cmd)
        param = json.loads(lines)
        print("param", param)

        # Backup the osticket files
        self.backup_files(remote_srv, [src], results=results)

        # Backup the mysql database
        self.backup_mysql(remote_srv, param, results=results)

    def backup_psql(self, remote_srv, src, results=None, name=None, subname=None):
        """
        Backup a postgresql database
        We don't compress the backup, compression makes dedup very hard
        """
        self.print_subheader("Backup postgresql database %s" % src["database"])
        result = citobackup_util.Backup_Result()
        result.name = name
        result.subname = subname
        result.backup_type = "psql"

        # Write password to .pgpass
        # hostname:port:database:username:password
        pgpass_file = "/home/citobackup/.pgpass"
        line = "%s:%s:%s:%s:%s" % (
            src["host"],
            "*",
            src["database"],
            src["username"],
            src["password"],
        )
        remote_srv.write_to_file(filename=pgpass_file, data=line, mode="600")

        # Write command file to remote host
        cmdfile = "/tmp/psql_backup.sh"
        cmd = []
        cmd += ["pg_dump"]
        cmd += ["-h", src["host"]]
        cmd += ["-U", src["username"]]
        cmd += [src["database"]]
        cmd += ["|"]

        cmd += ["/opt/restic/restic"]
        cmd += ["-r", "sftp:127.0.0.1:%s/%s" % (self.config.default_dest, remote_srv.hostname), "backup"]
        cmd += ["-p", "/tmp/restic_password.txt"]

        cmd += ["--stdin"]
        cmd += ["--stdin-filename", "%s.dump" % src["database"]]
        cmd += ["--json"]

        cmd = "#!/bin/bash\n" + " ".join(cmd)
        remote_srv.write_to_file(filename=cmdfile, data=cmd, mode="700")
       
        output = remote_srv.ssh(cmdfile, decode_json=True)
        self.add_backup_output(output=output, result=result)
        results.add(result)

        # Cleanup
        # remote_srv.ssh(f"rm {pgpass_file}")
        # remote_srv.ssh(f"rm {cmdfile}")

    def backup_wordpress(self, remote_srv, src, results=None, name=None, subname=None):
        """
        Backup a wordpress instance
        Backups all files, and the mysql database, suitable for a full recovery
        """
        self.print_subheader("Backup wordpress site %s" % src)
        result = citobackup_util.Backup_Result()
        result.name = "Wordpress site"
        result.subname = name
        result.include_stat = False
        results.add(result)

        # Parse the wordpress config file, get mysql parameters
        c = "'"
        c += f'include("{src}/wp-config.php"); '
        c += '$a=array('
        c += '  "host"=>DB_HOST, '
        c += '  "database"=>DB_NAME, '
        c += '  "username"=>DB_USER, '
        c += '  "password"=>DB_PASSWORD, '
        c += ');'
        c += 'print(json_encode($a)); '
        c += "'"
        
        cmd = ["php", "-r", c]
        lines = remote_srv.ssh(cmd)
        param = json.loads(lines)

        # Backup the wordpress files
        self.backup_files(remote_srv, [src], results=results, name="", subname="")

        # Backup the mysql database
        self.backup_mysql(remote_srv, param, results=results, name="", subname="")

    def backup_host(self, hostname, backup):
        """
        Copy needed files to server, and run backup
        """
        self.print_header("Running backup on %s" % hostname)
        backup.results = citobackup_util.Backup_Results()

        # Initialize SSH to remote server
        port = backup.get("port", None)
        if port:
            port = int(port)
        remote_srv = SSH(hostname=hostname, port=port, username="citobackup")

        remote_srv.connect()

        # Create .ssh dir and set permissions
        remote_srv.ssh(["mkdir", "/home/citobackup/.ssh"])
        remote_srv.chmod(path="/home/citobackup/.ssh", mode="700")

        # generate keys on remote system, if there are none
        if not remote_srv.file_exists(".ssh/id_rsa"):
            print("Generating keys on remote system")
            remote_srv.ssh(["ssh-keygen", "-N", "''", "-f", ".ssh/id_rsa"])

        # Fetch remote pub key, and add to our local authorized_keys
        remote_id_rsa_pub = remote_srv.read_from_file(".ssh/id_rsa.pub")
        remote_srv.add_authorized_keys(remote_id_rsa_pub)

        # Generate remote known_host
        remote_srv.ssh(["ssh-keyscan", "-p", "44444", "127.0.0.1", ">.ssh/known_hosts"])

        # copy .ssh configuration
        remote_srv.scp(local="/opt/citobackup/remote/ssh-config", remote=".ssh/config", mode="600")

        # Check if there is a remote backup binary
        # remote_srv.scp(local="/opt/restic/restic", remote=".")

        # copy restic password file
        remote_srv.scp(local="/etc/citobackup/restic_password.txt", remote="/tmp/restic_password.txt", mode="600")

        result = citobackup_util.Backup_Result()
        result.hostname = hostname
        result.include_stat = False

        backup.results.add(result)

        for backup1 in backup["backups"]:
            name = backup1.get("name", "")
            backup_list = backup1.get("backup", [])
            for backup2 in backup_list:
                subname = backup2.get("name", "")
                if backup2.type == "docker-compose":
                    self.backup_docker_compose(remote_srv, backup2.src, results=backup.results, name=name, subname=subname)

                elif backup2.type == "files":
                    self.backup_files(remote_srv, backup2.src, results=backup.results, name=name, subname=subname)

                elif backup2.type == "mysql":
                    self.backup_mysql(remote_srv, backup2.src, results=backup.results, name=name, subname=subname)

                elif backup2.type == "osticket":
                    self.backup_osticket(remote_srv, backup2.src, results=backup.results, name=name, subname=subname)

                elif backup2.type == "psql":
                    self.backup_psql(remote_srv, backup2.src, results=backup.results, name=name, subname=subname)

                elif backup2.type == "wordpress":
                    self.backup_wordpress(remote_srv, backup2.src, results=backup.results, name=name, subname=subname)

                else:
                    print("Error: Unknown backup type %s" % backup2.type)

        remote_srv.unlink(path="/tmp/restic_password.txt")

        remote_srv.disconnect()
    
    def backup(self, hostname_filter=None, port=None):
        """
        Backup hosts
        """
        for hostname, backup in self.backups.iter(hostname_filter):
            try:
                self.backup_host(hostname, backup)
            except:
                print("----- Error during backup -----")
                print(traceback.format_exc())

        return self.backups

    def check(self, hostname_filter=None):
        """
        """
        for hostname, backup in self.backups.iter(hostname_filter):
            self.print_header("Check repo %s" % hostname)
            cmd = ["/opt/restic/restic"]
            cmd += ["-r", "%s/%s" % (self.config.default_dest, hostname)]
            cmd += ["-p", "/etc/citobackup/restic_password.txt"]
            cmd += ["check", "--no-lock", "--json"]
            r, txt = citobackup_util.run_cmd(cmd)
            print(txt)

    def init(self, hostname=None):
        """
        """
        cmd = ["/opt/restic/restic"]
        cmd += ["-r", "%s/%s" % (self.config.default_dest, hostname)]
        cmd += ["init"]
        cmd += ["-p", "/etc/citobackup/restic_password.txt"]
        r, txt = citobackup_util.run_cmd(cmd)
        print(txt)

    def ls(self, hostname=None, id=None):
        """
        """
        cmd = ["/opt/restic/restic"]
        cmd += ["-r", "%s/%s" % (self.config.default_dest, hostname)]
        cmd += ["-p", "/etc/citobackup/restic_password.txt"]
        cmd += ["ls", "-l", id]
        r, txt = citobackup_util.run_cmd(cmd)
        print(txt)

    def prune(self, hostname_filter=None, days=365):
        """
        """
        for hostname, backup in self.backups.iter(hostname_filter):
            self.print_header("Pruning repo %s" % hostname)
            cmd = ["/opt/restic/restic"]
            cmd += ["-r", "%s/%s" % (self.config.default_dest, hostname)]
            cmd += ["-p", "/etc/citobackup/restic_password.txt"]
            cmd += ["forget", "--prune", "--keep-daily", str(days), "--json"]
            print(cmd)
            r, txt = citobackup_util.run_cmd(cmd)
            # print("r", r)
            # print(txt)

            try:
                tmp = txt.split("\n")
                ret = json.loads(tmp[0])
            except json.decoder.JSONDecodeError as err:
                print("Error:", err)

            print("Keep count:", len(ret[0]["keep"]))
            print("Paths:", ret[0]["paths"])
            print("Removed:", ret[0]["remove"])
            for s in tmp[1:]:
                print(s)

    def snapshots(self, hostname_filter=None):
        """
        Show all snapshots
        """
        for hostname, backup in self.backups.iter(hostname_filter):
            self.print_header("Snapshot for %s" % hostname)
            cmd = ["/opt/restic/restic"]
            cmd += ["-r", "%s/%s" % (self.config.default_dest, hostname)]
            cmd += ["snapshots"]
            cmd += ["-p", "/etc/citobackup/restic_password.txt"]
            r, txt = citobackup_util.run_cmd(cmd)
            print(txt)
            print()

    def stats(self, hostname_filter=None):
        """
        Show statistics
        """
        for hostname, backup in self.backups.iter(hostname_filter):
            self.print_header("Stats for %s" % hostname)
            cmd = ["/opt/restic/restic"]
            cmd += ["-r", "%s/%s" % (self.config.default_dest, hostname)]
            cmd += ["-p", "/etc/citobackup/restic_password.txt", "stats"]
            r, txt = citobackup_util.run_cmd(cmd)
            print(txt)

    def unlock(self, hostname_filter=None, days=365):
        """
        """
        for hostname, backup in self.backups.iter(hostname_filter):
            self.print_header("Unlocking repo %s" % hostname)
            cmd = ["/opt/restic/restic"]
            cmd += ["-r", "%s/%s" % (self.config.default_dest, hostname)]
            cmd += ["-p", "/etc/citobackup/restic_password.txt", "unlock", "--json"]
            r, txt = citobackup_util.run_cmd(cmd)
            print(txt)
