# -*- coding: utf-8 -*-
"""
Requires Python 3.8 or later

PostgreSQL DB backend.

Each one of the CRUD operations should be able to open a database connection if
there isn't already one available (check if there are any issues with this).

Documentation:
    About the Van data on the database to generate CRUD operations from endpoint of the API:
    - Insert Van data
    - Update Van data
    - Delete Van data
    - Search Van data by UUID
    - Search Van data by Status

    About the User to authenticate request endpoints on the API adding security to the operations:
    - Validate user data
    - Insert user data
    - Update user password hashed
"""


__author__ = "Jorge Morfinez Mojica (jorge.morfinez.m@gmail.com)"
__copyright__ = "Copyright 2021, Jorge Morfinez Mojica"
__license__ = ""
__history__ = """ """
__version__ = "1.1.A19.1 ($Rev: 1 $)"


import re
import json
import logging
from datetime import datetime

import psycopg2
from sqlalchemy import Column, String, Numeric
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base

from constants.constants import Constants as Const
from db_controller import mvc_exceptions as mvc_exc
from logger_controller.logger_control import *
from model.StoreModel import StoreModel
from model.ProductModel import ProductModel

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)

Base = declarative_base()
logger = configure_db_logger()


# Datos de conecxion a base de datos
def init_connect_db():
    r"""
    Contiene la inicializacion de datos para conectar a base de datos.
    :return: list_data_cnx
    """
    init_cnx_db_data = []

    cfg = get_config_constant_file()

    # TEST:
    db_host = cfg['DB_RDS']['HOST_DB']
    db_username = cfg['DB_RDS']['USER_DB']
    db_password = cfg['DB_RDS']['PASSWORD_DB']
    db_port = cfg['DB_RDS']['PORT_DB']
    db_driver = cfg['DB_RDS']['SQL_DRIVER']
    db_name = cfg['DB_RDS']['DATABASE_NAME']

    data_connection = [db_host, db_username, db_password, db_port, db_name]

    init_cnx_db_data.append(data_connection)

    return data_connection


def session_to_db():
    r"""
    Get and manage the session connect to the database engine.

    :return connection: Object to connect to the database and transact on it.
    """

    data_bd_connection = init_connect_db()

    connection = None

    try:

        if data_bd_connection:

            connection = psycopg2.connect(user=data_bd_connection[1],
                                          password=data_bd_connection[2],
                                          host=data_bd_connection[0],
                                          port=data_bd_connection[3],
                                          database=data_bd_connection[4])

        else:
            logger.error('Some data is not established to connect PostgreSQL DB. Please verify it!')

    except (Exception, psycopg2.Error) as error:
        logger.exception('Can not connect to database, verify data connection to %s', data_bd_connection[4],
                         error, exc_info=True)
        raise mvc_exc.ConnectionError(
            '"{}" Can not connect to database, verify data connection to "{}".\nOriginal Exception raised: {}'.format(
                data_bd_connection[0], data_bd_connection[4], error
            )
        )

    return connection


def scrub(input_string):
    """Clean an input string (to prevent SQL injection).

    Parameters
    ----------
    input_string : str

    Returns
    -------
    str
    """
    return "".join(k for k in input_string if k.isalnum())


def create_cursor(conn):
    r"""
    Create an object statement to transact to the database and manage his data.

    :param conn: Object to connect to the database.
    :return cursor: Object statement to transact to the database with the connection.

    """
    try:
        cursor = conn.cursor()

    except (Exception, psycopg2.Error) as error:
        logger.exception('Can not create the cursor object, verify database connection', error, exc_info=True)
        raise mvc_exc.ConnectionError(
            'Can not connect to database, verify data connection.\nOriginal Exception raised: {}'.format(
                error
            )
        )

    return cursor


def disconnect_from_db(conn):
    r"""
    Generate close session to the database through the disconnection of the conn object.

    :param conn: Object connector to close session.
    """

    if conn is not None:
        conn.close()


def close_cursor(cursor):
    r"""
    Generate close statement to the database through the disconnection of the cursor object.

    :param cursor: Object cursor to close statement.
    """

    if cursor is not None:
        cursor.close()


