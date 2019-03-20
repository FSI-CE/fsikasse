#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

# python3 workaround
try:
    reload(sys)
    sys.setdefaultencoding('utf-8')
except:
    pass

from sqlite3 import dbapi2 as sqlite3
import os
import io
import re
import random
import string
from datetime import datetime, timedelta
import time
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import calendar

from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash
from werkzeug import secure_filename
from PIL import Image
app = Flask(__name__)

# regex to check for valid email adresses
EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'kasse.db'),
    UPLOAD_FOLDER = 'static/',
    ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif']),
    PROFILE_IMAGE_SIZE = (150, 200),
    ITEM_IMAGE_SIZE = (150, 300),
    STORAGE_ACCOUNT = (4, 'Lager+Kühlschrank'),
    CASH_IN_ACCOUNT = (1, 'FSI: Graue Kasse'),
    MONEY_VALUABLE_ID = 1,
    SECRET_KEY='development key',
))

def randomword(length):
   return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def init_db():
    """Initializes the database."""
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    """Creates the database tables."""
    init_db()
    print('Initialized the database.')


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def show_index():
    db = get_db()
    cur = db.execute("""
SELECT name, 
    CASE
    WHEN balance<-1000 then 'users/shame.gif'
    ELSE image_path
    END AS image_path,
balance, umsatz * 100.0 / (SELECT SUM(umsatz) FROM `index`) AS prio FROM `index`""")
    users = cur.fetchall()
    cur = db.execute('SELECT substr(datetime,0,11) as date, to_name as name FROM stats WHERE valuable_id != 1 AND to_id != 4 LIMIT 999,1')
    purchase = cur.fetchone()

    return render_template('start.html', title="Benutzerübersicht", users=users, purchase=purchase)

@app.route('/admin', methods=['GET'])
def admin_index():
    db = get_db()
    cur = db.execute("""
SELECT name, 
    CASE
    WHEN balance<-1000 then 'users/shame.gif'
    ELSE image_path
    END AS image_path,
balance, umsatz * 100.0 / (SELECT SUM(umsatz) FROM `index`) AS prio FROM `index`""")
    users = cur.fetchall()
    cur = db.execute('SELECT substr(datetime,0,11) as date, to_name as name FROM stats WHERE valuable_id != 1 AND to_id != 4 LIMIT 999,1')
    purchase = cur.fetchone()

    return render_template('start.html', title="Benutzerübersicht", admin_panel=True, users=users, purchase=purchase)

@app.route('/admin/lager', methods=['GET'])
def admin_lagerbestand():
    db = get_db()
    if request.method == 'GET':
        cur = db.execute(
            'SELECT valuable_name, balance, unit_name FROM account_valuable_balance WHERE account_id=?', [app.config['STORAGE_ACCOUNT'][0]])
        balance = cur.fetchall()
        return render_template('admin_lagerbestand.html', title="Übersicht " + app.config['STORAGE_ACCOUNT'][1], admin_panel=True, balance=balance)

    return redirect(url_for('admin_index'))

@app.route('/admin/lieferung', methods=['GET', 'POST'])
def admin_lieferung():
    db = get_db()
    cur = db.execute(
            'SELECT valuable_name, valuable_id, balance, unit_name FROM account_valuable_balance WHERE account_id=? AND unit_name!=?', [app.config['STORAGE_ACCOUNT'][0],'Cent'])
    valuable = cur.fetchall()

    if request.method == 'GET':
        return render_template('admin_lieferung.html', title="Neue Lieferung eintragen", admin_panel=True, valuable=valuable )

    if request.method == 'POST':
        for v in valuable:
            modified_value = int(request.form[v['valuable_name']])
            if modified_value is not 0:
                modified_value = modified_value + v['balance']
                # generate transaction
                cur.execute('INSERT INTO `transaction` (comment, datetime) VALUES (?, ?)', ['Einzahlung Lieferung', datetime.now()])
                transaction_id = cur.lastrowid
                cur.execute('INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) VALUES  (?, ?, ?, ?, ?)', [None, app.config['STORAGE_ACCOUNT'][0], int(v['valuable_id']), request.form[v['valuable_name']], transaction_id])
                # cur.execute('INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) VALUES  (?, ?, ?, ?, ?)', [app.config['STORAGE_ACCOUNT'][0], None, app.config['MONEY_VALUABLE_ID'], valuable['price'], transaction_id])
                # save new amount
                # cur.execute('UPDATE account_valuable_balance SET amount=? WHERE valuable_id = ?', [modified_value, int(v['valuable_id'])])
                # commit to database
                db.commit()

        flash('Neue Lieferung entgegengenommen!')
        return redirect(url_for('admin_index'))

