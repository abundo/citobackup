#!/usr/bin/env python3

"""
Manage remote host, using SSH
"""

import json
import os
import subprocess
import sys
import tempfile

import citobackup_util


class SSH(dict):
    """
    """
    def __init__(self, hostname, port=None, username=None, password=None):
        super().__init__()
        if port is None:
            port = 22

        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password

        self.persistent_socket = "/tmp/master-%s@%s:%s" % (self.username, self.hostname, self.port)

        # Check and generate local ssh keys
        # Used to connect to remote server
        # This also creates the .ssh directory if needed
        self.keygen("id_rsa")

        # Close any old persistent connections
        self.disconnect()

    def connect(self):
        print("Open a persistent connection to %s:%s with reverse port forwarding back to us" % (self.hostname, self.port))
        # cmd = "ssh -6 -M -S %s -p %s -R 44444:[::1]:22 %s" % (self.persistent_socket, self.port, self.hostname)
        cmd = ["/usr/bin/ssh"]
        cmd += ["-6"]
        cmd += ["-M"]
        cmd += ["-S", self.persistent_socket]
        cmd += ["-p", str(self.port)]
        cmd += ["-R", "44444:[::1]:22"]
        cmd += [self.hostname]
        print("cmd", " ".join(cmd))
        self.p = subprocess.Popen(cmd, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    def disconnect(self, close_p=False):
        if close_p:
            print("Closing control master process")
            self.p.stdin.write(b"logout\n")
            self.p.join()

        # Close the master process
        if os.path.exists(self.persistent_socket):
            print("Removing persistent socket")
            cmd = ["/usr/bin/ssh", "-S", self.persistent_socket, "-O", "exit", self.hostname]
            r, txt = citobackup_util.run_cmd(cmd)
            return txt
        return ""

    def keygen(self, keyname):
        """
        Create ssh keys if they dont exist
        """
        priv_key = os.path.expanduser("/home/citobackup/.ssh/%s" % keyname)
        pub_key = os.path.expanduser("/home/citobackup/.ssh/%s.pub" % keyname)
        found = True
        if not os.path.exists(priv_key):
            found = False
        if not os.path.exists(pub_key):
            found = False

        if not found:
            print(f"Creating key for {keyname} with no password")
            cmd = ["ssh-keygen", "-f", priv_key, "-N", '""']
            r, txt = citobackup_util.run_cmd(cmd)
            print("r =", r)
            print(txt)

    def get_pubkey(self, keyname):
        """
        """
        pub_key = os.path.expanduser("/home/citobackup/.ssh/%s.pub" % keyname)
        with open(pub_key, "r") as f:
            new_key = f.readline().strip()
        return new_key

    def add_authorized_keys(self, new_key):
        """
        Add a key to authorized_keys
        """
        # Search our local authorized_keys for the new key, add if it does not exist
        file = os.path.expanduser("/home/citobackup/.ssh/authorized_keys")
        found = False
        if not os.path.exists(file):
            # Create file
            with open(file, "w") as f:
                f.write(new_key + "\n")
            os.chmod(file, 0o600)
            return

        # Check if we already have the key
        with open(file, "r") as f:
            line = f.readline()
            while line:
                line = line.strip()
                if line == new_key:
                    found = True
                    break
                line = f.readline()

        if not found:
            # The key did not exist, add key
            with open(file, "a") as f:
                f.write(new_key + "\n")

    def get_own_server_key(self):
        # Get our server key
        # cmd = "ssh-keyscan -t rsa 127.0.0.1"
        cmd = ["/usr/bin/ssh-keyscan", "-t", "rsa", "127.0.0.1"]
        r = subprocess.run(cmd, stdout=subprocess.PIPE)
        local_key = r.stdout.decode()
        return local_key

    def ssh(self, cmd, decode_json=False):
        """
        """
        if isinstance(cmd, str):
            cmd = [cmd]

        c = []
        if self.password:
            c += ["sshpass", "-p", self.password]
        c += ["ssh", "-6", "-S", self.persistent_socket]

        if self.port:
            c += ["-p", str(self.port)]

        if self.username:
            c += [f"{self.username}@{self.hostname}"]
        else:
            c += [self.hostname]

        c += cmd

        # print("c =", c)
        if decode_json:
            res = []
            p = subprocess.Popen(c, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            while True:
                line = p.stdout.readline()
                if not line:
                    break
                if not line.strip():
                    continue
                if line[0] != "{":
                    # not json
                    print("Unknown", line)
                    continue
                # print("line", line)
                try:
                    tmp = json.loads(line)
                except json.decoder.JSONDecodeError as err:
                    # if line.startswith(b"subprocess ssh: Warning: Permanently added"):
                    #     continue
                    print("Error json decoding", err)
                    print("  line:", line)
                    continue
                if "message_type" in tmp:
                    if tmp["message_type"] == "error":
                        res.append(tmp)
                    elif tmp["message_type"] == "summary":
                        res.append(tmp)
                    elif tmp["message_type"] == "status":
                        if citobackup_util.write_console:
                            s = ""
                            if "seconds_elapsed" in tmp:
                                s += "Seconds elapsed: %i" % tmp["seconds_elapsed"]
                            if "percent_done" in tmp:
                                s += ", Percent done: %i" % (tmp["percent_done"] * 100)
                            if "files_done" in tmp:
                                s += ", Files done: %i" % tmp["files_done"]
                            print("\r%s\033[K" % s, end="")
                    else:
                        print("Unknown message", tmp)
                else:
                    print("Unknown message", tmp)
            if citobackup_util.write_console:
                print("\r%s\033[K" % "", end="")
            print()
            return res
        else:
            r, txt = citobackup_util.run_cmd(c)
            return txt

    def scp(self, local=None, remote=None, mode=None):
        """
        """
        c = []
        if self.password:
            c += ["/usr/bin/sshpass", "-p", self.password]
        c += ["/usr/bin/scp", "-6"]
        c += ["-o", "ControlPath=%s" % self.persistent_socket]
        if self.port:
            c += ["-P", str(self.port)]
        if local:
            c += [local]

        tmp = ""
        if self.username:
            tmp += "%s@" % self.username
        tmp += "%s:" % self.hostname
        tmp += remote
        c += [tmp]

        r, txt = citobackup_util.run_cmd(c)

        if mode:
            self.chmod(remote, mode)
        return txt

    def rsync(self, local=None, remote=None):
        """
        rsync -e "ssh -o 'ControlPath=$HOME/.ssh/ctl/%L-%r@%h:%p'" ...
        """
        c = []
        if self.password:
            c += ["/usr/bin/sshpass", "-p", self.password]
        c += ["/usr/bin/rsync", "-c", "--inplace"]
        c += ["-e", '"ssh -o \"Controlpath=%s\"']
        if local:
            c += [local]
        if remote:
            c += [remote]
        r, txt = citobackup_util.run_cmd(c)
        return txt

    # ----- convenience functions -----

    def file_exists(self, filename):
        """
        Check if filename exist on remote server
        Returns True if file exist
        """
        r = self.ssh('[[ -f %s ]] && echo "exists_yes" || echo "exists_no";' % filename)
        return "exists_yes" in r

    def read_from_file(self, filename):
        """
        Read file from remote
        Return data as string
        """
        cmd = ["cat", filename]
        lines = self.ssh(cmd)
        return lines

    def write_to_file(self, filename=None, data=None, mode=None):
        """
        Write string as remote file
        """
        with tempfile.NamedTemporaryFile(mode="w") as f:
            f.write(data)
            f.flush()
            self.scp(local=f.name, remote=filename)
        if mode:
            self.chmod(path=filename, mode=mode)

    # ----- trying to mimic API in sftp -----

    def chdir(self, path=None):
        raise RuntimeError("Not implemented")
    
    def chmod(self, path=None, mode=None):
        cmd = ["/bin/chmod", mode, path]
        lines = self.ssh(cmd)
        return lines

    def chown(self, path, uid, gid):
        raise RuntimeError("Not implemented")

    def file_(filename, mode="r", bufsize=-1):
        """
        Note, file is a reserved keyword in python
        """
        raise RuntimeError("Not implemented")

    def get(self, remotepath, localpath, callback=None):
        raise RuntimeError("Not implemented")

    def getcwd(self):
        raise RuntimeError("Not implemented")

    def listdir(self, path="."):
        raise RuntimeError("Not implemented")

    def lstat(self, path):
        raise RuntimeError("Not implemented")

    def mkdir(self, path, mode=511):
        raise RuntimeError("Not implemented")

    def open(self, filename, mode="r", bufsize=-1):
        raise RuntimeError("Not implemented")

    def put(self, localpath, remotepath, callback=None, confirm=True):
        raise RuntimeError("Not implemented")

    def remove(self, path):
        raise RuntimeError("Not implemented")

    def rename(self, oldpath, newpath):
        raise RuntimeError("Not implemented")

    def rmdir(self, path):
        raise RuntimeError("Not implemented")

    def stat(self, path):
        raise RuntimeError("Not implemented")

    def symlink(self, source, dest):
        raise RuntimeError("Not implemented")

    def truncate(self, path, size):
        raise RuntimeError("Not implemented")

    def unlink(self, path=None):
        cmd = ["rm", path]
        lines = self.ssh(cmd)
        return lines


if __name__ == "__main__":
    s = SSH(hostname="ns2.abundo.se", port=33333)
    for dir in ["/tmp", "/var"]:
        print("-"*79)
        print(s.ssh("ls %s" % dir))
    s.disconnect()
    sys.exit(1)