def get_datenow_from_db():
    r"""
    Get the current date and hour from the database server to set to the row registered or updated.

    :return last_updated_date: The current day with hour to set the date value.
    """

    conn = None
    cursor = None
    last_updated_date = None
    sql_nowdate = ''

    try:

        sql_nowdate = 'SELECT now()'

        conn = session_to_db()
        cursor = create_cursor(conn)

        cursor.execute(sql_nowdate)

        result = cursor.fetchall()

        if result is not None:
            last_updated_date = result

        cursor.close()

    except SQLAlchemyError as error:
        conn.rollback()
        logger.exception('An exception occurred while execute transaction: %s', error)
        raise SQLAlchemyError(
            "A SQL Exception {} occurred while transacting with the database.".format(error)
        )
    finally:
        disconnect_from_db(conn)

    return last_updated_date


def get_nextval_economic_number_van(conn):
    r"""
    Get the next value number to set as part of Economic Number in a Van attribute.
    Use it to create a new Van register on the database.

    :param conn: Object to create a session to connect to the database.
    :return economic_number_nextval: The next value data to set to the Van Economic Number.
    """

    cursor = None
    economic_number_nextval = int()
    sql_nextval_seq = ""

    try:
        sql_nextval_seq = "SELECT nextval('urbvan.eco_num_van')"

        cursor = create_cursor(conn)

        cursor.execute(sql_nextval_seq)

        economic_number_nextval = cursor.fetchone()

        close_cursor(cursor)

        if economic_number_nextval:
            return economic_number_nextval

    except SQLAlchemyError as error:
        conn.rollback()
        logger.exception('An exception occurred while execute transaction: %s', error)
        raise SQLAlchemyError(
            "A SQL Exception {} occurred while transacting with the database.".format(error)
        )


def exists_data_row(table_name, column_name, column_filter1, value1, column_filter2, value2):
    r"""
    Transaction that validates the existence and searches for a certain record in the database.

    :param table_name: The table name to looking for data.
    :param column_name: The name of the column to find existence.
    :param column_filter1: The name of the first column filter to looking for data.
    :param value1: The value of the first filter to looking for data.
    :param column_filter2: The name of the next column filter to looking for data.
    :param value2: The value of the next filter to looking for data.
    :return row_data: The data if row exists.
    """

    conn = None
    cursor = None
    row_data = None

    try:
        conn = session_to_db()
        cursor = conn.cursor()

        sql_exists = f"SELECT {column_name} FROM {table_name} " \
                     f"WHERE {column_filter1} = {value1} AND {column_filter2} = '{value2}'"

        cursor.execute(sql_exists)

        row_exists = cursor.fetchall()

        # row_exists = session.execute(sql_exists)

        for r_e in row_exists:

            logger.info('Row Info in Query: %s', str(r_e))

            if r_e is None:
                r_e = None
            else:
                row_data = r_e[column_name]

            # row_exists.close()

            close_cursor(cursor)

    except SQLAlchemyError as error:
        conn.rollback()
        logger.exception('An exception occurred while execute transaction: %s', error)
        raise SQLAlchemyError(
            "A SQL Exception {} occurred while transacting with the database on table {}.".format(error, table_name)
        )
    finally:
        disconnect_from_db(conn)

    return row_data