@app.route('/admin/edit/<item_name>')
def admin_edit_item(item_name):
    db = get_db()
    cur = db.execute( 'SELECT name, active, unit_name, price, image_path, product FROM valuable WHERE name=?', [item_name])
    valuable = cur.fetchone()

    cur = db.execute( 'SELECT * FROM unit' )
    units = cur.fetchall()

    return render_template('admin_edit_item.html', title="Ware bearbeiten", admin_panel=True, item=valuable, units=units )

@app.route('/admin/edit/<item_name>/change_properties', methods=['POST'])
def edit_item_properties(item_name):
    db = get_db()
    cur = db.execute( 'SELECT name, active, unit_name, price, image_path, product FROM valuable WHERE name=?', [item_name])
    item = cur.fetchone()

    print(request.form)

    name      = request.form['name']      if request.form['name'] != ''      else item['name']
    unit_name = request.form['unit_name'] if request.form['unit_name'] != '' else item['unit_name']
    price     = request.form['price']
    active    = False if not 'active' in request.form else request.form.get('active') == 'on'
    product   = False if not 'product' in request.form else request.form.get('product') == 'on'

    filename = item['image_path']
    if 'image' in request.files and request.files['image'].filename != '':
        # Replace image
        image = request.files['image']
        assert image and allowed_file(image.filename), \
            "No image given or invalid filename/extension."
        filename = 'products/'+randomword(10)+'_'+secure_filename(image.filename)

        # Resizing image with PIL
        im = Image.open(image)

        if im.size[0] > app.config['ITEM_IMAGE_SIZE'][0] or im.size[1] > app.config['ITEM_IMAGE_SIZE'][1]:
            # cut/crop image if not 5:12 ratio
            if float(im.size[0]) / float(im.size[1]) > 5.0/12.0: # crop width
                new_width = int(im.size[0] * ( ( float(im.size[1]) * 5.0 )/ ( float(im.size[0]) * 12.0 ) ) )
                left = int(im.size[0]/2 - new_width/2)
                im = im.crop((left, 0, left + new_width, im.size[1]))
                flash(u'Image had to be cropped to 5:12 ratio, sorry!')
            elif float(im.size[0]) / float(im.size[1]) < 5.0/12.0: # crop height
                new_height = int(im.size[1] * ( ( float(im.size[0]) * 12.0 )/ ( float(im.size[1]) * 5.0 ) ) )
                top = int(im.size[1]/2 - new_height/2)
                im = im.crop((0, top, im.size[0], top + new_height))
                flash(u'Image had to be cropped to 5:12 ratio, sorry!')

            im.thumbnail(app.config['ITEM_IMAGE_SIZE'], Image.ANTIALIAS)

        im.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    cur.execute('UPDATE valuable SET name=?, active=?, unit_name=?, price=?, image_path=?, product=? WHERE name=?',
        [name, active, unit_name, price, filename, product, item['name']])
    db.commit()

    return redirect(url_for('admin_index'))

@app.route('/admin/add_item')
def admin_add_item():
    db = get_db()
    cur = db.execute( 'SELECT * FROM unit' )
    units = cur.fetchall()
    return render_template('admin_add_item.html', title="Ware hinzufügen", admin_panel=True, units=units )

