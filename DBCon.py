import mysql.connector as mariadb
from constants import Constants
class DBConnector(object):

    def __init__(self, database, password, port):

        self.database = database
        self.password = password
        self.port = port

    def create_connection(self):
        return mariadb.connect(
            user="root",
            password=self.password,
            host="localhost",
            port=self.port,
            database=self.database,
            )

    # For explicitly opening database connection
    def __enter__(self):
        self.dbconn = self.create_connection()
        return self.dbconn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dbconn.close()

# https://stackoverflow.com/questions/40525545/single-database-connection-throughout-the-python-application-following-singleto

class DBConnection(object):

    connection = None
    database = Constants.DB_NAME
    password = Constants.DB_PASS
    port = Constants.DB_PORT

    @classmethod
    def get_connection(cls, new=False):
        if new or not cls.connection:
            cls.connection = DBConnector(cls.database, cls.password, cls.port).create_connection()
            cls.connection.autocommit = True
        return cls.connection

    @classmethod
    def execute_query(cls, query, item, returnAll=False, many=False):

        connection = cls.get_connection()
        try:
            cursor = connection.cursor()
        except mariadb.ProgrammingError:
            connection = cls.get_connection(new=True)  # Create new connection
            cursor = connection.cursor()

        # Checks if the item is an instance of a tuple or list - if not, turn it into a list item - this has
        # to be a list for sql to use it.
        if item is not None:
            if not isinstance(item, list) and not isinstance(item, tuple):
                item = [item]

        if many is True:
            cursor.executemany(query, item)

        elif item is None:
            cursor.execute(query)

        else:
            cursor.execute(query, item)

        if returnAll is True:
            result = cursor.fetchall()

        else:
            result = cursor.fetchone()


        cursor.close()
        return result