def validate_transaction(table_name,
                         column_name,
                         column_filter1, value1,
                         column_filter2, value2,
                         column_filter3, value3):
    r"""
    Transaction that validates the existence and searches for a certain record in the database.

    :param table_name: The table name to looking for data.
    :param column_name: The name of the column to find existence.
    :param column_filter1: The name of the first column filter to looking for data.
    :param value1: The value of the first filter to looking for data.
    :param column_filter2: The name of the next column filter to looking for data.
    :param value2: The value of the next filter to looking for data.
    :param column_filter3: The name of the next column filter to looking for data.
    :param value3: The value of the next filter to looking for data.
    :return row_data: The data if row exists.
    """

    conn = None
    cursor = None
    row_data = None

    try:
        conn = session_to_db()
        cursor = conn.cursor()

        sql_exists = 'SELECT {} FROM {} WHERE {} = {} AND {} = {} AND {} = {}'.format(column_name, table_name,
                                                                                      column_filter1, value1,
                                                                                      column_filter2, "'" + value2 + "'",
                                                                                      column_filter3, "'" + value3 + "'")

        cursor.execute(sql_exists)

        row_exists = cursor.fetchall()

        for r_e in row_exists:

            logger.info('Row Info in Query: %s', str(r_e))

            if r_e is None:
                r_e = None
            else:
                row_data = r_e[column_name]

            close_cursor(cursor)

    except SQLAlchemyError as error:
        conn.rollback()
        logger.exception('An exception occurred while execute transaction: %s', error)
        raise SQLAlchemyError(
            "A SQL Exception {} occurred while transacting with the database on table {}.".format(error, table_name)
        )
    finally:
        disconnect_from_db(conn)

    return row_data


class StoreModelDb(Base):

    r"""
    Class to instance the data of a Van on the database.
    Transactions:
     - Insert: Add Van data to the database if not exists.
     - Update: Update Van data on the database if exists.
    """

    cfg = get_config_constant_file()

    __tablename__ = cfg['DB_OBJECTS']['STORE_TABLE']

    uuid_van = Column(cfg['DB_COLUMNS_DATA']['VAN_VEHICLE']['UUID_VAN'], String, primary_key=True)
    plates_van = Column(cfg['DB_COLUMNS_DATA']['VAN_VEHICLE']['PLATES_VAN'], String)
    economic_number_van = Column(cfg['DB_COLUMNS_DATA']['VAN_VEHICLE']['ECONOMIC_NUMBER'], String)
    seats_van = Column(cfg['DB_COLUMNS_DATA']['VAN_VEHICLE']['SEATS_VAN'], Numeric)
    created_at = Column(cfg['DB_COLUMNS_DATA']['VAN_VEHICLE']['CREATED_AT'], String)
    status_van = Column(cfg['DB_COLUMNS_DATA']['VAN_VEHICLE']['STATUS_VAN'], String)

    def manage_van_vehicle_data(self, uuid_van, plates_van, economic_number_van, seats_van, status_van):

        van_data = {}

        # session = self

        if exists_data_row(self.__tablename__,
                           self.uuid_van,
                           self.uuid_van,
                           uuid_van,
                           self.plates_van,
                           plates_van):

            van_data = update_store_data(self.__tablename__,
                                         uuid_van,
                                         plates_van,
                                         economic_number_van,
                                         seats_van,
                                         status_van)
        else:
            van_data = insert_new_store(self.__tablename__,
                                        uuid_van,
                                        plates_van,
                                        economic_number_van,
                                        seats_van,
                                        status_van)

        return van_data