@app.route('/admin/add_item/new', methods=['POST'])
def add_item():
    if request.form['name'] == '' or request.form['name'] == 'New Item':
        flash(u'Please specify a name!')
        return redirect(url_for('admin_index'))
    elif request.form['unit_name'] == '':
        flash(u'Please specify a unit_name!')
        return redirect(url_for('admin_index'))

    active    = False if not 'active' in request.form else request.form.get('active') == 'on'
    product   = False if not 'product' in request.form else request.form.get('product') == 'on'

    filename = 'products/placeholder.png'
    if 'image' in request.files and request.files['image'].filename != '':
        # Replace image
        image = request.files['image']
        assert image and allowed_file(image.filename), \
            "No image given or invalid filename/extension."
        filename = 'products/'+randomword(10)+'_'+secure_filename(image.filename)

        # Resizing image with PIL
        im = Image.open(image)

        if im.size[0] > app.config['ITEM_IMAGE_SIZE'][0] or im.size[1] > app.config['ITEM_IMAGE_SIZE'][1]:
            # cut/crop image if not 5:12 ratio
            if float(im.size[0]) / float(im.size[1]) > 5.0/12.0: # crop width
                new_width = int(im.size[0] * ( ( float(im.size[1]) * 5.0 )/ ( float(im.size[0]) * 12.0 ) ) )
                left = int(im.size[0]/2 - new_width/2)
                im = im.crop((left, 0, left + new_width, im.size[1]))
                flash(u'Image had to be cropped to 5:12 ratio, sorry!')
            elif float(im.size[0]) / float(im.size[1]) < 5.0/12.0: # crop height
                new_height = int(im.size[1] * ( ( float(im.size[0]) * 12.0 )/ ( float(im.size[1]) * 5.0 ) ) )
                top = int(im.size[1]/2 - new_height/2)
                im = im.crop((0, top, im.size[0], top + new_height))
                flash(u'Image had to be cropped to 5:12 ratio, sorry!')

            im.thumbnail(app.config['ITEM_IMAGE_SIZE'], Image.ANTIALIAS)

        im.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    db = get_db()
    db.execute('INSERT INTO valuable (name, active, unit_name, price, image_path, product) VALUES  (?, ?, ?, ?, ?, ?)',
        [request.form['name'], active, request.form['unit_name'], request.form['price'], filename, product])
    db.commit()

    return redirect(url_for('admin_index'))

@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    db = get_db()
    if request.method == 'GET':
        cur = db.execute(
            'SELECT * FROM stats WHERE from_id = ? OR to_id = ? LIMIT 100',
            [app.config['STORAGE_ACCOUNT'][0], app.config['STORAGE_ACCOUNT'][0]])
        transactions = cur.fetchall()
        return render_template('admin_statistiken.html', title="Statistiken" + app.config['STORAGE_ACCOUNT'][1], transactions=transactions, admin_panel=True )

@app.route('/user/<username>')
def show_userpage(username):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'SELECT name, image_path, account_id, direct_payment FROM user WHERE active=1 and name=?',
        [username])
    user = cur.fetchone()
    if not user:
        abort(404)
    cur = db.execute('SELECT name, image_path FROM user WHERE active=1 AND direct_payment=0 AND browsable=1 AND name!=? ORDER BY name', [username])
    user_list = cur.fetchall()
    cur = db.execute(
        'SELECT balance FROM account_valuable_balance WHERE account_id=? and valuable_id=?',
        [user['account_id'], app.config['MONEY_VALUABLE_ID']])
    user_balance = cur.fetchone()
    cur = cur.execute('SELECT valuable.name AS name, valuable.active, price+tax AS price, unit_name, symbol, valuable.image_path FROM valuable, unit, user WHERE unit.name = valuable.unit_name AND product = 1 AND user.name=?', [username])
    products = cur.fetchall()
    return render_template(
        'show_userpage.html', title="Getränkeliste", user=user, products=products, balance=user_balance,
        user_list=user_list, return_to_index=True )

@app.route('/user/<username>/buy/<valuablename>')
def action_buy(username, valuablename):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'SELECT name, account_id, direct_payment FROM user WHERE active=1 and name=?',
        [username])
    user = cur.fetchone()
    if not user:
        abort(404)
        
    cur.execute('SELECT valuable.valuable_id, price+tax AS price FROM valuable, user WHERE product=1 and valuable.name=? and user.name=?', [valuablename, username])
    valuable = cur.fetchone()
    cur.execute('INSERT INTO `transaction` (datetime) VALUES (?)', [datetime.now()])
    transaction_id = cur.lastrowid
    cur.execute('INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) VALUES  (?, ?, ?, ?, ?)', [app.config['STORAGE_ACCOUNT'][0], user['account_id'], valuable['valuable_id'], 1, transaction_id])
    if not user['direct_payment']:
        cur.execute('INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) VALUES  (?, ?, ?, ?, ?)', [user['account_id'], None, app.config['MONEY_VALUABLE_ID'], valuable['price'], transaction_id])
    else:
        cur.execute('INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) VALUES  (?, ?, ?, ?, ?)', [None, app.config['CASH_IN_ACCOUNT'][0], app.config['MONEY_VALUABLE_ID'], valuable['price'], transaction_id])
    db.commit()

    if user['direct_payment']:
        flash('Bitte {:.2f} € in die graue Kasse legen.'.format(valuable['price']/100.0))
    else:
        flash('Einkauf war erfolgreich :)')
    return redirect(url_for('show_index'))

