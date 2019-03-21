#!/bin/bash -l

BACKUP_DIR="../fsikasse-backups"
REMOTE_DIR="server:fsikasse-backups"

BACKUP_FILE="backup_$(date +%F_%H-%M).db"

# install script
if [ $1 = "install" ]; then
	# install cronjob for automatic backups
	(crontab -l ; \
	echo "0 1 * * * ${PWD}/backup.sh &> /dev/null" ; \
	) | crontab -

	# create backup directory
	mkdir -p ${BACKUP_DIR}
	exit
fi

# remove script
if [ $1 = "remove" ]; then
	# remove cronjob
	crontab -l | grep -v "${PWD}/backup.sh" | crontab -

	exit
fi

# create backup of the database
sqlite3 kasse.db ".backup ${BACKUP_DIR}/${BACKUP_FILE}"
# create backup of static/
tar czf ${BACKUP_DIR}/static.tar.gz static/
# delete backups older than 7 days
find ${BACKUP_DIR} -type f -mtime +7 -name '*.db' -delete

# remote sync
rsync -a --delete ${BACKUP_DIR}/ ${REMOTE_DIR}