# Add Van data to insert the row on the database
def insert_new_store(table_name, store_obj: StoreModel):
    r"""
    Transaction to add data of a Van and inserted on database.
    The data that you can insert are:

    :param table_name: The table name to looking for data van.
    :param store_obj: Store object model to add new store data.
    :return store_data_inserted: Dictionary that contains Store data inserted on db.
    """

    conn = None
    cursor = None
    store_data_inserted = dict()

    try:
        conn = session_to_db()

        cursor = conn.cursor()

        created_at = get_datenow_from_db()
        last_update_date = get_datenow_from_db()

        store_id = store_obj.get_id_store()
        store_code = store_obj.get_store_code()
        store_name = store_obj.get_store_name()
        store_external_number = store_obj.get_external_number()
        store_street_address = store_obj.get_street_address()
        store_suburb_address = store_obj.get_suburb_address()
        store_city_address = store_obj.get_city_address()
        store_country_address = store_obj.get_country_address()
        store_zippostal_code = store_obj.get_zip_postal_address()
        store_min_inventory = store_obj.get_minimum_stock()

        data_insert = (store_id, store_code, store_name, store_external_number, store_street_address,
                       store_suburb_address, store_city_address, store_country_address, store_zippostal_code,
                       store_min_inventory,)

        sql_store_insert = 'INSERT INTO cargamos.store_api ' \
                           '(id_store, ' \
                           'store_name, ' \
                           'store_code, ' \
                           'store_street_address, ' \
                           'store_external_number, ' \
                           'store_suburb_address, ' \
                           'store_city_address, ' \
                           'store_country_address, ' \
                           'store_zippostal_code, ' \
                           'store_min_inventory, ' \
                           'creation_date, ' \
                           'last_update_date) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'.format(table_name)

        cursor.execute(sql_store_insert, data_insert)

        conn.commit()

        logger.info('Store inserted %s', "{0}, Code: {1}, Name: {2}".format(store_id, store_code, store_name))

        close_cursor(cursor)

        row_exists = validate_transaction(table_name,
                                          'id_store',
                                          'id_store', store_id,
                                          'store_code', store_code,
                                          'store_name', store_name)

        address_store = format_store_address(store_street_address,
                                             store_external_number,
                                             store_suburb_address,
                                             store_zippostal_code,
                                             store_city_address,
                                             store_country_address)

        if str(store_id) not in str(row_exists):

            store_data_inserted = {
                "IdStore": store_id,
                "CodeStore": store_code,
                "NameStore": store_name,
                "AddressStore": address_store,
                "MinimumStock": store_min_inventory,
                "CreationDate": created_at,
                "Message": "Store Inserted Successful",
            }

        else:
            store_data_inserted = {
                "IdStore": store_id,
                "CodeStore": store_code,
                "NameStore": store_name,
                "AddressStore": address_store,
                "MinimumStock": store_min_inventory,
                "CreationDate": created_at,
                "Message": "Store already Inserted",
            }

    except SQLAlchemyError as error:
        conn.rollback()
        logger.exception('An exception was occurred while execute transaction: %s', error)
        raise SQLAlchemyError(
            "A SQL Exception {} occurred while transacting with the database on table {}.".format(error, table_name)
        )
    finally:
        disconnect_from_db(conn)

    return json.dumps(store_data_inserted)


# Update van data registered
def update_store_data(table_name, data_store):
    r"""
    Transaction to update data of a Van registered on database.
    The data that you can update are:

    :param table_name: The table name to looking for data.
    :param data_store: Dictionary of all data store to update.
    :return store_data_updated: Dictionary that contains Store data updated on db.
    """

    conn = None
    cursor = None
    store_data_updated = dict()

    try:
        conn = session_to_db()

        cursor = conn.cursor()

        last_update_date = get_datenow_from_db()

        store_id = data_store.get("store_id")
        store_code = data_store.get("store_code")
        store_name = data_store.get("store_name")
        street_address = data_store("street_address")
        external_number_address = data_store("external_number_address")
        suburb_address = data_store.get("suburb_address")
        city_address = data_store.get("city_address")
        country_address = data_store.get("country_address")
        zip_postal_code_address = data_store.get("zip_postal_code_address")
        minimum_stock = data_store.get("minimum_inventory")

        # update row to database
        sql_update_store = 'UPDATE {} ' \
                           'SET store_name=%s, ' \
                           'store_street_address=%s, ' \
                           'store_external_number=%s, ' \
                           'store_suburb_address=%s, ' \
                           'store_city_address=%s, ' \
                           'store_country_address=%s, ' \
                           'store_zippostal_code=%s, ' \
                           'store_min_inventory=%s, ' \
                           'last_update_date=%s ' \
                           'WHERE id_store=%s AND store_code=%s'.format(table_name)

        cursor.execute(sql_update_store, (store_name,
                                          street_address,
                                          external_number_address,
                                          suburb_address,
                                          city_address,
                                          country_address,
                                          zip_postal_code_address,
                                          minimum_stock,))

        address_store = format_store_address(street_address,
                                             external_number_address,
                                             suburb_address,
                                             zip_postal_code_address,
                                             city_address,
                                             country_address)

        conn.commit()

        close_cursor(cursor)

        row_exists = validate_transaction(table_name,
                                          'id_store',
                                          'id_store', store_id,
                                          'store_code', store_code,
                                          'store_name', store_name)

        if str(store_id) in str(row_exists):

            store_data_updated = {
                "IdStore": store_id,
                "CodeStore": store_code,
                "NameStore": store_name,
                "AddressStore": address_store,
                "MinimumStock": minimum_stock,
                "LastUpdateDate": last_update_date,
                "Message": "Store Updated Successful",
            }

        else:

            store_data_updated = {
                "IdStore": store_id,
                "CodeStore": store_code,
                "NameStore": store_name,
                "AddressStore": address_store,
                "MinimumStock": minimum_stock,
                "LastUpdateDate": last_update_date,
                "Message": "Store not updated",
            }

            logger.error('Can not read the recordset: {}, beacause is not stored on table: {}'.format(status_van,
                                                                                                      table_name))
            raise SQLAlchemyError(
                "Can\'t read data because it\'s not stored in table {}. SQL Exception".format(table_name)
            )

    except SQLAlchemyError as error:
        conn.rollback()
        logger.exception('An exception occurred while execute transaction: %s', error)
        raise SQLAlchemyError(
            "A SQL Exception {} occurred while transacting with the database on table {}.".format(error, table_name)
        )
    finally:
        disconnect_from_db(conn)

    return json.dumps(store_data_updated)