@app.route('/user/<username>/transfer', methods=['POST'])
def transfer_money(username):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'SELECT name, account_id FROM user WHERE active=1 and direct_payment=0 and name=?',
        [username])
    user = cur.fetchone()
    cur.execute(
        'SELECT name, account_id FROM user WHERE active=1 and direct_payment=0 and name=?',
        [request.form['to']])
    to_user = cur.fetchone()
    if not user or not to_user:
        abort(404)

    amount = int(float(request.form['amount'])*100 + 0.5)

    if amount <= 0.0:
        flash(u'Keine Transaktion durchgeführt.')
        return redirect(url_for('show_index'))

    cur.execute('INSERT INTO `transaction` (datetime, comment) VALUES (?, ?)', [datetime.now(), 'Überweisung von %.2f€' % (float(amount)/100)])
    transaction_id = cur.lastrowid
    cur.execute('INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) VALUES  (?, ?, ?, ?, ?)',
        [user['account_id'], to_user['account_id'], app.config['MONEY_VALUABLE_ID'], amount, transaction_id])
    db.commit()

    flash('Geld wurde überwiesen.')
    return redirect(url_for('show_index'))

@app.route('/user/<username>/collect', methods=['POST', 'GET'])
def collect_money(username):
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT name, account_id, image_path FROM user WHERE active=1 and direct_payment=0 and name=?', [username])
    user = cur.fetchone()
    if not user:
        abort(404)

    if request.method == 'GET':
        cur.execute('SELECT name FROM user WHERE browsable=1 and active=1 and direct_payment=0 and name!=? ORDER BY name', [username])
        users = cur.fetchall()
        return render_template('user_collect.html', title="Einsammeln " + user['name'], user=user, users=users, return_to_userpage=True)
    
    else:  # request.method == 'POST':
        to_users = request.form.getlist('user_select')
        if len(to_users) == 0:
            flash(u'You need to specify some people.')
            return redirect(url_for('show_index'))
        amount = int(float(request.form['amount'])*100 / len(to_users) + 0.5)
        if amount <= 0.0:
            flash(u'Keine Transaktion durchgeführt.')
            return redirect(url_for('show_index'))

        # check all account_id
        sql='SELECT account_id FROM user WHERE active=1 and direct_payment=0 and name IN (%s)' 
        in_p = ', '.join(['?']*len(to_users))
        sql = sql % in_p
        cur.execute(sql, to_users)
        user_ids = cur.fetchall()
        if len(user_ids) != len(to_users):
            abort(403)
        
        cur.execute('INSERT INTO `transaction` (comment, datetime) VALUES (?, ?)', ["Einsammeln von " + request.form['comment'], datetime.now()])
        transaction_id = cur.lastrowid
        for to_user in user_ids:
            if to_user != user['account_id']:
                cur.execute('INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) VALUES  (?, ?, ?, ?, ?)', [to_user['account_id'], user['account_id'], app.config['MONEY_VALUABLE_ID'], amount, transaction_id])
        db.commit()

        flash('Geld wurde eingesammelt.')
        return redirect(url_for('show_index'))

