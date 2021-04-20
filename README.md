# Citobackup

A program that simplifies backups using the restic tool.

Citobackup can backup files, databases and supports a number
of applications, including docker-compose containers

Developed and tested on Ubuntu 20.04


# Installation

Install tools

    sudo apt install python3-pip


Checkout the app

    cd /opt
    git clone 


Activate Python virtual environment

    cd /opt/citobackup
    source bin/activate


Install dependencies

    pip3 install -r requirements.txt


# Configuration

## Backup server

### Create local user and SSH keys for backups

    sudo adduser --gecos "Citobackup user" citobackup
    sudo -iu citobackup
    ssh-keygen -N '' -f ~/.ssh/id_rsa


### Install citobackup code

    cd /opt
    git clone https://github.com/abundo/citobackup.git


### Install restic binaries

Visit https://github.com/restic/restic/releases

Scroll down to assets and right-click the binary file that matches your system.
For examle right-click restic_0.12.0_linux_amd64.bz2 and choose "Copy link location".
Use the copied link in the wget command.

    cd /opt
    mkdir restic
    cd restic
    wget https://github.com/restic/restic/releases/download/v0.12.0/restic_0.12.0_linux_amd64.bz2
    bunzip2 restic_0.12.0_linux_amd64.bz2
    chmod +x restic_0.12.0_linux_amd64.bz2
    ln -s /opt/restic/restic_0.12.0_linux_amd64.bz2 /opt/restic/restic


### Create main configuration files

Create directory, and copy example configation file.

    sudo mkdir /etc/citobackup
    cp /opt/citobackup/citobackup-example.yaml /etc/citobackup/citobackup.yaml

Adjust the configuration file in /etc/citobackup/citobackup.yaml if needed. Make sure
default_dest points where you want your backups stored.


Create a file with the password used to encrypt backups. Warning, keep track of this, 
if the key is lost your backups are probably lost. Do not change this, you cannot access
the backups using citobackup if the password file is incorrect.

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

    # Todo: If file is replaced/upgraded, is this needed again?
    chown root:citobackup /opt/restic/restic
    chmod 755 /opt/restic/restic
    sudo setcap cap_dac_read_search=+ep /opt/restic/restic


## backup server configuration file

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