# Delete store registered by id and code
def delete_store_data(table_name, store_id, store_code):
    r"""
    Transaction to delete a Van data registered on database from his uuid and plates.

    :param table_name: The table name to looking for data van.
    :param store_id: Id to looking for a Store data to delete.
    :param store_code: Code to looking for a Store data to delete.
    :return van_data_delete: Dictionary contains Van data deleted.
    """

    conn = None
    cursor = None
    store_data_deleted = dict()

    try:
        conn = session_to_db()

        cursor = conn.cursor()

        # delete row to database
        sql_delete_van = "DELETE FROM {} WHERE id_store=%s AND store_code=%s".format(table_name)

        cursor.execute(sql_delete_van, (store_id, store_code,))

        conn.commit()

        close_cursor(cursor)

        store_data_deleted = {
            "IdStore": store_id,
            "CodeStore": store_code,
            "Message": "Store Deleted Successful",
        }

        row_exists = exists_data_row(table_name,
                                     'id_store',
                                     'id_store', store_id,
                                     'store_code', store_code)

        if str(store_id) in str(row_exists):

            store_data_deleted = {
                "IdStore": store_id,
                "CodeStore": store_code,
                "Message": "Store not deleted",
            }

        else:

            logger.error('Can not read the recordset: {}, because is not stored on table: {}'.format(store_id,
                                                                                                     table_name))
            raise mvc_exc.ItemNotStored(
                'Can\'t read "{}" because it\'s not stored in table "{}. SQL Exception"'.format(
                    store_id, table_name
                )
            )

    except SQLAlchemyError as error:
        conn.rollback()
        logger.exception('An exception occurred while execute transaction: %s', error)
        raise SQLAlchemyError(
            "A SQL Exception {} occurred while transacting with the database on table {}.".format(error, table_name)
        )
    finally:
        disconnect_from_db(conn)

    return json.dumps(store_data_deleted)


# Format Store Address
def format_store_address(street_address, external_number_address, suburb_address, zip_postal_code_address, city_address,
                         country_address):
    address_store = "{} no. {}, col. {}, Cp. {}, {}, {}".format(street_address,
                                                                external_number_address,
                                                                suburb_address,
                                                                zip_postal_code_address,
                                                                city_address,
                                                                country_address)

    return address_store