@app.route('/user/<username>/profile', methods=['POST', 'GET'])
def edit_userprofile(username):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        'SELECT name, image_path, account_id, mail, allow_edit_profile FROM user WHERE active=1 AND name=?',
        [username])
    user = cur.fetchone()
    if not user:
        abort(404)

    if request.method == 'GET':
        cur = db.execute(
            'SELECT valuable_name, balance, unit_name FROM account_valuable_balance WHERE account_id=?',
            [user['account_id']])
        balance = cur.fetchall()
        cur = db.execute(
            'SELECT * FROM stats WHERE from_id = ? OR to_id = ? LIMIT 25',
            [user['account_id'], user['account_id']])
        transactions = cur.fetchall()
        return render_template('user_profile.html', title="Benutzerprofil " + user['name'], user=user, transactions=transactions, balance=balance, return_to_userpage=True)
    else:  # request.method == 'POST':
        if not user['allow_edit_profile']:
            abort(403)

        if request.form['mail'] == '' or not EMAIL_REGEX.match(request.form['mail']):
            flash(u'Bitte eine korrekte Kontaktadresse angeben, danke!')
            return redirect(url_for('edit_userprofile', username=user['name']))

        filename = user['image_path']
        if 'image' in request.files and request.files['image'].filename != '':
            # Replace image
            image = request.files['image']
            assert image and allowed_file(image.filename), \
                "No image given or invalid filename/extension."
            filename = 'users/'+randomword(10)+'_'+secure_filename(image.filename)

            # Resizing image with PIL
            im = Image.open(image)

            # cut/crop image if not 3:4 ratio
            if float(im.size[0]) / float(im.size[1]) > 3.0/4.0: # crop width
                new_width = int(im.size[0] * ( ( float(im.size[1]) * 3.0 )/ ( float(im.size[0]) * 4.0 ) ) )
                left = int(im.size[0]/2 - new_width/2)
                im = im.crop((left, 0, left + new_width, im.size[1]))
                flash(u'Image had to be cropped to 3:4 ratio, sorry!')
            elif float(im.size[0]) / float(im.size[1]) < 3.0/4.0: # crop height
                new_height = int(im.size[1] * ( ( float(im.size[0]) * 4.0 )/ ( float(im.size[1]) * 3.0 ) ) )
                top = int(im.size[1]/2 - new_height/2)
                im = im.crop((0, top, im.size[0], top + new_height))
                flash(u'Image had to be cropped to 3:4 ratio, sorry!')

            im.thumbnail(app.config['PROFILE_IMAGE_SIZE'], Image.ANTIALIAS)
            im.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cur.execute('UPDATE user SET name=?, mail=?, image_path=? WHERE name=?',
                   [request.form['name'], request.form['mail'], filename, username])
        db.commit()

        if 'image' in request.files and user['image_path']:
            # Remove old profile image
            os.unlink(os.path.join(app.config['UPLOAD_FOLDER'], user['image_path']))

        flash(u'Benutzerprofil erfolgreich aktualisiert!')
        return redirect(url_for('edit_userprofile', username=request.form['name']))

@app.route('/user/active', methods=['POST', 'GET'])
def activate_user():
    if request.method == 'GET':
        db = get_db()
        db = db.execute( 'SELECT name, active, browsable FROM user WHERE browsable=1 ORDER BY name ASC' )
        users = db.fetchall()
        return render_template('activate_user.html', title="Benutzer (de)aktivieren", users=users, admin_panel=True)
    else:  # request.method == 'POST'
        db = get_db()
        cur = db.cursor()
        cur.execute( 'UPDATE user SET active = CASE WHEN active > 0 THEN 0 ELSE 1 END WHERE name=?', [request.form['toggle_user']] )
        db.commit()
        return redirect(url_for('admin_index'))

@app.route('/user/add', methods=['POST', 'GET'])
def add_user():
    if request.method == 'GET':
        return render_template('add_user.html', title="Benutzer hinzufügen", admin_panel=True)
    else:  # request.method == 'POST'
        db = get_db()
        cur = db.cursor()

        if request.form['name'] == '':
            flash(u'Bitte einen Namen angeben, danke!')
            return redirect(url_for('show_index'))

        if request.form['mail'] == '' or not EMAIL_REGEX.match(request.form['mail']):
            flash(u'Bitte eine Kontaktadresse angeben, danke!')
            return redirect(url_for('show_index'))

        image = request.files['image'] if 'image' in request.files else None
        if image and allowed_file(image.filename):
            filename = 'users/'+randomword(10)+'_'+secure_filename(image.filename)

            # Resizing/saving image with PIL
            im = Image.open(image)

            # cut/crop image if not 3:4 ratio
            if float(im.size[0]) / float(im.size[1]) > 3.0/4.0: # crop width
                new_width = int(im.size[0] * ( ( float(im.size[1]) * 3.0 )/ ( float(im.size[0]) * 4.0 ) ) )
                left = int(im.size[0]/2 - new_width/2)
                im = im.crop((left, 0, left + new_width, im.size[1]))
                flash(u'Image had to be cropped to 3:4 ratio, sorry!')
            elif float(im.size[0]) / float(im.size[1]) < 3.0/4.0: # crop height
                new_height = int(im.size[1] * ( ( float(im.size[0]) * 4.0 )/ ( float(im.size[1]) * 3.0 ) ) )
                top = int(im.size[1]/2 - new_height/2)
                im = im.crop((0, top, im.size[0], top + new_height))
                flash(u'Image had to be cropped to 3:4 ratio, sorry!')


            im.thumbnail(app.config['PROFILE_IMAGE_SIZE'], Image.ANTIALIAS)
            im.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = None

        cur.execute('INSERT INTO user (name, mail, image_path) VALUES (?, ?, ?)',
                   [request.form['name'], request.form['mail'], filename])
        db.commit()
        return redirect(url_for('edit_userprofile', username=request.form['name']))

