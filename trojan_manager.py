#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Name: Trojan Manager
Dev: K4YT3X
Date Created: July 8, 2018
Last Modified: March 5, 2019

Licensed under the GNU General Public License Version 3 (GNU GPL v3),
    available at: https://www.gnu.org/licenses/gpl-3.0.txt
Copyright (C) 2018-2019, K4YT3X <k4yt3x@k4yt3x.com>
"""

from avalon_framework import Avalon
from prettytable import PrettyTable
import hashlib
import MySQLdb
import readline
import sys
import traceback

VERSION = '1.3.8'
COMMANDS = [
    "CreateUserTable",
    "TruncateUserTable",
    "Verify",
    "AddUser",
    "DelUser",
    "Show",
    "SetQuota",
    "AddQuota",
    "ClearUsage",
    "Exit",
    "Quit",
]


def show_affection(function):
    """ Shows cursor execution affected rows
    """
    def wrapper(*args, **kwargs):
        function(*args, **kwargs)
        Avalon.debug_info('{} row(s) affected'.format(args[0].cursor.rowcount))
    return wrapper


def catch_mysql_errors(function):
    """ Catch mysqldb warnings and errors
    """
    def wrapper(*args, **kwargs):
        try:
            function(*args, **kwargs)
        except (MySQLdb.Error, MySQLdb.Warning) as e:
            Avalon.error(e)
            return 1
    return wrapper


class ShellCompleter(object):
    """ Completer for readline

    This class tries to match input text
    to a list of available commands.
    """

    def __init__(self, options):
        self.options = sorted(options)

    def complete(self, text, state):
        if state == 0:
            if text:
                self.matches = [s for s in self.options if s and s.lower().startswith(text.lower())]
            else:
                self.matches = self.options[:]
        try:
            return self.matches[state]
        except IndexError:
            return None


class TrojanDatabase:
    """ Trojan Database Connector

    This class generates objects that
    connects to and controls the trojan
    database.
    """

    def __init__(self, db_host, db_user, db_pass, db, table):
        """ Initialize database connection
        """
        self.db_host = db_host
        self.db_user = db_user
        self.db_pass = db_pass
        self.db = db
        self.table = table
        self.connection = MySQLdb.connect(self.db_host, self.db_user, self.db_pass, self.db)
        self.cursor = self.connection.cursor()

    @show_affection
    @catch_mysql_errors
    def create_user_table(self):
        """ Create new user table
        """
        sql = ["CREATE TABLE {} (".format(self.table),
               "id INT UNSIGNED NOT NULL AUTO_INCREMENT,",
               "username VARCHAR(64) NOT NULL,",
               "password CHAR(56) NOT NULL,",
               "quota BIGINT NOT NULL DEFAULT 0,",
               "download BIGINT UNSIGNED NOT NULL DEFAULT 0,",
               "upload BIGINT UNSIGNED NOT NULL DEFAULT 0,",
               "PRIMARY KEY (id),",
               "INDEX (password)",
               ");",
               ]
        self.cursor.execute(''.join(sql))
        self.connection.commit()
        return 0

    @show_affection
    @catch_mysql_errors
    def truncate_user_table(self):
        """ truncate the user table
        """
        self.cursor.execute('TRUNCATE {};'.format(self.table))
        self.connection.commit()
        return 0

    @show_affection
    @catch_mysql_errors
    def drop_user_table(self):
        """ Boom
        """
        self.cursor.execute('DROP TABLE {};'.format(self.table))
        self.connection.commit()
        return 0

    @show_affection
    @catch_mysql_errors
    def add_user(self, username, password):
        """ Add new user into database
        """
        self.cursor.execute("SELECT * FROM {} WHERE username = '{}'".format(self.table, username))
        if self.cursor.fetchone() is not None:
            Avalon.error('User {} already exists'.format(username))
            self.cursor.rowcount = 0  # No actual changes to database
            return 1
        fullhash = hashlib.sha224('{}:{}'.format(username, password).encode('utf-8')).hexdigest()
        self.cursor.execute("INSERT INTO {} (username, password) VALUES ('{}', '{}')".format(self.table, username, fullhash))
        # self.cursor.execute("INSERT INTO {} SHA2(CONCAT(username, ':', password)', 224) VALUES ('{}', '{}')".format(self.table, username, password))
        self.connection.commit()
        return 0

    @show_affection
    @catch_mysql_errors
    def del_user(self, username):
        """ Delete a user from the database
        """
        self.cursor.execute("DELETE FROM {} WHERE username = '{}'".format(self.table, username))
        self.connection.commit()
        return 0

    @catch_mysql_errors
    def user_exists(self, username):
        """ Determines if a user exists in the database
        """
        self.cursor.execute("SELECT * FROM {} WHERE username = '{}'".format(self.table, username))
        user_id = self.cursor.fetchone()
        if user_id is not None:
            return True
        return False

    @catch_mysql_errors
    def show_users(self, show_quota=False):
        """ List users
        If show_quota is True, include quota and data usage
        """
        total_users = self.cursor.execute("SELECT * FROM {}".format(self.table))
        columns = ['ID', 'Username', 'Password']
        if show_quota:
            columns += ['Quota', 'Download', 'Upload']
        table = PrettyTable(columns)
        for user in self.cursor.fetchall():
            if show_quota:
                table.add_row(user)
            else:
                table.add_row([user[0], user[1], user[2]])
        print(table)
        Avalon.info('Query complete, {} user(s) found in database'.format(total_users))
        return 0

    def convert_units(self, data):
        """ Convert data unit into bytes
        """
        try:
            try:
                return int(data)
            except ValueError:
                if data[-1].lower() == 'k':
                    return int(data[:-1]) * 1024
                elif data[-1].lower() == 'm':
                    return int(data[:-1]) * 1024 ** 2
                elif data[-1].lower() == 'g':
                    return int(data[:-1]) * 1024 ** 3
                elif data[-1].lower() == 't':
                    return int(data[:-1]) * 1024 ** 4
                elif data[-1].lower() == 'p':
                    return int(data[:-1]) * 1024 ** 5
                else:
                    return False
        except ValueError:
            return False

    @show_affection
    @catch_mysql_errors
    def set_quota(self, username, quota):
        """ Set user quota to a specific value
        """
        converted = self.convert_units(quota)
        if not converted:
            Avalon.error('Invalid quota input')
            return 1
        self.cursor.execute("UPDATE {} SET quota = {} WHERE username = '{}'".format(self.table, converted, username))
        self.connection.commit()
        return 0

    @show_affection
    @catch_mysql_errors
    def add_quota(self, username, appended_quota):
        """ Append quota
        """
        converted = self.convert_units(appended_quota)
        if not converted:
            Avalon.error('Invalid quota input')
            return 1
        self.cursor.execute("UPDATE {} SET quota = quota + {} WHERE username = '{}'".format(self.table, converted, username))
        self.connection.commit()
        return 0

    @show_affection
    @catch_mysql_errors
    def clear_usage(self, username=None):
        if username is None:
            """ Clear all users data usage
            """
            self.cursor.execute("UPDATE {} SET download = 0, upload = 0".format(self.table))
            self.connection.commit()
        else:
            """ Clear user data usage
            """
            self.cursor.execute("UPDATE {} SET download = 0, upload = 0 WHERE username = '{}'".format(self.table, username))
            self.connection.commit()
        return 0

    @catch_mysql_errors
    def verify(self, fullhash):
        """ Verify if user credentials are valid
        """
        valid_hashes = []
        self.cursor.execute("SELECT * FROM {}".format(self.table))
        all_users = self.cursor.fetchall()
        for user in all_users:
            valid_hashes.append(user[2])
        if fullhash in valid_hashes:
            Avalon.info('Valid user')
            return 0
        Avalon.warning('Invalid user')
        return 1


def print_legal_info():
    print('Trojan Manager {}'.format(VERSION))
    print('(C) 2018 K4YT3X')
    print('Licensed under GNU GPL v3')


def print_help():
    help_lines = [
        "\n{}Commands are not case-sensitive{}".format(Avalon.FM.BD, Avalon.FM.RST),
        "CreateUserTable",
        "TruncateUserTable",
        "Verify [hash]",
        "AddUser [username] [password]",
        "DelUser [username]",
        "Show (users / quota)",
        "SetQuota [quota]",
        "AddQuota [quota]",
        "ClearUsage [username]",
        "Interactive / int"
        "Exit / Quit",
        "",
    ]
    for line in help_lines:
        print(line)


def command_interpreter(db_connection, commands):
    """ Trojan shell command interpreter
    """
    try:
        # Try to guess what the user is saying
        possibilities = [s for s in COMMANDS if s.lower().startswith(commands[1])]
        if len(possibilities) == 1:
            commands[1] = possibilities[0]

        if commands[1].replace(' ', '') == '':
            result = 0
        elif commands[1].lower() == 'help':
            print_help()
            result = 0
        elif commands[1].lower() == 'createusertable':
            result = db_connection.create_user_table()
        elif commands[1].lower() == 'truncateusertable':
            Avalon.warning('By truncating you will LOSE ALL USER DATA')
            if Avalon.ask('Are you sure you want to truncate?'):
                result = db_connection.truncate_user_table()
            else:
                Avalon.warning('Operation canceled')
                result = 0
        elif commands[1].lower() == 'dropusertable':
            Avalon.warning('By dropping the table you will LOSE ALL USER DATA')
            if Avalon.ask('Are you sure you want to drop the table?'):
                result = db_connection.drop_user_table()
            else:
                Avalon.warning('Operation canceled')
                result = 0
        elif commands[1].lower() == 'verify':
            result = db_connection.verify(commands[2])
        elif commands[1].lower() == 'adduser':
            result = db_connection.add_user(commands[2], commands[3])
        elif commands[1].lower() == 'deluser':
            result = db_connection.del_user(commands[2])
        elif commands[1].lower() == 'show':
            if commands[2].lower() == 'users':
                result = db_connection.show_users()
            elif commands[2].lower() == 'quota':
                result = db_connection.show_users(show_quota=True)
        elif commands[1].lower() == 'setquota':
            result = db_connection.set_quota(commands[2], commands[3])
        elif commands[1].lower() == 'addquota':
            result = db_connection.add_quota(commands[2], commands[3])
        elif commands[1].lower() == 'clearusage':
            if len(commands) > 2:
                result = db_connection.clear_usage(commands[2])
            else:
                result = db_connection.clear_usage()
        elif commands[1].lower() == 'exit' or commands[1].lower() == 'quit':
            Avalon.warning('Exiting')
            exit(0)
        elif len(possibilities) > 0:
            Avalon.warning('Ambiguous command \"{}\"'.format(commands[1]))
            print('Use \"Help\" command to list available commands')
            result = 1
        else:
            Avalon.error('Invalid command')
            print('Use \"Help\" command to list available commands')
            result = 1
        return result
    except IndexError:
        Avalon.error('Invalid arguments')
        print('Use \"Help\" command to list available commands')
        result = 0


def main():
    """ Trojan Manager main function
    This function can only be executed when
    this file is not being imported.
    """
    # Create database controller connection
    try:
        trojan_db = TrojanDatabase('127.0.0.1', 'trojan', 'thisisthetrojandbpassword', 'trojan_db', 'users')
    except (MySQLdb.OperationalError) as e:
        Avalon.error('Error establishing connection to MySQL/MariaDB')
        Avalon.error('Please check your settings')
        traceback.print_exc()
        exit(1)

    # Begin command interpreting
    try:
        if sys.argv[1].lower() == 'interactive' or sys.argv[1].lower() == 'int':
            print_legal_info()
            # Set command completer
            completer = ShellCompleter(COMMANDS)
            readline.set_completer(completer.complete)
            readline.parse_and_bind('tab: complete')
            # Launch interactive trojan shell
            prompt = '{}[trojan]> {}'.format(Avalon.FM.BD, Avalon.FM.RST)
            while True:
                command_interpreter(trojan_db, [''] + input(prompt).split(' '))
        else:
            # Return to shell with command return value
            exit(command_interpreter(trojan_db, sys.argv[0:]))
    except IndexError:
        Avalon.warning('No commands specified')
        exit(0)
    except (KeyboardInterrupt, EOFError):
        Avalon.warning('Exiting')
        exit(0)
    except Exception:
        Avalon.error('Exception caught')
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
else:
    Avalon.warning('This file cannot be imported')
