# Citobackup

A program that simplifies backups using the restic tool.

Citobackup can backup files, databases and supports a number
of applications, including docker-compose containers

Developed and tested on Ubuntu 20.04


**Table of contents:**
- [Citobackup](#citobackup)
- [Setup](#setup)
  - [Backup server](#backup-server)
    - [Install citobackup](#install-citobackup)
    - [Install restic application](#install-restic-application)
    - [Create local user and SSH keys for backups](#create-local-user-and-ssh-keys-for-backups)
    - [Create main configuration files](#create-main-configuration-files)
  - [Backup source](#backup-source)
  - [Backup server, configuration file](#backup-server-configuration-file)
  - [Backup type](#backup-type)
    - [Type files](#type-files)
    - [Databases](#databases)
      - [Type mysql](#type-mysql)
      - [Postgresql](#postgresql)
    - [Applications](#applications)
      - [bitwarden_rs, docker-compose](#bitwarden_rs-docker-compose)
    - [OSTicket](#osticket)
    - [Wordpress](#wordpress)
    - [Docker-compose](#docker-compose)
- [Usage](#usage)
  - [backup](#backup)
  - [check](#check)
  - [init](#init)
  - [ls](#ls)
  - [prune](#prune)
  - [snapshots](#snapshots)
  - [stats](#stats)
  - [unlock](#unlock)
- [Misc](#misc)
  - [Periodic backups](#periodic-backups)


# Setup

## Backup server

### Install citobackup

Tools

    sudo apt install python3-pip python3-venv


Create a virtual environment

    cd /opt
    python3 -m venv citobackup


Checkout the app

    cd /opt
    git clone https://github.com/abundo/citobackup.git


Activate Python virtual environment and install dependencies

    cd /opt/citobackup
    source bin/activate
    pip3 install -r requirements.txt


### Install restic application

Visit https://github.com/restic/restic/releases

Scroll down to assets, right-click restic_0.12.0_linux_amd64.bz2 and choose
"Copy link location". Use the copied link in the wget command.

    cd /opt
    mkdir restic
    cd restic
    wget https://github.com/restic/restic/releases/download/v0.12.0/restic_0.12.0_linux_amd64.bz2
    bunzip2 restic_0.12.0_linux_amd64.bz2
    chmod +x restic_0.12.0_linux_amd64.bz2
    ln -s /opt/restic/restic_0.12.0_linux_amd64.bz2 /opt/restic/restic


### Create local user and SSH keys for backups

    sudo adduser --gecos "Citobackup user" citobackup
    sudo -iu citobackup
    ssh-keygen -N '' -f ~/.ssh/id_rsa


### Create main configuration files

Create directory, and copy example configation file.

    sudo mkdir /etc/citobackup
    cp /opt/citobackup/citobackup-example.yaml /etc/citobackup/citobackup.yaml

Adjust the configuration file in /etc/citobackup/citobackup.yaml if needed. Make sure
default_dest points where you want your backups stored.


Create a file with the key used to encrypt backups. 

**Warning**, make sure you dont loose the encryption password, if the key is lost your backups 
are probably lost. Do not change this, you cannot access the backups using citobackup
if the password file is incorrect.

     echo "secretpassword" >/etc/citobackup/restic_password.txt
     chmod 600 /etc/citobackup/restic_password.txt
     chown citobackup:citobackup /etc/citobackup/restic_password.txt


## Backup source

This needs to be done for each server that should be backed up.

If possible, use a tool such as Ansible to create remote users
and copy needed files


On remote server, create an user dedicated for backup

    sudo adduser --gecos "Citobackup user" citobackup


On remote server, create a directory for restic program file

    sudo /opt/restic


On backup server, allow passwordless login to remote server

    sudo -iu citobackup
    ssh-copy-id <remote-server>


On backup server, copy restic binary to remote server

    scp /opt/restic/restic <remote-server>:/opt/restic/restic


On remote server, allow restic to read all files

    chown root:citobackup /opt/restic/restic
    chmod 755 /opt/restic/restic
    sudo setcap cap_dac_read_search=+ep /opt/restic/restic


## Backup server, configuration file

Create a configuration file on the backup server, describing the items to 
be backed up on remote servers. Name of file should be DNS name of remote
server with the extension .yaml

Example /etc/citobackup/dns-signer.example.com.yaml

    ---
    backups:
    - name: Host files
      backup:
        - name: /etc
          type: files
          src:
          - /etc

    - name: opendnssec
      backup:
      - name: ""
        type: files
        src:
        - /etc/opendnssec
        - /var/lib/opendnssec


## Backup type

There are a number of different backup types. 


### Type files

A list of directories. Everything in these directories are backed up

Add under section backups:

    - name: Data
      backup:
        type: files
        src:
        - /home
        - /data


### Databases

#### Type mysql

Specify host, database name, username and password. A mysqldump is done and backed up.

Add under section backups:

    - name: Mysql database
      backup:
        type: mysql
        src:
          username: <mysql username>
          password: <mysql password>
          database: <mysql database name>


#### Postgresql

Specify host, database name, username and password. A pgdump is done and backed up.

Add under section backups:

    - name: Postgresql database
      backup:
        type: psql
        src:
          host: <hostnmae>
          username: <psql username>
          password: <psql password>
          database: <psql database name>


### Applications

To simplify backup, handle less configuration and avoid storing credentials, citobackup
understands a number of applications


#### bitwarden_rs, docker-compose

Todo: replace with docker-compose

- Stops docker container
- Backup files
- Starts docker container

Add under section backups:

    - name: Bitwarden RS server
      backup:
      - name: Docker-compose instance
          type: docker-compose
          src: /opt/bitwarden_rs


### OSTicket

Specify directory to osticket.
Reads the database credentials from the osticket configuration file
Backups all files and does a mysqldump of the database


Add under section backups:

    - name: Data
      backup:
        type: osticket
        src: /var/www/html/osticket


### Wordpress

Source is the wordpress directory.

- The database credentials is read from wp-config.php
- The mysql database is backed up with these credentials
- The directory tree where the wordpress configuration file is backed up

Add under section backups:

    - name: example.com website
      backup:
        type: wordpress
        src: /var/www/sites/example.com


### Docker-compose

Source is the directory that contains the docker_compose.yaml file

The docker-compose.yaml file is parsed, and volume names are retireved

- Stops docker container
- Backup files
- Backup named volumes
- Starts docker container

Add under section backups:

    - name: 
        backup:
          type: docker-compose
          src: /opt/trilium

If there is additional volumes outside the src directory, you need to add a 
file backup for these. They are NOT parsed from the docker-compose.yaml


# Usage

## backup

Run a backup on all or subset of hostnames.

Parameters:

| parameter    | Mandatory? | Description                                  |
| ------------ | ---------- | -------------------------------------------- |
| --hostname   | No         | comma separated list of hostnames            |
| --email      | No         | comma separated list of email addresses      |


Example:

    /opt/citobackup/citobackup.py backup --hostname ergotime.example.com


```
┌──────────────────────────────────────────┐
│ Running backup on ergotime.example.com   │
└──────────────────────────────────────────┘
```

| hostname             | name      | subname              | type   | files new  | files changed  | files unmodified  | dirs new  | dirs changed  | dirs unmodified  | total files  | total bytes  | duration  | snapshot ID  |
| -------------------- | --------: | -------------------: | -----: | ---------: | -------------: | ----------------: | --------: | ------------: | ---------------: | -----------: | -----------: | --------: | -----------: |
| ergotime.example.com |           |                      |        |            |                |                   |           |               |                  |              |              |           |              |
|                      |     Host  |                /etc  | files  |         0  |             0  |              577  |        0  |            0  |             233  |         577  |     3.59 MB  |      3.1  |    61f8fed5  |
|                      | Ergotime  |         Application  | files  |         0  |             0  |              577  |        0  |            0  |             233  |         577  |     3.59 MB  |      1.9  |    3945152e  |
|                      | Ergotime  | Postgresql database  |  psql  |         0  |             0  |                 0 |        0  |            0  |               0  |         577  |      0.00 N  |        0  |    45645645  |


## check

Check the integrity and consistency on a backup repository

Option is --hostname, one or multiple hostnames separated by commas. If not 
specified, all repositories are checked

Parameters:

| parameter    | Mandatory? | Description                                  |
| ------------ | ---------- | -------------------------------------------- |
| --hostname   | No         | comma separated list of hostnames            |


Example:

    /opt/citobackup/citobackup.py check --hostname ergotime.example.com

    ┌─────────────────────────────────────┐
    │ Check repo ergotime.example.com     │
    └─────────────────────────────────────┘

    using temporary cache in /tmp/restic-check-cache-368216012
    load indexes
    check all packs
    check snapshots, trees and blobs
    no errors were found
    [0:00] 100.00%  564 / 564 snapshots


## init

Initialize a new restic backup repository. The default_dest in the configation
file is appended with the hostname, and a restic repository is created there.

Parameters:

| parameter    | Mandatory? | Description                                  |
| ------------ | ---------- | -------------------------------------------- |
| --hostname   | Yes        | comma separated list of hostnames            |

Example:

    /opt/citobackup/citobackup.py check --hostname ergotime.example.com
    
    created restic repository 60dbd2b806 at /extdata1/citobackup/ergotime.example.com
    Please note that knowledge of your password is required to access
    the repository. Losing your password means that your data is
    irrecoverably lost.


## ls

List files in a backup snapshot. See command "snapshots" to get the ID

Parameters:

| parameter    | Mandatory? | Description                                  |
| ------------ | ---------- | -------------------------------------------- |
| --hostname   | Yes        | comma separated list of hostnames            |
| --id         | Yes        | snapshot id                                  |

Example:

    /opt/citobackup/citobackup.py ls --hostname dns.example.com --id 3945152e

    snapshot 3945152e of [/opt/ergotime] filtered by [] at 2021-04-21 02:19:00.426839585 +0200 +0200):
    drwxr-xr-x  1000  1000      0 2021-04-20 02:27:18 /opt
    drwxr-xr-x  1000  1000      0 2018-11-11 20:14:15 /opt/ergotime
    drwxr-xr-x  1000  1000      0 2018-10-15 21:29:00 /opt/ergotime/.git
    <output truncated>


## prune

Removes old backup data. Unless specified, 365 days/backups are kept.

Parameters:

| parameter    | Mandatory? | Description                                  |
| ------------ | ---------- | -------------------------------------------- |
| --hostname   | No         | comma separated list of hostnames            |


Example:

    /opt/citobackup/citobackup.py prune --hostname ergotime.example.com

    ┌─────────────────────────────────────┐
    │ Pruning repo ergotime.example.com   │
    └─────────────────────────────────────┘

    Keep count: 276
    Paths: ['/home/mybackup/ergotime.dump']
    Removed: None
    loading indexes...
    loading all snapshots...
    finding data that is still in use for 866 snapshots
    [0:00] 100.00%  866 / 866 snapshots

    searching used packs...
    collecting packs for deletion and repacking
    [0:00] 100.00%  642 / 642 packs processed


    to repack:            0 blobs / 0 B
    this removes          0 blobs / 0 B
    to delete:            0 blobs / 0 B
    total prune:          0 blobs / 0 B
    remaining:         3088 blobs / 165.923 MiB
    unused size after prune: 0 B (0.00% of remaining size)

    done

## snapshots

Displays snapshots and their IDs.

Parameters:

| parameter    | Mandatory? | Description                                  |
| ------------ | ---------- | -------------------------------------------- |
| --hostname   | No         | comma separated list of hostnames            |

Example:

    /opt/citobackup/citobackup.py snapshots --hostname ergotime.example.com --id


    ┌─────────────────────────────────────┐
    │ Snapshot for ergotime.example.com   │
    └─────────────────────────────────────┘

    ID        Time                 Host        Tags        Paths
    -------------------------------------------------------------------------------------
    3945152e  2021-04-21 00:19:00  ergotime                /opt/ergotime
    -------------------------------------------------------------------------------------
    1 snapshots


## stats

Display status on repository.

Note: This command can take a while to run, be patient.


Parameters:

| parameter    | Mandatory? | Description                                  |
| ------------ | ---------- | -------------------------------------------- |
| --hostname   | No         | comma separated list of hostnames            |


Example:

    /opt/citobackup/citobackup.py check --stats ergotime.example.com

    ┌────────────────────────────────────┐
    │ Stats for ergotime.example.com     │
    └────────────────────────────────────┘
    scanning...
    Stats in restore-size mode:
    Snapshots processed:   697
      Total File Count:   60689428
            Total Size:   126.465 GiB


## unlock

Removes all restic locks on repositories. Locks can be left hanging if a backup operation
was aborted.

Parameters:

| parameter    | Mandatory? | Description                                  |
| ------------ | ---------- | -------------------------------------------- |
| --hostname   | No         | comma separated list of hostnames            |

Example:

    /opt/citobackup/citobackup.py unlock --hostname ergotime.example.com

    ┌───────────────────────────────────────┐
    │ Unlocking repo ergotime.example.com   │
    └───────────────────────────────────────┘

    successfully removed locks


# Misc


## Periodic backups

To run periodic backups, create a file in /etc/cron.d/citobackup with the following content:

    MAILTO="anders@abundo.se"
    13 3 * * *   citobackup    /opt/citobackup/citobackup.py backup --email anders@abundo.se

Note that the time is specified in UTC. In the example the backup is run 03:13 every morning.
In Sweden that is 04:13 during wintertime, and 05:13 during summertime.