@app.route('/user/<username>/add', methods=['POST'])
def add_to_account(username):
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT account_id FROM user WHERE active=1 AND name=? AND direct_payment=0',
        [username])
    user = cur.fetchone()

    if not user:
        abort(404)

    amount = int(float(request.form['amount'])*100 + 0.5)

    if amount <= 0.0:
        flash(u'Keine Transaktion durchgeführt.')
        return redirect(url_for('show_index'))

    cur.execute('INSERT INTO `transaction` (datetime, comment) VALUES (?, ?)', [datetime.now(), 'Einzahlung von %.2f€' % (float(amount)/100)])
    transaction_id = cur.lastrowid
    cur.execute(
        'INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) ' +
            'VALUES  (?, ?, ?, ?, ?)',
        [None, user['account_id'], app.config['MONEY_VALUABLE_ID'], amount, transaction_id])
    cur.execute(
        'INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) ' +
            'VALUES  (?, ?, ?, ?, ?)',
        [None, app.config['CASH_IN_ACCOUNT'][0], app.config['MONEY_VALUABLE_ID'], amount, transaction_id])
    db.commit()
    flash(u'Danke für das Geld :)')

    return redirect(url_for('show_index'))

@app.route('/user/<username>/sub', methods=['POST'])
def sub_from_account(username):
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT account_id FROM user WHERE active=1 AND name=? AND direct_payment=0',
        [username])
    user = cur.fetchone()

    if not user:
        abort(404)

    amount = int(float(request.form['amount'])*100 + 0.5)

    if amount <= 0.0:
        flash(u'Keine Transaktion durchgeführt.')
        return redirect(url_for('show_index'))

    cur.execute('INSERT INTO `transaction` (datetime, comment) VALUES (?, ?)', [datetime.now(), 'Auszahlung von %.2f€' % (float(amount)/100)])
    transaction_id = cur.lastrowid
    cur.execute(
        'INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) ' +
            'VALUES  (?, ?, ?, ?, ?)',
        [user['account_id'], None, app.config['MONEY_VALUABLE_ID'], amount, transaction_id])
    cur.execute(
        'INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) ' +
            'VALUES  (?, ?, ?, ?, ?)',
        [app.config['CASH_IN_ACCOUNT'][0], None, app.config['MONEY_VALUABLE_ID'], amount, transaction_id])
    db.commit()
    flash(u'Geld wurde abgezogen.')

    return redirect(url_for('show_index'))

@app.route('/user/<username>/cancel/<int:transaction_id>')
def cancle_transaction(username, transaction_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT account_id FROM user WHERE active=1 AND name=?',
        [username])
    user = cur.fetchone()

    if not user:
        abort(404)

    # hide canceled transaction
    cur.execute('SELECT * FROM `transaction` WHERE transaction_id = ? AND visible = 1', [transaction_id])
    transaction = cur.fetchone()
    
    if not transaction:
        abort(403)

    cur.execute(
        'SELECT from_id, to_id, valuable_id, amount FROM transfer WHERE transaction_id = ?',
        [transaction_id])
    transfers = cur.fetchall()

    cur.execute('INSERT INTO `transaction` (datetime, comment) VALUES (?, ?)',
        [datetime.now(), 'Storno von '+str(transaction_id)+' durch '+username])
    cancle_transaction_id = cur.lastrowid
    for t in transfers:
        cur.execute(
            'INSERT INTO transfer (from_id, to_id, valuable_id, amount, transaction_id) ' +
                'VALUES  (?, ?, ?, ?, ?)',
            [t['to_id'], t['from_id'], t['valuable_id'], t['amount'], cancle_transaction_id])
    cur.execute('UPDATE `transaction` SET visible = 0 WHERE transaction_id = ?', [transaction_id])
    db.commit()

    flash('Buchung wurde storniert.')
    return redirect(url_for('edit_userprofile', username=username))

