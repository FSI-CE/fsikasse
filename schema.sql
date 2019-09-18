BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS `unit` (
    `name`      TEXT PRIMARY KEY,
    `symbol`    TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS `transfer` (
    `from_id`        INTEGER,
    `to_id`          INTEGER,
    `valuable_id`    INTEGER NOT NULL,
    `amount`         INTEGER NOT NULL,
    `transaction_id` INTEGER NOT NULL,
    FOREIGN KEY(`transaction_id`) REFERENCES `transaction`(`transaction_id`),
    FOREIGN KEY(`from_id`) REFERENCES `user`(`account_id`),
    FOREIGN KEY(`to_id`) REFERENCES `user`(`account_id`),
    FOREIGN KEY(`valuable_id`) REFERENCES `valuable`(`valuable_id`)
);
CREATE TABLE IF NOT EXISTS `transaction` (
    `transaction_id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `visible`   BOOLEAN NOT NULL DEFAULT 1,
    `comment`   TEXT,
    `datetime`  TEXT
);
CREATE TABLE IF NOT EXISTS `valuable` (
    `valuable_id`   INTEGER PRIMARY KEY AUTOINCREMENT,
    `name`          TEXT NOT NULL UNIQUE,
    `active`        INTEGER NOT NULL DEFAULT 1,
    `unit_name`     INTEGER NOT NULL,
    `price`         INTEGER NOT NULL,
    `image_path`    TEXT,
    `product`       INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(`unit_name`) REFERENCES `unit`(`name`)
);
CREATE TABLE IF NOT EXISTS `user` (
    `name`               TEXT NOT NULL UNIQUE,
    `account_id`         INTEGER PRIMARY KEY AUTOINCREMENT,
    `mail`               TEXT,
    `image_path`         TEXT,
    `browsable`          INTEGER NOT NULL DEFAULT 1,
    `direct_payment`     INTEGER NOT NULL DEFAULT 0,
    `allow_edit_profile` INTEGER NOT NULL DEFAULT 1,
    `active`             INTEGER NOT NULL DEFAULT 1,
    `tax`                INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS `balance` (
    `account_id`     INT NOT NULL,
    `valuable_id`    INT NOT NULL,
    `balance`        INT NOT NULL DEFAULT 0,
    UNIQUE(account_id, valuable_id)
);

CREATE VIEW IF NOT EXISTS `account_valuable_balance` AS
    SELECT
        user.name AS account_name,
        balance.account_id AS account_id,
        valuable.name AS valuable_name,
        balance.valuable_id,
        balance,
        valuable.unit_name AS unit_name
    FROM balance
	INNER JOIN user ON user.account_id=balance.account_id
	INNER JOIN valuable ON valuable.valuable_id=balance.valuable_id
    ORDER BY account_id;

-- detailed transfer history, canceled transactions are hidden
CREATE VIEW IF NOT EXISTS `stats` AS
    SELECT 
        `transaction`.transaction_id,
        comment,
        datetime,
        account_from.name AS from_name,
        from_id,
        account_to.name AS to_name,
        to_id,
        amount,
        valuable.unit_name,
        valuable.name AS valuable_name,
        valuable.valuable_id
    FROM `transaction`
    JOIN transfer ON `transaction`.transaction_id = transfer.transaction_id
    JOIN `valuable` ON transfer.valuable_id = valuable.valuable_id
    LEFT JOIN user AS account_from ON from_id = account_from.account_id
    LEFT JOIN user AS account_to ON to_id = account_to.account_id
    WHERE visible = 1
    ORDER BY strftime("%s", datetime) DESC;

-- view for front page
CREATE VIEW IF NOT EXISTS `index` AS
    SELECT user.name AS name, image_path, balance, umsatz
    FROM user
    INNER JOIN account_valuable_balance AS avb ON user.account_id = avb.account_id
    LEFT JOIN (
        -- calculate turnover
        SELECT to_id, SUM(price) AS umsatz 
        FROM (
            -- select last 1000 transactions which aren't canceled
            SELECT to_id, price 
            FROM `transfer` 
            INNER JOIN valuable ON transfer.valuable_id=valuable.valuable_id
            INNER JOIN `transaction` ON `transaction`.transaction_id = transfer.transaction_id
            WHERE transfer.valuable_id != 1 AND to_id != 4 AND visible = 1
            ORDER BY transfer.transaction_id DESC 
            LIMIT 1000
        ) GROUP BY to_id
        ) ON ( to_id = avb.account_id )
    WHERE active=1 AND browsable=1 AND valuable_id = 1
    ORDER BY umsatz DESC, name ASC;

INSERT INTO `user` (`name`, `browsable`, `direct_payment`, `allow_edit_profile`)
    VALUES ('FSI: Graue Kasse', 0, 0, 0);
INSERT INTO `user` (`name`, `browsable`, `direct_payment`, `allow_edit_profile`)
    VALUES ('FSI: Blaue Kasse', 0, 0, 0);
INSERT INTO `user` (`name`, `browsable`, `direct_payment`, `allow_edit_profile`)
    VALUES ('FSI: Bankkonto', 0, 0, 0);
INSERT INTO `user` (`name`, `browsable`, `direct_payment`, `allow_edit_profile`)
    VALUES ('FSI: Lager+Kühlschrank', 0, 0, 0);
INSERT INTO `user` (`name`, `browsable`, `direct_payment`, `allow_edit_profile`, `tax`)
    VALUES ("Gäste", 0, 1, 0, 10);
INSERT INTO `user` (`name`, `browsable`, `direct_payment`, `allow_edit_profile`, `tax`)
    VALUES ("Materialsammlung", 0, 1, 0, 10);

INSERT INTO `unit` (`name`, `symbol`) VALUES ('Cent', '¢');
INSERT INTO `unit` (`name`, `symbol`) VALUES ('Flasche', 'Fl.');
INSERT INTO `unit` (`name`, `symbol`) VALUES ('Stück', 'Stk.');

INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`, `product`)
    VALUES ('Euro', 1, 'Cent', 1, NULL, 0);
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('Club-Mate', 1, 'Flasche', 60, 'products/Loscher-Club-Mate.png');
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('ICE-T', 1, 'Flasche', 60, 'products/Loscher-ICE-T.png');
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('Wintermate', 1, 'Flasche', 60, 'products/Loscher-Winter-Mate.png');
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('Lapacho', 1, 'Flasche', 60, 'products/Loscher-Lapacho.png');
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('Mate-Cola', 1, 'Flasche', 60, 'products/Loscher-Mate-Cola.png');
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('Apfelschorle', 1, 'Flasche', 60, 'products/Loscher-Apfelschorle.png');
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('Apfelsaft', 1, 'Flasche', 60, 'products/Loscher-Apfelsaft.png');
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('Bier', 1, 'Flasche', 90, 'products/Bier.png');
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('Orangensaft', 1, 'Flasche', 60, 'products/Loscher-Orangensaft.png');
INSERT INTO `valuable` (`name`, `active`, `unit_name`, `price`, `image_path`)
    VALUES ('Wasser', 1, 'Flasche', 30, 'products/Loscher-Tafelwasser.png');
COMMIT;