# Select all data van by uuid from db
def select_van_by_uuid(table_name, uuid_van):
    r"""
    Get all the Van's data looking for specific status on database.

    :param table_name: The table name to looking for data van.
    :param uuid_van: Id to looking for a Van data.
    :return data_van_by_uuid: Dictionary that contains all the Van's data by specific UUID.
    """

    conn = None
    cursor = None

    van_data_by_id = []
    data_van_all = dict()

    try:

        conn = session_to_db()

        cursor = conn.cursor()

        sql_van_by_id = " SELECT uuid_van, " \
                        "        plates_van, " \
                        "        economic_number_van, " \
                        "        seats_van, " \
                        "        created_at, " \
                        "        status_van, " \
                        "        last_update_date " \
                        " FROM {} " \
                        " WHERE uuid_van = %s".format(table_name)

        cursor.execute(sql_van_by_id, (uuid_van,))

        result = cursor.fetchall()

        if result is not None:
            for van_data in result:
                if van_data is not None:

                    uuid_van = van_data['uuid_van']
                    plates_van = van_data['plates_van']
                    economic_number = van_data['economic_number_van']
                    seats_van = van_data['seats_van']
                    fecha_creacion = datetime.strptime(str(van_data['created_at']), "%Y-%m-%d %H:%M:%S")
                    status_van = van_data['status_van']
                    fecha_actualizacion = datetime.strptime(str(van_data['last_update_date']), "%Y-%m-%d %H:%M:%S")

                    logger.info('Van Registered: %s', 'VanUUId: {}, '
                                                      'VanPlates: {}, '
                                                      'VanEconomicNumber: {}, '
                                                      'VanSeats: {}, '
                                                      'VanStatus: {}, '
                                                      'VanCreatedAt: {} '.format(uuid_van,
                                                                                 plates_van,
                                                                                 economic_number,
                                                                                 seats_van,
                                                                                 status_van,
                                                                                 fecha_creacion))

                    van_data_by_id += [{
                        "VanVehicle": {
                            "UUID": uuid_van,
                            "Plate": plates_van,
                            "EconomicNumber": economic_number,
                            "SeatsNumber": seats_van,
                            "Status": status_van,
                            "CreationDate": fecha_creacion,
                            "LastUpdateDate": fecha_actualizacion,
                        }
                    }]

                else:
                    logger.error('Can not read the recordset: {}, '
                                 'beacause is not stored on table: {}'.format(uuid_van, table_name))
                    raise SQLAlchemyError(
                        "Can\'t read data because it\'s not stored in table {}. SQL Exception".format(table_name)
                    )
        else:
            logger.error('Can not read the recordset, because is not stored: %s', uuid_van)
            raise mvc_exc.ItemNotStored(
                'Can\'t read "{}" because it\'s not stored in table "{}. SQL Exception"'.format(
                    uuid_van, table_name
                )
            )

        close_cursor(cursor)

        data_van_all = json.dumps(van_data_by_id)

    except SQLAlchemyError as error:
        conn.rollback()
        logger.exception('An exception occurred while execute transaction: %s', error)
        raise SQLAlchemyError(
            "A SQL Exception {} occurred while transacting with the database on table {}.".format(error, table_name)
        )
    finally:
        disconnect_from_db(conn)

    return data_van_all


