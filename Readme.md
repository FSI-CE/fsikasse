# FSI-Kasse

## Description

A neat little web application that manages the sale and stock of drinks and sweets. It is designed to run on a single machine, all users are expected to be trusted and "well behaved". It was meant to have (at least) the same feature set as the paper tally sheet, which it replaced.

## Installation

Install dependencies:

    $ pip install -U Flask Pillow Pandas Matplotlib

[Download](https://github.com/FSI-CE/fsikasse/archive/master.zip) and extract fsikasse or clone the git repository.

    $ git clone https://github.com/FSI-CE/fsikasse.git
    $ cd fsikasse

Setup fsikasse:

    $ FLASK_APP=fsikasse.py flask initdb

From now on it is sufficient to start fsikasse with:

    $ FLASK_APP=fsikasse.py flask run

## Backup (optional)

The FSI-Kasse comes with a neat little backup script. It requires rsync and sqlite3 to be installed.
First a local backup of the database and the static/ directory is created. Afterwards the backup directory is synchronized with rsync.

The backup directories should be configured to your own preferences.

It is installed by running

    $ ./backup.sh install

## Update (experimental)

If you have cloned the repository, you can run the following commands to update the fsikasse:

    $ pip install -U Flask
    $ pip install -U Pillow
    $ git pull

Don't forget the restart flask.
