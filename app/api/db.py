import os

from peewee import SqliteDatabase

path = os.path.join(os.getcwd(), 'gis_data', 'database.db')

db = SqliteDatabase(path, pragmas={
    'journal_mode': 'wal',
    'cache_size': -1024 * 64
})