# Select all data van by status from db
def select_van_by_status(table_name, status_van):
    r"""
    Get all the Van's data looking for specific status on database.

    :param table_name: The table name to looking for data van.
    :param status_van: Status to looking for a Van data.
    :return data_van_by_status: Dictionary that contains all the Van's data by specific status.
    """

    conn = None
    cursor = None

    van_data_by_status = []
    data_van_all = dict()

    try:

        conn = session_to_db()

        cursor = conn.cursor()

        sql_van_by_id = " SELECT uuid_van, " \
                        "        plates_van, " \
                        "        economic_number_van, " \
                        "        seats_van, " \
                        "        created_at, " \
                        "        status_van, " \
                        "        last_update_date " \
                        " FROM {} " \
                        " WHERE status_van = %s".format(table_name)

        cursor.execute(sql_van_by_id, (status_van,))

        result = cursor.fetchall()

        if result is not None:
            for van_data in result:
                if van_data is not None:

                    uuid_van = van_data['uuid_van']
                    plates_van = van_data['plates_van']
                    economic_number = van_data['economic_number_van']
                    seats_van = van_data['seats_van']
                    fecha_creacion = datetime.strptime(str(van_data['created_at']), "%Y-%m-%d %H:%M:%S")
                    status_van = van_data['status_van']
                    fecha_actualizacion = datetime.strptime(str(van_data['last_update_date']), "%Y-%m-%d %H:%M:%S")

                    logger.info('Van Registered: %s', 'VanUUId: {}, '
                                                      'VanPlates: {}, '
                                                      'VanEconomicNumber: {}, '
                                                      'VanSeats: {}, '
                                                      'VanStatus: {}, '
                                                      'VanCreatedAt: {} '.format(uuid_van,
                                                                                 plates_van,
                                                                                 economic_number,
                                                                                 seats_van,
                                                                                 status_van,
                                                                                 fecha_creacion))

                    van_data_by_status += [{
                        "VanVehicle": {
                            "UUID": uuid_van,
                            "Plate": plates_van,
                            "EconomicNumber": economic_number,
                            "SeatsNumber": seats_van,
                            "Status": status_van,
                            "CreationDate": fecha_creacion,
                            "LastUpdateDate": fecha_actualizacion,
                        }
                    }]

                else:
                    logger.error('Can not read the recordset: {}, '
                                 'beacause is not stored on table: {}'.format(status_van, table_name))
                    raise SQLAlchemyError(
                        "Can\'t read data because it\'s not stored in table {}. SQL Exception".format(table_name)
                    )
        else:
            logger.error('Can not read the recordset, because is not stored: %s', status_van)
            raise mvc_exc.ItemNotStored(
                'Can\'t read "{}" because it\'s not stored in table "{}. SQL Exception"'.format(
                    status_van, table_name
                )
            )

        close_cursor(cursor)

        data_van_all = json.dumps(van_data_by_status)

    except SQLAlchemyError as error:
        conn.rollback()
        logger.exception('An exception occurred while execute transaction: %s', error)
        raise SQLAlchemyError(
            "A SQL Exception {} occurred while transacting with the database on table {}.".format(error, table_name)
        )
    finally:
        disconnect_from_db(conn)

    return data_van_all


class UsersAuth(Base):
    r"""
    Class to instance User data to authenticate the API.
    Transactions:
     - Insert: Add user data to the database if not exists.
     - Update: Update user data on the database if exists.
    """

    cfg = get_config_constant_file()

    __tablename__ = cfg['DB_AUTH_OBJECT']['USERS_AUTH']

    user_id = Column(cfg['DB_AUTH_COLUMNS_DATA']['USER_AUTH']['USER_ID'], Numeric, primary_key=True)
    user_name = Column(cfg['DB_AUTH_COLUMNS_DATA']['USER_AUTH']['USER_NAME'], String, primary_key=True)
    user_password = Column(cfg['DB_AUTH_COLUMNS_DATA']['USER_AUTH']['USER_PASSWORD'], String)
    password_hash = Column(cfg['DB_AUTH_COLUMNS_DATA']['USER_AUTH']['PASSWORD_HASH'], String)
    last_update_date = Column(cfg['DB_AUTH_COLUMNS_DATA']['USER_AUTH']['LAST_UPDATE_DATE'], String)

    @staticmethod
    def manage_user_authentication(user_id, user_name, user_password, password_hash):

        try:

            user_verification = validate_user_exists(user_name)

            # insert validation
            if user_verification[0]:

                # update method
                update_user_password_hashed(user_name, password_hash)

            else:
                # insert

                insert_user_authenticated(user_id, user_name, user_password, password_hash)

        except SQLAlchemyError as e:
            logger.exception('An exception was occurred while execute transactions: %s', e)
            raise mvc_exc.ItemNotStored(
                'Can\'t insert user_id: "{}" with user_name: {} because it\'s not stored in "{}"'.format(
                    user_id, user_name, UsersAuth.__tablename__
                )
            )