def graphs_helper():
    t1 = time.time()
    db = get_db()
    df = pd.read_sql_query("""
SELECT dt as date, count(dt) as amount
FROM (SELECT substr(datetime,0,11) as dt FROM `transaction` INNER JOIN transfer ON `transaction`.transaction_id = transfer.transaction_id WHERE valuable_id!=1 AND to_id!=4)
GROUP BY dt
ORDER BY dt DESC
LIMIT 365
    """, db)

    df['date'] = df['date'].astype('datetime64[D]')
    df = df.resample('D', on='date').sum().reset_index()
    df.plot(x='date', y='amount', figsize=[12.8, 4.8], label='', legend=False, title='Purchases per day (last 365 days)')
    plt.gca().xaxis.label.set_visible(False)
    imgdata = io.StringIO()
    plt.savefig(imgdata, format='svg', bbox_inches='tight')
    yield imgdata.getvalue()
    imgdata.close()
    plt.close()

    df = df.groupby(df['date'].apply(lambda x: x.dayofweek)).sum().reset_index()
    df['date'] = df['date'].apply(lambda x: calendar.day_abbr[x])
    df['amount'] = df['amount'].apply(lambda x: x/df['amount'].sum())
    df.set_index('date').plot.bar(rot=0, label='', legend=False, title='Purchases per week day (last 365 days)')
    plt.gca().xaxis.label.set_visible(False)
    # manipulate
    ax = plt.gca()
    vals = ax.get_yticks()
    ax.set_yticklabels(['{:,.2%}'.format(x) for x in vals])
    imgdata = io.StringIO()
    plt.savefig(imgdata, format='svg', bbox_inches='tight')
    yield imgdata.getvalue()
    imgdata.close()
    plt.close()

    df = pd.read_sql_query("""
SELECT dt as date, count(dt) as amount
FROM (SELECT substr(datetime,12,8) as dt FROM `transaction` INNER JOIN transfer ON `transaction`.transaction_id = transfer.transaction_id WHERE valuable_id!=1 AND to_id!=4)
GROUP BY dt
ORDER BY dt ASC
    """, db)
    df['date'] = df['date'].astype('datetime64')
    df = df.resample('30T', on='date').sum().reset_index()
    df['amount'] = df['amount'].apply(lambda x: x/df['amount'].sum())
    df.plot(x='date', y='amount', label='', legend=False, title='Purchases per hour')
    # manipulate
    ax = plt.gca()
    vals = ax.get_yticks()
    ax.set_yticklabels(['{:,.2%}'.format(x) for x in vals])
    # ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))
    imgdata = io.StringIO()
    plt.savefig(imgdata, format='svg', bbox_inches='tight')
    yield imgdata.getvalue()
    imgdata.close()
    plt.close()

    yield '<p>Plotting took %.2f seconds.</p>' % (time.time()-t1)

from flask import stream_with_context, request, Response

@app.route('/graphs')
def graphs():
    def stream_template(template_name, **context):
        app.update_template_context(context) 
        t = app.jinja_env.get_template(template_name)
        rv = t.stream(context) 
        return rv
    svgs=graphs_helper()
    db = get_db()
    cur = db.execute('select count(*) as amount, valuable_name as name from stats where datetime>? and valuable_id!=? group by valuable_id order by valuable_id', [datetime.today() - timedelta(days=14),app.config['MONEY_VALUABLE_ID']])
    purchases= cur.fetchall()
    return Response(stream_with_context(stream_template('graphs.html', svgs=svgs, purchases=purchases, title='Some graphs', return_to_index=True)))

if __name__ == '__main__':
    app.debug = True
    app.run()
