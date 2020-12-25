from peewee import SqliteDatabase

db = SqliteDatabase('database.db', pragmas={
    'journal_mode': 'wal',
    'cache_size': -1024 * 64
})