# Transaction to looking for a user on db to authenticate
def validate_user_exists(user_name):
    r"""
    Looking for a user by name on the database to valid authentication.

    :param user_name: The user name to valid authentication on the API.
    :return result: Boolean to valid if the user name exists to authenticate the API.
    """

    cfg = get_config_constant_file()

    conn = session_to_db()

    cursor = conn.cursor()

    table_name = cfg['DB_AUTH_OBJECT']['USERS_AUTH']

    sql_check = "SELECT EXISTS(SELECT 1 FROM {} WHERE username = {} LIMIT 1)".format(table_name, "'" + user_name + "'")

    cursor.execute(sql_check)

    result = cursor.fetchone()

    return result


# Transaction to update user' password  hashed on db to authenticate
def update_user_password_hashed(user_name, password_hash):
    r"""
    Transaction to update password hashed of a user to authenticate on the API correctly.

    :param user_name: The user name to update password hashed.
    :param password_hash: The password hashed to authenticate on the API.
    """

    cfg = get_config_constant_file()

    conn = session_to_db()

    cursor = create_cursor(conn)

    last_update_date = get_datenow_from_db()

    table_name = cfg['DB_AUTH_OBJECT']['USERS_AUTH']

    # update row to database
    sql_update_user = "UPDATE {} SET password_hash = %s, last_update_date = NOW() WHERE username = %s".format(
        table_name
    )

    cursor.execute(sql_update_user, (password_hash, user_name,))

    conn.commit()

    close_cursor(cursor)


def insert_user_authenticated(user_id, user_name, user_password, password_hash):
    r"""
    Transaction to add a user data to authenticate to API, inserted on the db.

    :param user_id: The Id of the user to add on the db.
    :param user_name: The user name of the user to add on the db.
    :param user_password:  The password od the user to add on the db.
    :param password_hash: The password hashed to authenticate on the API.
    """

    cfg = get_config_constant_file()

    conn = session_to_db()

    cursor = create_cursor(conn)

    last_update_date = get_datenow_from_db()

    table_name = cfg['DB_AUTH_OBJECT']['USERS_AUTH']

    data = (user_id, user_name, user_password, password_hash,)

    sql_user_insert = 'INSERT INTO {} (user_id, username, password, password_hash) ' \
                      'VALUES (%s, %s, %s, %s)'.format(table_name)

    cursor.execute(sql_user_insert, data)

    conn.commit()

    logger.info('Usuario insertado %s', "{0}, User_Name: {1}".format(user_id, user_name))

    close_cursor(cursor)


# Function not used.
def get_data_user_authentication(session, table_name, user_name):
    user_auth = []

    user_auth_data = {}

    try:
        sql_user_data = " SELECT user_name, user_password, password_hash, last_update_date " \
                        " FROM {} " \
                        " WHERE user_name = {} ".format(table_name, "'" + user_name + "'")

        user_auth_db = session.execute(sql_user_data)

        for user in user_auth_db:
            if user is not None:

                user_name_db = user['username']
                user_password_db = user['password']
                password_hash = user['password_hash']
                last_update_date = datetime.strptime(str(user['last_update_date']), "%Y-%m-%d")

                user_auth += [{
                    "username": user_name_db,
                    "password": user_password_db,
                    "password_hash": password_hash,
                    "date_updated": last_update_date
                }]

            else:
                logger.error('Can not read the recordset, beacause is not stored')
                raise SQLAlchemyError(
                    "Can\'t read data because it\'s not stored in table {}. SQL Exception".format(table_name)
                )

        user_auth_data = json.dumps(user_auth)

        user_auth_db.close()

    except SQLAlchemyError as sql_exec:
        logger.exception(sql_exec)
    finally:
        session.close()

    return user_auth_data


# Define y obtiene el configurador para las constantes del sistema:
def get_config_constant_file():
    """
    Contiene la obtencion del objeto config
    para setear datos de constantes en archivo
    configurador.

    :return object: ocfg object, contain the Map to the constants allowed in Constants File configuration.
    """

    # PROD
    _constants_file = "/app/constants/constants.yml"

    # TEST
    # _constants_file = "/home/jorgemm/Documentos/PycharmProjects/urbvan_microservice_test/constants/constants.yml"

    cfg = Const.get_constants_file(_constants_file)

    return cfg
